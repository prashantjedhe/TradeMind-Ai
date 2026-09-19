"""
Backtesting + Walk-Forward engine (float-only, no Decimal).

Standard backtest: replay a strategy against OHLCV bars with
slippage + fee model, compute CAGR, Sharpe, max drawdown, win rate.

Walk-forward: rolling 3yr train / 1yr test windows.
Efficiency Ratio = OOS Sharpe ÷ IS Sharpe.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from types import SimpleNamespace
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.backtest_copy_league import (
    BacktestResult, BacktestStatus,
)
from app.models.strategy import Strategy, StrategyStatus
from app.models.user import User
from app.models.order import OrderSide, SettlementType
from app.models.ohlcv import OHLCVBar, BarInterval
from app.services.strategy_service import evaluate_condition_tree, required_bars_for_tree
from app.utils.indicators import compute_indicator

logger = logging.getLogger(__name__)

WFO_TRAIN_YEARS = 3
WFO_TEST_YEARS = 1
WFO_STEP_MONTHS = 1
INITIAL_CAPITAL = 1000000.0
SLIPPAGE_RATE = 0.0005
BROKERAGE_RATE = 0.001
STT_RATE = 0.001


def compute_metrics(equity_series: pd.Series, risk_free_annual: float = 0.06) -> dict:
    import math
    equity = equity_series.dropna()
    if len(equity) < 2:
        return {
            "cagr": 0, "sharpe": 0, "max_drawdown": 0,
            "win_rate": 0, "total_trades": 0, "total_pnl": 0,
            "final_equity": float(equity.iloc[-1]) if len(equity) else INITIAL_CAPITAL,
        }

    total_days = (equity.index[-1] - equity.index[0]).days
    total_years = max(total_days / 365.25, 1 / 365.25)
    cagr = (float(equity.iloc[-1]) / float(equity.iloc[0])) ** (1 / total_years) - 1
    if not math.isfinite(cagr):
        cagr = 0

    daily_returns = equity.pct_change().dropna()
    if len(daily_returns) == 0 or daily_returns.std() == 0:
        return {"cagr": cagr, "sharpe": 0, "max_drawdown": 0,
                "win_rate": 0, "total_trades": len(daily_returns),
                "total_pnl": 0, "final_equity": float(equity.iloc[-1])}

    excess_returns = daily_returns - (risk_free_annual / 252)
    sharpe = float(excess_returns.mean() / excess_returns.std() * np.sqrt(252)) if excess_returns.std() > 0 else 0
    if not math.isfinite(sharpe):
        sharpe = 0

    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    max_drawdown = float(drawdown.min())
    if not math.isfinite(max_drawdown):
        max_drawdown = 0

    wins = float((daily_returns > 0).sum())
    total = float(len(daily_returns))
    win_rate = wins / total if total > 0 else 0

    total_pnl = float(equity.iloc[-1]) - float(equity.iloc[0])
    final_equity = float(equity.iloc[-1])
    if not math.isfinite(total_pnl):
        total_pnl = 0

    return {
        "cagr": cagr, "sharpe": sharpe, "max_drawdown": max_drawdown,
        "win_rate": win_rate, "total_trades": len(daily_returns),
        "total_pnl": total_pnl, "final_equity": final_equity,
    }


async def run_backtest(
    db: AsyncSession,
    user: User,
    strategy_id: str | None,
    ticker: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
    initial_capital: float = INITIAL_CAPITAL,
    strategy_config: dict | None = None,
) -> BacktestResult:
    interval = BarInterval(str(timeframe) if timeframe in ("1d", "15m") else "1d")
    limit = max(int((end_date - start_date).days * 1.5), 300)
    df = await load_backtest_df(db, ticker, interval, start_date, end_date, limit)

    if df.empty:
        return _create_empty_result(db, user, strategy_id, ticker, timeframe, start_date, end_date)

    strategy = None
    if strategy_id:
        result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
        strategy = result.scalar_one_or_none()
    if strategy is None and strategy_config:
        action = strategy_config.get("action") or {}
        strategy = SimpleNamespace(
            root_condition=strategy_config.get("root_condition"),
            action_side=OrderSide(action.get("side", OrderSide.BUY)),
            action_order_type=action.get("order_type", "MARKET"),
            action_quantity=int(action.get("quantity", 1)),
            action_settlement_type=SettlementType(action.get("settlement_type", SettlementType.INTRADAY)),
            action_limit_price=action.get("limit_price"),
        )

    equity_curve, trades = _simulate_strategy(df, strategy, initial_capital)
    metrics = compute_metrics(equity_curve)
    metrics["total_trades"] = len(trades)

    result = BacktestResult(
        user_id=user.id, strategy_id=strategy_id,
        ticker=ticker, timeframe=timeframe,
        start_date=start_date, end_date=end_date,
        status=BacktestStatus.COMPLETE,
        cagr=metrics["cagr"], sharpe=metrics["sharpe"],
        max_drawdown=metrics["max_drawdown"],
        win_rate=metrics["win_rate"],
        total_trades=metrics["total_trades"],
        total_pnl=metrics["total_pnl"],
        final_equity=metrics["final_equity"],
        initial_capital=initial_capital,
        equity_curve=_equity_to_json(equity_curve),
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    logger.info("Backtest complete: %s ticker=%s sharpe=%.2f", result.id, ticker, result.sharpe)
    return result


async def load_backtest_df(
    db: AsyncSession, ticker: str, interval: BarInterval,
    start_date: datetime, end_date: datetime, limit: int = 1000,
) -> pd.DataFrame:
    from app.services.ohlcv_service import load_bars_range
    return await load_bars_range(db, ticker, interval, start=start_date, end=end_date)


def _simulate_strategy(
    df: pd.DataFrame,
    strategy: Strategy | None,
    initial_capital: float,
) -> tuple[pd.Series, list[dict]]:
    cash = initial_capital
    position_qty = 0
    entry_price = 0.0
    equity_series = []
    trades = []

    required = required_bars_for_tree(strategy.root_condition) if strategy and strategy.root_condition else 30

    for i in range(required, len(df)):
        row = df.iloc[i]
        price = float(row["close"])

        if strategy is not None and strategy.root_condition:
            try:
                bar_df = df.iloc[: i + 1]
                signal = evaluate_condition_tree(bar_df, strategy.root_condition, {})
            except Exception:
                continue
        else:
            signal = i == required

        if signal and position_qty == 0:
            side = strategy.action_side if strategy else OrderSide.BUY
            slippage_price = price * (1 + SLIPPAGE_RATE) if side == OrderSide.BUY else price * (1 - SLIPPAGE_RATE)
            qty = strategy.action_quantity if strategy else 1
            fees = slippage_price * qty * (BROKERAGE_RATE + STT_RATE)
            cost = slippage_price * qty + fees
            if cash >= cost:
                position_qty = qty
                entry_price = slippage_price
                cash -= cost
                trades.append({"date": df.index[i], "side": "BUY", "price": slippage_price, "qty": qty, "fees": fees})

        elif signal and position_qty > 0 and (strategy is None or strategy.action_side == OrderSide.SELL):
            slippage_price = price * (1 - SLIPPAGE_RATE)
            qty = position_qty
            fees = slippage_price * qty * (BROKERAGE_RATE + STT_RATE)
            proceeds = slippage_price * qty - fees
            pnl = proceeds - (entry_price * qty + sum(t["fees"] for t in trades[-1:] if t["side"] == "BUY"))
            cash += proceeds
            equity = cash
            trades.append({"date": df.index[i], "side": "SELL", "price": slippage_price, "qty": qty, "fees": fees, "pnl": pnl})
            position_qty = 0
            entry_price = 0.0

        equity = cash + position_qty * price
        equity_series.append({"date": df.index[i], "equity": equity})

    if not equity_series:
        equity_series.append({"date": df.index[-1], "equity": initial_capital})

    equity_s = pd.Series(
        [e["equity"] for e in equity_series],
        index=pd.DatetimeIndex([e["date"] for e in equity_series], name="timestamp"),
    )
    return equity_s, trades


def _equity_to_json(equity: pd.Series) -> dict:
    import math
    return {
        "dates": [d.strftime("%Y-%m-%d") for d in equity.index],
        "values": [round(float(v), 2) if math.isfinite(float(v)) else 0.0 for v in equity.values],
    }


def _create_empty_result(
    db: AsyncSession, user: User, strategy_id, ticker, timeframe, start_date, end_date
) -> BacktestResult:
    result = BacktestResult(
        user_id=user.id, strategy_id=strategy_id, ticker=ticker,
        timeframe=timeframe, start_date=start_date, end_date=end_date,
        status=BacktestStatus.FAILED,
    )
    db.add(result)
    return result


async def run_walk_forward(
    db: AsyncSession,
    user: User,
    strategy_id: str | None,
    ticker: str,
    timeframe: str,
    start_date: datetime,
    end_date: datetime,
) -> BacktestResult:
    interval = BarInterval(str(timeframe) if timeframe in ("1d", "15m") else "1d")
    limit = max(int((end_date - start_date).days * 1.5), 1200)
    df = await load_backtest_df(db, ticker, interval, start_date, end_date, limit)

    if df.empty:
        return _create_empty_result(db, user, strategy_id, ticker, timeframe, start_date, end_date)

    strategy = None
    if strategy_id:
        result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
        strategy = result.scalar_one_or_none()

    windows = []
    current = start_date
    train_months = WFO_TRAIN_YEARS * 12
    test_months = WFO_TEST_YEARS * 12
    step = WFO_STEP_MONTHS
    min_bars = max(required_bars_for_tree(strategy.root_condition) if strategy and strategy.root_condition else 30, 30)

    while current + timedelta(days=365) <= end_date:
        train_end = current + timedelta(days=train_months * 30)
        test_start = train_end
        test_end = test_start + timedelta(days=test_months * 30)
        if test_end > end_date:
            test_end = end_date

        train_df = df[(df.index >= current) & (df.index <= train_end)]
        test_df = df[(df.index > train_end) & (df.index <= test_end)]

        if len(train_df) < min_bars or len(test_df) < 30:
            current += timedelta(days=step * 30)
            continue

        is_equity, _ = _simulate_strategy(train_df, strategy, INITIAL_CAPITAL)
        is_metrics = compute_metrics(is_equity)

        oos_equity, _ = _simulate_strategy(test_df, strategy, float(is_equity.iloc[-1]) if len(is_equity) else INITIAL_CAPITAL)
        oos_metrics = compute_metrics(oos_equity)

        eff_ratio = (oos_metrics["sharpe"] / is_metrics["sharpe"]) if is_metrics["sharpe"] != 0 and not math.isnan(is_metrics["sharpe"]) else 0

        _finite = lambda v: float(v) if math.isfinite(float(v)) else 0.0

        windows.append({
            "train_start": current.strftime("%Y-%m-%d"),
            "train_end": train_end.strftime("%Y-%m-%d"),
            "test_start": test_start.strftime("%Y-%m-%d"),
            "test_end": test_end.strftime("%Y-%m-%d"),
            "is_sharpe": _finite(is_metrics["sharpe"]),
            "oos_sharpe": _finite(oos_metrics["sharpe"]),
            "is_cagr": _finite(is_metrics["cagr"]),
            "oos_cagr": _finite(oos_metrics["cagr"]),
            "is_drawdown": _finite(is_metrics["max_drawdown"]),
            "oos_drawdown": _finite(oos_metrics["max_drawdown"]),
            "is_trades": int(is_metrics["total_trades"]),
            "oos_trades": int(oos_metrics["total_trades"]),
            "efficiency_ratio": _finite(eff_ratio),
            "is_final_equity": _finite(is_equity.iloc[-1]) if len(is_equity) else INITIAL_CAPITAL,
            "oos_final_equity": _finite(oos_equity.iloc[-1]) if len(oos_equity) else INITIAL_CAPITAL,
        })

        current += timedelta(days=step * 30)

    avg_is_sharpe = float(np.mean([w["is_sharpe"] for w in windows])) if windows else 0
    avg_oos_sharpe = float(np.mean([w["oos_sharpe"] for w in windows])) if windows else 0
    avg_eff = (avg_oos_sharpe / avg_is_sharpe) if avg_is_sharpe != 0 else 0
    if not math.isfinite(avg_is_sharpe): avg_is_sharpe = 0
    if not math.isfinite(avg_oos_sharpe): avg_oos_sharpe = 0
    if not math.isfinite(avg_eff): avg_eff = 0
    last_window = windows[-1] if windows else {}
    total_trades = sum(w["oos_trades"] for w in windows)
    total_pnl = sum(w["oos_final_equity"] - w["is_final_equity"] for w in windows)
    if not math.isfinite(total_pnl): total_pnl = 0

    def _finite(v):
        return float(v) if math.isfinite(float(v)) else 0.0

    result = BacktestResult(
        user_id=user.id, strategy_id=strategy_id,
        ticker=ticker, timeframe=timeframe,
        start_date=start_date, end_date=end_date,
        status=BacktestStatus.COMPLETE,
        cagr=_finite(last_window.get("oos_cagr", 0)),
        sharpe=avg_oos_sharpe,
        max_drawdown=_finite(last_window.get("oos_drawdown", 0)),
        win_rate=0,
        total_trades=total_trades,
        total_pnl=total_pnl,
        final_equity=_finite(last_window.get("oos_final_equity", INITIAL_CAPITAL)),
        initial_capital=INITIAL_CAPITAL,
        is_sharpe=avg_is_sharpe,
        oos_sharpe=avg_oos_sharpe,
        efficiency_ratio=avg_eff,
        num_windows=len(windows),
        window_results=windows if windows else None,
        equity_curve=_equity_to_json(_build_wfo_curve(windows)),
    )
    db.add(result)
    await db.commit()
    await db.refresh(result)
    logger.info("Walk-forward complete: %s ticker=%s ER=%.2f windows=%d", result.id, ticker, result.efficiency_ratio, len(windows))
    return result


def _build_wfo_curve(windows: list[dict]) -> pd.Series:
    import math
    if not windows:
        return pd.Series([INITIAL_CAPITAL], index=[datetime.now()])
    dates = []
    values = []
    for w in windows:
        dates.append(datetime.strptime(w["test_end"], "%Y-%m-%d"))
        v = w["oos_final_equity"]
        values.append(v if math.isfinite(v) else INITIAL_CAPITAL)
    return pd.Series(values, index=pd.DatetimeIndex(dates, name="timestamp"))