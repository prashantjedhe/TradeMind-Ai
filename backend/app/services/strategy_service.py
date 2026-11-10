"""
Strategy service: CRUD + condition-tree evaluation for the
Phase 3 Visual Strategy Builder.

A strategy's `root_condition` is a JSONB AND/OR tree of condition
nodes (see app/schemas/strategy.py). This module owns:

1. CRUD: create / list / get / update / delete strategies.
2. Evaluation: evaluate_condition_tree() walks that tree against a
   pandas OHLCV DataFrame and returns True/False for the LATEST bar
   (plus edge-trigger info for crosses operators).
3. Proposal generation: when a root condition is satisfied,
   fire_action() creates an expiring paper-order proposal. Only the
   user confirmation endpoint submits that order.

Evaluation semantics:
- Leaves compare an indicator (or raw price/volume) on the latest
  completed bar against either a constant or another indicator value.
- Groups apply AND / OR to their children.
- "crosses_above" / "crosses_below" are edge operators: they compare
  the LAST TWO bars so a strategy only fires on the transition, not on
  every consecutive bar where the condition stays satisfied.
- Warm-up: indicators return NaN until enough bars exist (see
  indicators.min_bars_required). A leaf whose computed value is NaN
  evaluates to False rather than crashing - the evaluator simply
  skips that strategy until it has enough history.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.api.deps import redis_client
from app.models.order import OrderSide, SettlementType
from app.models.news import NewsSignal
from app.models.ohlcv import BarInterval
from app.models.strategy import (
    Strategy,
    StrategyStatus,
    StrategyTimeframe,
    StrategyActionOrderType,
)
from app.models.user import User
from app.schemas.strategy import ActionSchema, StrategyCreate, StrategyUpdate, STRATEGY_PROMPT_LIBRARY
from app.services.price_cache_service import get_price_or_derive
from app.services.fn_o_service import underlying_of
from app.services.news_signal_service import load_sentiment_series, top_headlines
from app.services.trade_proposal_service import create_trade_proposal
from app.services.advisor_market_context import build_market_snapshot
from app.utils.indicators import compute_indicator, min_bars_required

logger = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────────
# CRUD
# ────────────────────────────────────────────────────────────────

def _resolve_prompt_to_condition(prompt: str) -> dict | None:
    """Resolve a strategy prompt to a condition tree + action.
    
    Looks up the prompt in the STRATEGY_PROMPT_LIBRARY. If not found,
    returns None (the caller can decide how to handle unknown prompts).
    """
    entry = STRATEGY_PROMPT_LIBRARY.get(prompt)
    if entry is None:
        return None
    return {
        "root_condition": entry["condition"],
        "action": entry["action"],
    }


def _to_strategy_model(user: User, data: StrategyCreate) -> Strategy:
    settlement_by_product = {
        "MIS": SettlementType.INTRADAY,
        "CNC": SettlementType.DELIVERY,
        "BTST": SettlementType.BTST,
    }
    action = data.action or ActionSchema(
        side=OrderSide.BUY,
        order_type=StrategyActionOrderType.MARKET,
        quantity=1,
        settlement_type=settlement_by_product.get(data.product, SettlementType.INTRADAY),
    )
    strategy = Strategy(
        user_id=user.id,
        name=data.name.strip(),
        ticker=data.ticker.strip().upper(),
        timeframe=StrategyTimeframe(data.timeframe),
        root_condition=data.root_condition.model_dump(mode="json") if data.root_condition else None,
        action_side=OrderSide(action.side),
        action_order_type=StrategyActionOrderType(action.order_type),
        action_quantity=action.quantity,
        action_settlement_type=SettlementType(action.settlement_type),
        action_limit_price=action.limit_price,
        status=StrategyStatus(data.status),
        strategy_type=data.strategy_type,
        reference=data.reference,
        product=data.product,
        order_mode=data.order_mode,
        start_time=data.start_time,
        square_off_time=data.square_off_time,
        trading_days=data.trading_days,
        legs=[leg.model_dump(mode="json") for leg in data.legs] if data.legs else None,
        risk_controls=data.risk_controls.model_dump(mode="json") if data.risk_controls else None,
    )
    # If a prompt was provided and no root_condition, resolve it now.
    if data.prompt and not data.root_condition:
        resolved = _resolve_prompt_to_condition(data.prompt)
        if resolved:
            strategy.root_condition = resolved["root_condition"]
            # We cannot set strategy.action here because Strategy uses flat
            # columns (action_side, action_order_type, etc.). The prompt's
            # action info is stored in the strategy's description for reference.
    return strategy


def _apply_update(strategy: Strategy, data: StrategyUpdate) -> Strategy:
    updates = data.model_dump(exclude_unset=True)

    if "name" in updates:
        strategy.name = updates["name"].strip()
    if "ticker" in updates:
        strategy.ticker = updates["ticker"].strip().upper()
    if "timeframe" in updates:
        strategy.timeframe = StrategyTimeframe(updates["timeframe"])
    if "root_condition" in updates:
        strategy.root_condition = updates["root_condition"].model_dump(mode="json") if updates["root_condition"] else None
    if "prompt" in updates and updates["prompt"] and not updates.get("root_condition"):
        resolved = _resolve_prompt_to_condition(updates["prompt"])
        if resolved:
            strategy.root_condition = resolved["root_condition"]
    
    if "action" in updates:
        action: ActionSchema = updates["action"]
        strategy.action_side = OrderSide(action.side)
        strategy.action_order_type = StrategyActionOrderType(action.order_type)
        strategy.action_quantity = action.quantity
        strategy.action_settlement_type = SettlementType(action.settlement_type)
        strategy.action_limit_price = action.limit_price

    for field in (
        "strategy_type", "reference", "order_mode", "start_time",
        "square_off_time", "trading_days",
    ):
        if field in updates:
            setattr(strategy, field, updates[field])
    if "product" in updates:
        strategy.product = updates["product"]
    if "legs" in updates:
        strategy.legs = [leg.model_dump(mode="json") for leg in updates["legs"]] if updates["legs"] else None
    if "risk_controls" in updates:
        strategy.risk_controls = (
            updates["risk_controls"].model_dump(mode="json")
            if updates["risk_controls"] else None
        )

    if "status" in updates:
        strategy.status = StrategyStatus(updates["status"])

    return strategy


async def create_strategy(db: AsyncSession, user: User, data: StrategyCreate) -> Strategy:
    strategy = _to_strategy_model(user, data)
    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def list_strategies(db: AsyncSession, user: User) -> list[Strategy]:
    result = await db.execute(
        select(Strategy).where(Strategy.user_id == user.id).order_by(Strategy.created_at.desc())
    )
    return list(result.scalars().all())


async def get_strategy(db: AsyncSession, user: User, strategy_id) -> Strategy | None:
    result = await db.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.user_id == user.id)
    )
    return result.scalar_one_or_none()


async def update_strategy(
    db: AsyncSession, user: User, strategy_id, data: StrategyUpdate
) -> Strategy | None:
    strategy = await get_strategy(db, user, strategy_id)
    if strategy is None:
        return None

    _apply_update(strategy, data)
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def set_strategy_status(
    db: AsyncSession, user: User, strategy_id, status: StrategyStatus
) -> Strategy | None:
    strategy = await get_strategy(db, user, strategy_id)
    if strategy is None:
        return None

    strategy.status = status
    if status == StrategyStatus.ACTIVE:
        # Manual re-activation clears the news-pause audit trail: the
        # user takes responsibility. (Engine resume clears these too.)
        strategy.paused_reason = None
        strategy.news_event_id = None
        await redis_client.set(f"strategy_state:{strategy.id}", "0")
    await db.commit()
    await db.refresh(strategy)
    return strategy


async def delete_strategy(db: AsyncSession, user: User, strategy_id) -> bool:
    strategy = await get_strategy(db, user, strategy_id)
    if strategy is None:
        return False

    await db.delete(strategy)
    await db.commit()
    return True


# ────────────────────────────────────────────────────────────────
# Condition-tree evaluation
# ────────────────────────────────────────────────────────────────

# SENTIMENT window aliases -> minutes. Must stay in sync with
# settings.NEWS_WINDOWS_MINUTES (unknown windows load as empty).
_SENT_WINDOW_ALIASES = {"15m": 15, "1h": 60, "1d": 1440, "24h": 1440}


def _sent_window_metric(params: dict) -> tuple[int, str]:
    """Parse SENTIMENT params -> (window_minutes, metric)."""
    params = params or {}
    window = params.get("window", params.get("window_minutes", "1h"))
    if isinstance(window, int):
        window_minutes = window
    else:
        window_minutes = _SENT_WINDOW_ALIASES.get(str(window).strip().lower(), 60)
    metric = str(params.get("metric", "score")).strip().lower()
    if metric not in ("score", "zscore", "count"):
        metric = "score"
    return window_minutes, metric


def _tree_uses_sentiment(node: dict) -> bool:
    """True if any leaf in the tree references the SENTIMENT indicator."""
    node_type = node.get("type") if isinstance(node, dict) else None
    if node_type == "condition":
        left = node.get("left") or {}
        right = node.get("right")
        if isinstance(left, dict) and left.get("indicator") == "SENTIMENT":
            return True
        return isinstance(right, dict) and right.get("indicator") == "SENTIMENT"
    if node_type == "group":
        return any(_tree_uses_sentiment(c) for c in node.get("conditions", []))
    return False


def _sentiment_specs(node: dict) -> set[tuple[int, str]]:
    """Unique (window_minutes, metric) pairs a tree needs preloaded."""
    specs: set[tuple[int, str]] = set()

    def walk(n: dict) -> None:
        node_type = n.get("type") if isinstance(n, dict) else None
        if node_type == "condition":
            for side in (n.get("left"), n.get("right")):
                if isinstance(side, dict) and side.get("indicator") == "SENTIMENT":
                    specs.add(_sent_window_metric(side.get("params") or {}))
        elif node_type == "group":
            for c in n.get("conditions", []):
                walk(c)

    if isinstance(node, dict):
        walk(node)
    return specs


def _indicator_series(
    df: pd.DataFrame, ref: dict, sent_ctx: dict | None = None
) -> pd.Series:
    """
    Compute the indicator series for an IndicatorRef dict. SENTIMENT
    leaves resolve from the preloaded signal context (keyed by
    (window_minutes, metric)); everything else computes from OHLCV.
    """
    indicator = ref["indicator"]
    params = ref.get("params") or {}
    if indicator == "SENTIMENT":
        key = _sent_window_metric(params)
        if sent_ctx and key in sent_ctx:
            return sent_ctx[key]
        return pd.Series(dtype=float)
    return compute_indicator(df, indicator, params)


def _latest_value(series: pd.Series) -> float | None:
    """Latest non-NaN value of a series, or None if not enough history."""
    valid = series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


def _two_latest_values(series: pd.Series) -> tuple[float | None, float | None]:
    """(prev, latest) non-NaN values for edge operators, or (None, None)."""
    valid = series.dropna()
    if len(valid) < 2:
        prev = valid.iloc[-1] if len(valid) == 1 else None
        return (float(prev) if prev is not None else None, float(valid.iloc[-1]) if len(valid) >= 1 else None)
    return (float(valid.iloc[-2]), float(valid.iloc[-1]))


def _resolve_leaf_value(
    df: pd.DataFrame, value: float | dict, edge: bool = False,
    sent_ctx: dict | None = None,
) -> float | tuple[float | None, float | None] | None:
    """
    Resolve the right-hand operand of a condition: a constant float, or
    an IndicatorRef whose value (or two-bar edge window) we evaluate.
    """
    if isinstance(value, dict):
        series = _indicator_series(df, value, sent_ctx)
        if edge:
            return _two_latest_values(series)
        return _latest_value(series)
    return float(value)


def _compare(op: str, left, right) -> bool:
    if left is None or right is None:
        return False
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == "==":
        return math.isclose(left, right, rel_tol=1e-6)
    return False


def _cross(op: str, left_prev, left_now, right_prev, right_now) -> bool:
    """Edge operators compare the two most recent bars."""
    if None in (left_prev, left_now, right_prev, right_now):
        return False
    if op == "crosses_above":
        return left_prev <= right_prev and left_now > right_now
    if op == "crosses_below":
        return left_prev >= right_prev and left_now < right_now
    return False


def evaluate_leaf(df: pd.DataFrame, leaf: dict, sent_ctx: dict | None = None) -> bool:
    """Evaluate a single ConditionLeaf node."""
    left_ref = leaf["left"]
    operator = leaf["operator"]
    right_ref = leaf["right"]

    left_series = _indicator_series(df, left_ref, sent_ctx)

    if operator in ("crosses_above", "crosses_below"):
        left_prev, left_now = _two_latest_values(left_series)
        right = _resolve_leaf_value(df, right_ref, edge=True, sent_ctx=sent_ctx)
        if isinstance(right, tuple):
            right_prev, right_now = right
            return _cross(operator, left_prev, left_now, right_prev, right_now)
        return False

    left_now = _latest_value(left_series)
    right_now = _resolve_leaf_value(df, right_ref, edge=False, sent_ctx=sent_ctx)
    return _compare(operator, left_now, right_now)


def evaluate_condition_tree(
    df: pd.DataFrame, node: dict, sent_ctx: dict | None = None
) -> bool:
    """Recursively evaluate a ConditionGroup / ConditionLeaf tree."""
    node_type = node.get("type")

    if node_type == "condition":
        return evaluate_leaf(df, node, sent_ctx)

    if node_type == "group":
        logic = node.get("logic", "AND")
        children = node.get("conditions", [])

        if logic == "OR":
            return any(evaluate_condition_tree(df, child, sent_ctx) for child in children)
        return all(evaluate_condition_tree(df, child, sent_ctx) for child in children)

    logger.warning("Unknown condition node type: %r", node_type)
    return False


def required_bars_for_tree(node: dict) -> int:
    """Max bars any indicator in the tree needs to warm up."""
    if node.get("type") == "condition":
        left = node["left"]
        required = min_bars_required(left["indicator"], left.get("params") or {})
        right = node.get("right")
        if isinstance(right, dict):
            required = max(required, min_bars_required(right["indicator"], right.get("params") or {}))
        # +1 so crosses_above/below can compare two non-NaN bars.
        return required + 1

    if node.get("type") == "group":
        return max((required_bars_for_tree(child) for child in node.get("conditions", [])), default=1)

    return 1


# ────────────────────────────────────────────────────────────────
# Strategy evaluation + action firing
# ────────────────────────────────────────────────────────────────

async def evaluate_strategy(db: AsyncSession, strategy: Strategy) -> bool:
    """
    Load OHLCV bars for the strategy's ticker/timeframe and evaluate
    its root condition against the LATEST bar. Returns False when the
    tree needs more warm-up history than we have stored.

    F&O contracts have no candles of their own, so an F&O strategy
    ticker (e.g. RELIANCE24AUG2800CE) is resolved back to its equity
    underlying (RELIANCE) for OHLCV evaluation - exactly how real
    traders read the underlying chart to trade the option. The order
    still fires on the F&O contract itself (see fire_action).
    """
    if not strategy.root_condition:
        # Multi-leg strategies may be scheduled independently of the
        # classic indicator condition tree.
        return False
    try:
        interval = BarInterval(strategy.timeframe.value)
    except ValueError:
        logger.error("Unsupported timeframe %s on strategy %s", strategy.timeframe, strategy.id)
        return False

    eval_ticker = underlying_of(strategy.ticker)
    required = required_bars_for_tree(strategy.root_condition)
    limit = max(required, 60)
    df = await _load_df(db, eval_ticker, interval, limit)

    if df.empty or len(df) < required:
        logger.info(
            "Strategy %s (%s) needs %d bars, has %d - skipping",
            strategy.id, eval_ticker, required, len(df),
        )
        return False

    # Pure-news or hybrid trees: preload each (window, metric) signal
    # series once. Missing/low-count buckets load as NaN -> leaf False,
    # the same "missing means skip" rule as OHLCV warm-up.
    sent_ctx: dict = {}
    if _tree_uses_sentiment(strategy.root_condition):
        for window_minutes, metric in _sentiment_specs(strategy.root_condition):
            try:
                sent_ctx[(window_minutes, metric)] = await load_sentiment_series(
                    db, eval_ticker, window_minutes, metric, limit=200
                )
            except Exception as exc:
                logger.warning("Strategy %s sentiment load failed (%s/%s): %s",
                               strategy.id, window_minutes, metric, exc)

    return evaluate_condition_tree(df, strategy.root_condition, sent_ctx)


async def _load_df(db: AsyncSession, ticker: str, interval: BarInterval, limit: int) -> pd.DataFrame:
    from app.services.ohlcv_service import load_bars_dataframe
    return await load_bars_dataframe(db, ticker, interval, limit=limit)


async def opposing_strategy_context(db: AsyncSession, strategy: Strategy) -> str | None:
    """Return a reason to stop an active strategy when confirmed context opposes it."""
    ticker = underlying_of(strategy.ticker)
    expected = "bullish" if strategy.action_side == OrderSide.BUY else "bearish"
    now = datetime.now(timezone.utc)

    try:
        bars = await _load_df(db, ticker, BarInterval.ONE_DAY, 100)
        if not bars.empty:
            last_bar = pd.Timestamp(bars.index[-1])
            if last_bar.tzinfo is None:
                last_bar = last_bar.tz_localize(timezone.utc)
            if (now - last_bar.to_pydatetime()).total_seconds() <= 7 * 24 * 3600:
                trend = build_market_snapshot(ticker, None, bars)["daily_trend"]
                if trend in ("bullish", "bearish") and trend != expected:
                    return f"MARKET: daily {trend} trend opposes {strategy.action_side.value} strategy"
    except Exception as exc:
        logger.warning("Strategy %s market guard unavailable: %s", strategy.id, exc)

    try:
        signal = (await db.execute(
            select(NewsSignal)
            .where(
                NewsSignal.ticker == ticker,
                NewsSignal.window_minutes == 60,
                NewsSignal.timestamp <= now,
                NewsSignal.timestamp >= now - timedelta(
                    seconds=settings.NEWS_SIGNAL_TTL_SECONDS
                ),
                NewsSignal.article_count >= settings.NEWS_MIN_ARTICLES,
                NewsSignal.band.in_(("MEDIUM", "HIGH")),
            )
            .order_by(NewsSignal.timestamp.desc())
            .limit(1)
        )).scalar_one_or_none()
        if signal is not None:
            impact = float(signal.impact)
            if abs(impact) >= settings.NEWS_MED_THRESHOLD:
                news_direction = "bullish" if impact > 0 else "bearish"
                if news_direction != expected:
                    return (
                        f"NEWS: corroborated {news_direction} impact "
                        f"({impact:+.2f}) opposes {strategy.action_side.value} strategy"
                    )
    except Exception as exc:
        logger.warning("Strategy %s news guard unavailable: %s", strategy.id, exc)
    return None


async def fire_action(db: AsyncSession, strategy: Strategy) -> bool:
    """
    Convert a triggered strategy into an expiring paper-trade proposal.
    No strategy evaluator path submits an order without user confirmation.
    """
    # News risk controls may reduce the proposed size before it is shown.
    try:
        mult = float(strategy.quantity_multiplier or 1.0)
    except (TypeError, ValueError):
        mult = 1.0
    eff_qty = max(1, math.floor(strategy.action_quantity * mult)) \
        if mult != 1.0 else strategy.action_quantity
    if eff_qty != strategy.action_quantity:
        logger.info("Strategy %s lot-size: %s x %.4f -> %s",
                    strategy.id, strategy.action_quantity, mult, eff_qty)

    ticker = strategy.ticker.strip().upper()
    quote = await get_price_or_derive(ticker)
    if quote is None or not quote.is_finite() or quote <= 0:
        logger.warning("Strategy %s setup has no fresh executable quote", strategy.id)
        return False

    limit_price = strategy.action_limit_price
    if strategy.action_order_type.value == "MARKET" or limit_price is None:
        limit_price = quote

    minute_key = datetime.now(timezone.utc).replace(second=0, microsecond=0).isoformat()
    evidence = {
        "strategy_name": strategy.name,
        "timeframe": strategy.timeframe.value,
        "condition": strategy.root_condition,
        "suggested_order_type": strategy.action_order_type.value,
        "reference_quote": str(quote),
    }
    if _tree_uses_sentiment(strategy.root_condition):
        try:
            evidence["headlines"] = await top_headlines(
                db, underlying_of(ticker), 60, limit=3
            )
        except Exception as exc:
            logger.warning("Strategy %s proposal evidence unavailable: %s", strategy.id, exc)

    proposal = await create_trade_proposal(
        db,
        proposal_key=f"strategy:{strategy.id}:{minute_key}",
        user_id=strategy.user_id,
        strategy_id=strategy.id,
        ticker=ticker,
        side=strategy.action_side.value,
        quantity=eff_qty,
        settlement_type=strategy.action_settlement_type.value,
        limit_price=Decimal(str(limit_price)).quantize(Decimal("0.01")),
        rationale=f"{strategy.name} conditions are currently satisfied.",
        evidence=evidence,
    )
    strategy.last_triggered_at = datetime.now(timezone.utc)
    await db.commit()

    logger.info(
        "Strategy %s setup proposed: %s LIMIT %s x%s (proposal %s)",
        strategy.id, strategy.action_side.value, ticker, eff_qty, proposal.id,
    )
    return True