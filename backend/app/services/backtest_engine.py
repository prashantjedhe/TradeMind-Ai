"""
Historical OHLCV replay engine.

Assumptions (documented for academic defensibility):
- Signals are evaluated on bar i using only bars[0..i] (inclusive close).
- MARKET fills occur at the *next* bar's open, then adverse slippage.
  This prevents using bar i's close as a same-bar fill (look-ahead).
- LIMIT fills at the limit if the subsequent bar trades through it;
  if the next open gaps through the limit, fill at that open (gap).
- SL/TP are checked on bars after entry using that bar's high/low.
  If both would trigger in the same bar, SL is assumed (worst case).
- NSE fee_calculator is used per fill (delivery vs intraday, F&O rates).
- SENTIMENT leaves are not evaluated on historical replay (no future
  news). They resolve False, matching missing-indicator warm-up.
- Cash and positions are tracked; entries that exceed cash are skipped.
- Monetary values use Decimal (paise). Equity series is float for metrics.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import numpy as np
import pandas as pd

from app.models.order import OrderSide, SettlementType
from app.models.strategy import StrategyActionOrderType
from app.services.fee_calculator import calculate_fees
from app.services.order_service import SLIPPAGE_RATE as DEFAULT_SLIPPAGE
from app.services.strategy_service import evaluate_condition_tree, required_bars_for_tree

CENTS = Decimal("0.01")
PAISE = ROUND_HALF_UP
INITIAL_CAPITAL_DEFAULT = Decimal("1000000.00")
RISK_FREE_ANNUAL = 0.06
TRADING_DAYS = 252
PROFIT_FACTOR_CAP = 999.9999


def _q(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=PAISE)


def _finite(value: float, default: float = 0.0) -> float:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return default
    return v if math.isfinite(v) else default


@dataclass
class BacktestSpec:
    root_condition: dict | None
    action_side: OrderSide
    action_order_type: StrategyActionOrderType
    action_quantity: int
    action_settlement_type: SettlementType
    action_limit_price: Decimal | None
    ticker: str


@dataclass
class BacktestConfig:
    initial_capital: Decimal = INITIAL_CAPITAL_DEFAULT
    slippage_rate: Decimal = DEFAULT_SLIPPAGE
    sl_pct: Decimal | None = Decimal("0.03")
    tp_pct: Decimal | None = Decimal("0.06")
    flatten_at_end: bool = True


@dataclass
class FillRecord:
    timestamp: str
    side: str
    order_type: str
    reason: str
    price: float
    qty: int
    fees: float
    cash_after: float
    pnl: float | None = None
    position_after: int = 0


@dataclass
class SimulationResult:
    equity: pd.Series
    trades: list[FillRecord]
    final_cash: Decimal
    final_position: int
    skipped_insufficient_cash: int = 0
    error: str | None = None
    notes: list[str] = field(default_factory=list)


def sanitize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Drop invalid / duplicate bars. Index must be timestamps."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        raise ValueError("OHLCV index must be a DatetimeIndex")

    if out.index.tz is None:
        out.index = out.index.tz_localize("UTC")
    else:
        out.index = out.index.tz_convert("UTC")

    out = out.sort_index()
    out = out[~out.index.duplicated(keep="first")]
    for col in ("open", "high", "low", "close"):
        if col not in out.columns:
            return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if "volume" not in out.columns:
        out["volume"] = 0
    out["volume"] = pd.to_numeric(out["volume"], errors="coerce").fillna(0).astype(int)
    out = out.dropna(subset=["open", "high", "low", "close"])
    valid = (
        (out["high"] >= out["low"])
        & (out["high"] >= out["open"])
        & (out["high"] >= out["close"])
        & (out["low"] <= out["open"])
        & (out["low"] <= out["close"])
        & (out["open"] > 0)
        & (out["close"] > 0)
    )
    return out.loc[valid]


def apply_slippage(price: Decimal, side: OrderSide, rate: Decimal) -> Decimal:
    if side == OrderSide.BUY:
        adjusted = price * (1 + rate)
    else:
        adjusted = price * (1 - rate)
    return _q(adjusted)


def _limit_fill_price(
    side: OrderSide,
    limit_price: Decimal,
    bar_open: Decimal,
    bar_high: Decimal,
    bar_low: Decimal,
) -> Decimal | None:
    """Return fill price if the limit is tradable on this bar, else None."""
    if side == OrderSide.BUY:
        if bar_low <= limit_price:
            if bar_open <= limit_price:
                return _q(bar_open)
            return _q(limit_price)
        return None
    if bar_high >= limit_price:
        if bar_open >= limit_price:
            return _q(bar_open)
        return _q(limit_price)
    return None


def _sl_hit(side: OrderSide, sl_price: Decimal, bar_high: Decimal, bar_low: Decimal) -> bool:
    if side == OrderSide.BUY:  # long: SL is sell below
        return bar_low <= sl_price
    return bar_high >= sl_price  # short: SL is buy above


def _tp_hit(side: OrderSide, tp_price: Decimal, bar_high: Decimal, bar_low: Decimal) -> bool:
    if side == OrderSide.BUY:
        return bar_high >= tp_price
    return bar_low <= tp_price


class _Portfolio:
    def __init__(self, cash: Decimal):
        self.cash = _q(cash)
        self.qty = 0  # signed: >0 long, <0 short
        self.avg_entry = Decimal("0")
        self.entry_side: OrderSide | None = None

    @property
    def is_flat(self) -> bool:
        return self.qty == 0

    def mark(self, price: Decimal) -> Decimal:
        return _q(self.cash + Decimal(self.qty) * price)


def _fees(price: Decimal, qty: int, side: OrderSide, settlement: SettlementType, ticker: str) -> Decimal:
    return calculate_fees(price, abs(qty), side, settlement, ticker=ticker).total_fees


def simulate_strategy(
    df: pd.DataFrame,
    spec: BacktestSpec,
    config: BacktestConfig | None = None,
    trade_start: datetime | None = None,
    trade_end: datetime | None = None,
) -> SimulationResult:
    """
    Replay `spec` on sanitized OHLCV.

    trade_start/trade_end restrict *execution* (not indicator history).
    Bars before trade_start are warm-up only — no orders.
    """
    config = config or BacktestConfig()
    notes = [
        "Signals use bars through the current close only.",
        "MARKET fills at the next bar open with adverse slippage.",
        "SENTIMENT conditions are ignored in historical replay.",
        "Same-bar SL and TP: stop-loss is assumed (conservative).",
    ]

    if config.initial_capital <= 0:
        empty = pd.Series(dtype=float)
        return SimulationResult(empty, [], Decimal("0"), 0, error="Initial capital must be positive")

    clean = sanitize_ohlcv(df)
    if clean.empty:
        empty = pd.Series([float(config.initial_capital)], index=pd.DatetimeIndex(
            [datetime.now(timezone.utc)], name="timestamp"))
        return SimulationResult(empty, [], config.initial_capital, 0, error="No valid OHLCV bars")

    required = 2
    if spec.root_condition:
        required = max(required_bars_for_tree(spec.root_condition), 2)

    if len(clean) < required + 1:
        empty = pd.Series([float(config.initial_capital)], index=pd.DatetimeIndex([clean.index[0]], name="timestamp"))
        return SimulationResult(
            empty, [], config.initial_capital, 0,
            error=f"Insufficient history: need {required + 1} bars, have {len(clean)}",
        )

    port = _Portfolio(config.initial_capital)
    trades: list[FillRecord] = []
    equity_pts: list[tuple[Any, float]] = []
    skipped = 0
    pending: dict | None = None  # execute on next bar
    sl_price: Decimal | None = None
    tp_price: Decimal | None = None

    def in_trade_window(ts) -> bool:
        ts = pd.Timestamp(ts)
        if ts.tzinfo is None:
            ts = ts.tz_localize("UTC")
        if trade_start is not None:
            start = pd.Timestamp(trade_start)
            if start.tzinfo is None:
                start = start.tz_localize("UTC")
            if ts < start:
                return False
        if trade_end is not None:
            end = pd.Timestamp(trade_end)
            if end.tzinfo is None:
                end = end.tz_localize("UTC")
            if ts >= end:
                return False
        return True

    def record_fill(ts, side: OrderSide, order_type: str, reason: str, price: Decimal, qty: int, fees: Decimal, pnl: Decimal | None):
        trades.append(FillRecord(
            timestamp=pd.Timestamp(ts).tz_convert("UTC").isoformat(),
            side=side.value,
            order_type=order_type,
            reason=reason,
            price=float(price),
            qty=qty,
            fees=float(fees),
            cash_after=float(port.cash),
            pnl=float(pnl) if pnl is not None else None,
            position_after=port.qty,
        ))

    def close_position(ts, price: Decimal, order_type: str, reason: str, apply_slip: bool) -> None:
        nonlocal sl_price, tp_price
        if port.is_flat:
            return
        qty = abs(port.qty)
        if port.qty > 0:
            side = OrderSide.SELL
        else:
            side = OrderSide.BUY
        fill = apply_slippage(price, side, config.slippage_rate) if apply_slip else _q(price)
        fees = _fees(fill, qty, side, spec.action_settlement_type, spec.ticker)
        # Long: cash += fill*qty - fees; short: cash -= fill*qty + fees (buy to cover)
        if port.qty > 0:
            port.cash = _q(port.cash + fill * qty - fees)
            pnl = _q((fill - port.avg_entry) * qty - fees)
        else:
            port.cash = _q(port.cash - fill * qty - fees)
            pnl = _q((port.avg_entry - fill) * qty - fees)
        port.qty = 0
        port.avg_entry = Decimal("0")
        port.entry_side = None
        sl_price = None
        tp_price = None
        record_fill(ts, side, order_type, reason, fill, qty, fees, pnl)

    def open_position(ts, side: OrderSide, price: Decimal, order_type: str, reason: str) -> bool:
        nonlocal skipped, sl_price, tp_price
        qty = spec.action_quantity
        if qty <= 0:
            return False
        fees = _fees(price, qty, side, spec.action_settlement_type, spec.ticker)
        cost = price * qty + fees
        if side == OrderSide.BUY:
            if port.cash < cost:
                skipped += 1
                return False
            port.cash = _q(port.cash - cost)
            port.qty = qty
        else:
            # Short: receive proceeds minus fees; require cash cushion of fees + 10% notional
            cushion = _q(price * qty * Decimal("0.10") + fees)
            if port.cash < cushion:
                skipped += 1
                return False
            port.cash = _q(port.cash + price * qty - fees)
            port.qty = -qty
        port.avg_entry = price
        port.entry_side = side
        if config.sl_pct and config.sl_pct > 0:
            if side == OrderSide.BUY:
                sl_price = _q(price * (1 - config.sl_pct))
            else:
                sl_price = _q(price * (1 + config.sl_pct))
        else:
            sl_price = None
        if config.tp_pct and config.tp_pct > 0:
            if side == OrderSide.BUY:
                tp_price = _q(price * (1 + config.tp_pct))
            else:
                tp_price = _q(price * (1 - config.tp_pct))
        else:
            tp_price = None
        record_fill(ts, side, order_type, reason, price, qty, fees, None)
        return True

    n = len(clean)
    for i in range(n):
        row = clean.iloc[i]
        ts = clean.index[i]
        o = _q(Decimal(str(row["open"])))
        h = _q(Decimal(str(row["high"])))
        l = _q(Decimal(str(row["low"])))
        c = _q(Decimal(str(row["close"])))
        tradable = in_trade_window(ts)

        if tradable and pending is not None:
            p_side: OrderSide = pending["side"]
            p_type = pending["type"]
            p_reason = pending["reason"]
            p_limit = pending.get("limit")
            fill_price = None
            if p_type == "MARKET":
                fill_price = apply_slippage(o, p_side, config.slippage_rate)
            else:
                fill_price = _limit_fill_price(p_side, p_limit, o, h, l)
            if fill_price is not None:
                if port.is_flat:
                    open_position(ts, p_side, fill_price, p_type, p_reason)
                pending = None
            elif p_type == "MARKET":
                pending = None
            # LIMIT remains pending until filled or trade window ends

        if tradable and not port.is_flat:
            long = port.qty > 0
            pos_side = OrderSide.BUY if long else OrderSide.SELL
            sl_triggered = sl_price is not None and _sl_hit(pos_side, sl_price, h, l)
            tp_triggered = tp_price is not None and _tp_hit(pos_side, tp_price, h, l)
            if sl_triggered:
                # Gap through stop: fill at open if open already beyond stop, else at stop with slippage
                if long:
                    raw = o if o <= sl_price else sl_price
                else:
                    raw = o if o >= sl_price else sl_price
                close_position(ts, raw, "SL", "STOP_LOSS", apply_slip=True)
            elif tp_triggered:
                raw = tp_price if tp_price is not None else c
                close_position(ts, raw, "TP", "TAKE_PROFIT", apply_slip=False)

        if tradable and i >= required - 1 and spec.root_condition:
            hist = clean.iloc[: i + 1]
            try:
                signal = evaluate_condition_tree(hist, spec.root_condition, {})
            except Exception:
                signal = False
            if signal and port.is_flat and pending is None:
                pending = {
                    "side": spec.action_side,
                    "type": spec.action_order_type.value,
                    "reason": "SIGNAL",
                    "limit": spec.action_limit_price,
                }
            elif signal and not port.is_flat:
                # Opposite action closes: BUY strategy in a short, or SELL strategy in a long
                want_long = spec.action_side == OrderSide.BUY
                if want_long and port.qty < 0:
                    pending = {"side": OrderSide.BUY, "type": "MARKET", "reason": "SIGNAL_COVER", "limit": None}
                elif (not want_long) and port.qty > 0:
                    pending = {"side": OrderSide.SELL, "type": "MARKET", "reason": "SIGNAL_EXIT", "limit": None}

        if tradable:
            equity_pts.append((ts, float(port.mark(c))))

    if config.flatten_at_end and not port.is_flat:
        last_ts = clean.index[-1]
        last_c = _q(Decimal(str(clean.iloc[-1]["close"])))
        close_position(last_ts, last_c, "MARKET", "END_FLATTEN", apply_slip=True)
        if equity_pts:
            equity_pts[-1] = (equity_pts[-1][0], float(port.cash))
        else:
            equity_pts.append((last_ts, float(port.cash)))

    if not equity_pts:
        equity_pts.append((clean.index[-1], float(port.mark(_q(Decimal(str(clean.iloc[-1]["close"])))))))

    equity = pd.Series(
        [v for _, v in equity_pts],
        index=pd.DatetimeIndex([t for t, _ in equity_pts], name="timestamp"),
    )
    return SimulationResult(
        equity=equity,
        trades=trades,
        final_cash=port.cash,
        final_position=port.qty,
        skipped_insufficient_cash=skipped,
        notes=notes,
    )


def _daily_equity(equity: pd.Series) -> pd.Series:
    if equity.empty:
        return equity
    s = equity.copy()
    if s.index.tz is None:
        s.index = s.index.tz_localize("UTC")
    daily = s.resample("1D").last().dropna()
    return daily if len(daily) >= 2 else s


def compute_metrics(
    equity_series: pd.Series,
    trades: list[FillRecord],
    initial_capital: float,
    risk_free_annual: float = RISK_FREE_ANNUAL,
) -> dict:
    """
    Performance metrics from the marked equity curve and the trade ledger.

    Win rate and profit factor use completed round-trips (fills with pnl),
    not the fraction of up-days. Sharpe uses daily returns vs cash RF.
    """
    empty = {
        "cagr": 0.0,
        "sharpe": 0.0,
        "sortino": 0.0,
        "calmar": 0.0,
        "max_drawdown": 0.0,
        "volatility": 0.0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "total_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "avg_trade_pnl": 0.0,
        "expectancy": 0.0,
        "total_pnl": 0.0,
        "final_equity": float(initial_capital),
        "total_fees": 0.0,
    }

    equity = equity_series.dropna() if equity_series is not None else pd.Series(dtype=float)
    closed = [t for t in trades if t.pnl is not None]
    empty["total_trades"] = len(closed)
    empty["total_fees"] = _finite(sum(t.fees for t in trades))
    if equity.empty or len(equity) < 2:
        if len(equity) == 1:
            empty["final_equity"] = _finite(equity.iloc[-1], initial_capital)
            empty["total_pnl"] = _finite(empty["final_equity"] - initial_capital)
        return empty

    start_eq = float(equity.iloc[0])
    end_eq = float(equity.iloc[-1])
    if not math.isfinite(start_eq) or start_eq <= 0:
        start_eq = float(initial_capital) if initial_capital > 0 else 1.0
    if not math.isfinite(end_eq):
        end_eq = start_eq

    span = equity.index[-1] - equity.index[0]
    total_days = max(span.total_seconds() / 86400.0, 1 / 365.25)
    total_years = max(total_days / 365.25, 1 / 365.25)
    cagr = (end_eq / start_eq) ** (1 / total_years) - 1
    cagr = _finite(cagr)

    daily = _daily_equity(equity)
    rets = daily.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    vol = 0.0
    sharpe = 0.0
    sortino = 0.0
    if len(rets) > 1 and float(rets.std()) > 0:
        excess = rets - (risk_free_annual / TRADING_DAYS)
        std = float(rets.std())
        vol = _finite(std * math.sqrt(TRADING_DAYS))
        sharpe = _finite(float(excess.mean()) / float(excess.std()) * math.sqrt(TRADING_DAYS)) if float(excess.std()) > 0 else 0.0
        downside = rets[rets < 0]
        dstd = float(downside.std()) if len(downside) > 1 else 0.0
        if dstd > 0:
            sortino = _finite(float(excess.mean()) / dstd * math.sqrt(TRADING_DAYS))

    cummax = equity.cummax().replace(0, np.nan)
    dd = (equity - cummax) / cummax
    max_dd = _finite(float(dd.min()) if len(dd) else 0.0)
    calmar = _finite(cagr / abs(max_dd)) if max_dd < 0 else 0.0

    wins = [t.pnl for t in closed if t.pnl is not None and t.pnl > 0]
    losses = [t.pnl for t in closed if t.pnl is not None and t.pnl < 0]
    n_closed = len(closed)
    win_rate = (len(wins) / n_closed) if n_closed else 0.0
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    if gross_loss == 0:
        pf = PROFIT_FACTOR_CAP if gross_profit > 0 else 0.0
    else:
        pf = min(gross_profit / gross_loss, PROFIT_FACTOR_CAP)
    pnls = [t.pnl for t in closed if t.pnl is not None]
    avg = (sum(pnls) / len(pnls)) if pnls else 0.0

    return {
        "cagr": cagr,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": max_dd,
        "volatility": vol,
        "win_rate": _finite(win_rate),
        "profit_factor": _finite(pf),
        "total_trades": n_closed,
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "avg_trade_pnl": _finite(avg),
        "expectancy": _finite(avg),
        "total_pnl": _finite(end_eq - float(initial_capital)),
        "final_equity": _finite(end_eq),
        "total_fees": _finite(sum(t.fees for t in trades)),
    }


def equity_to_json(equity: pd.Series) -> dict:
    if equity is None or equity.empty:
        return {"dates": [], "values": []}
    dates = []
    values = []
    for ts, v in equity.items():
        t = pd.Timestamp(ts)
        if t.tzinfo is None:
            t = t.tz_localize("UTC")
        t = t.tz_convert("Asia/Kolkata")
        dates.append(t.strftime("%Y-%m-%d"))
        values.append(round(_finite(v), 2))
    return {"dates": dates, "values": values}


def collect_numeric_constants(node: dict | None, path: list | None = None) -> list[list]:
    """Paths to float `right` leaves in a condition tree (for IS grid search)."""
    if not isinstance(node, dict):
        return []
    path = path or []
    found: list[list] = []
    if node.get("type") == "condition":
        right = node.get("right")
        if isinstance(right, (int, float)) and not isinstance(right, bool):
            found.append(path + ["right"])
        return found
    if node.get("type") == "group":
        for i, child in enumerate(node.get("conditions") or []):
            found.extend(collect_numeric_constants(child, path + ["conditions", i]))
    return found


def set_path(tree: dict, path: list, value: float) -> dict:
    out = deepcopy(tree)
    cur: Any = out
    for key in path[:-1]:
        cur = cur[key]
    cur[path[-1]] = value
    return out


def get_path(tree: dict, path: list) -> float:
    cur: Any = tree
    for key in path:
        cur = cur[key]
    return float(cur)


def candidate_values(original: float) -> list[float]:
    if 0 < original <= 100:
        raw = [max(1.0, original - 5), original, min(99.0, original + 5)]
    else:
        raw = [original * 0.85, original, original * 1.15]
    uniq: list[float] = []
    for v in raw:
        if v != 0 and all(abs(v - u) > 1e-9 for u in uniq):
            uniq.append(float(v))
    return uniq


def parameter_grid(tree: dict | None, max_params: int = 2) -> list[dict]:
    """Small IS-only grid around numeric thresholds. Original tree is always included."""
    if not tree:
        return []
    paths = collect_numeric_constants(tree)[:max_params]
    grids = [deepcopy(tree)]
    if not paths:
        return grids
    from itertools import product

    options = [candidate_values(get_path(tree, p)) for p in paths]
    for combo in product(*options):
        mutated = deepcopy(tree)
        for p, val in zip(paths, combo):
            mutated = set_path(mutated, p, val)
        grids.append(mutated)
    # de-dupe
    seen = set()
    unique = []
    for g in grids:
        key = repr(g)
        if key not in seen:
            seen.add(key)
            unique.append(g)
    return unique[:12]
