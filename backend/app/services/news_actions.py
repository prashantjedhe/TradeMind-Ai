"""
News Action Engine: turns ticker impact bands into guarded risk signals.

Band semantics (impact = signed; gates use |impact|, direction uses sign):
- HIGH   (|impact| >= NEWS_HIGH_THRESHOLD): pause ticker strategies,
  pause opposing strategies and shrink proposed lot size. Any exit needs user approval.
- MEDIUM (|impact| >= NEWS_MED_THRESHOLD): in-app alert + smaller lot
  reduction. Strategies keep running.
- LOW: log only (the news feed itself).

Safety rails (the parts the naive spec missed):
- Cooldown: each action fires once per (strategy|user+ticker) per
  NEWS_ACTION_COOLDOWN_MIN via Redis NX keys -- a sustained HIGH band
  must not re-pause/re-tighten every 5-minute cycle.
- Ticker scope only in v1: NIFTY HIGH pauses NIFTY strategies, it does
  NOT fan out to equities (documented future work).
- Resume: news-paused strategies (paused_reason LIKE 'NEWS:%') resume
  after NEWS_RESUME_CALM_CYCLES calm cycles OR the 120-minute timeout,
  whichever first; lot multipliers restore on the same timeout.
- News does not create or modify orders without user confirmation.
- All money movement reuses order_service.create_order (slippage +
  fee_calculator + row-locked balance/position) -- no parallel math.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import redis_client
from app.config import settings
from app.models.news import NewsArticle, NewsSentiment
from app.models.order import OrderSide, OrderStatus, OrderType, TriggeredBy
from app.models.order import Order
from app.models.portfolio import Position, PositionStatus
from app.models.strategy import Strategy, StrategyStatus
from app.models.user import User
from app.schemas.order import OrderCreateRequest
from app.services.news_impact import (
    age_minutes,
    article_impact,
    classify_band,
)
from app.services.order_service import create_order as create_order_service

logger = logging.getLogger(__name__)

ACTION_KEY_PREFIX = "news_action:"
CALM_KEY_PREFIX = "news_calm:"
ALERTS_KEY_PREFIX = "news:alerts:"
ALERT_TTL_S = 24 * 3600
ALERT_CAP = 20


async def _cooldown_acquire(key: str, ttl_s: int) -> bool:
    """True if we won the cooldown (NX set); False if action ran recently."""
    try:
        return bool(await redis_client.set(key, "1", ex=ttl_s, nx=True))
    except Exception as exc:
        logger.warning("Cooldown backend unavailable (%s), acting once", exc)
        return True


def _cooldown_s(kind: str, *parts: str) -> int:
    return settings.NEWS_ACTION_COOLDOWN_MIN * 60


async def ticker_impact(db: AsyncSession, ticker: str, now: datetime) -> dict:
    """
    Aggregate signed impact for one ticker from articles younger than
    NEWS_IMPACT_MAX_AGE_MIN. Magnitude-weighted mean (confident stories
    count more) + top evidence article. n gate enforced by callers.
    """
    ticker = ticker.strip().upper()
    cutoff = now - timedelta(minutes=settings.NEWS_IMPACT_MAX_AGE_MIN)
    rows = (await db.execute(
        select(NewsSentiment.score, NewsSentiment.magnitude,
               NewsArticle.published_at, NewsArticle.source,
               NewsArticle.sector, NewsArticle.title, NewsArticle.id)
        .join(NewsArticle, NewsSentiment.article_id == NewsArticle.id)
        .where(NewsSentiment.ticker == ticker,
               NewsArticle.published_at <= now,
               NewsArticle.published_at >= cutoff)
        .order_by(NewsArticle.published_at.desc())
        .limit(500)
    )).all()

    if not rows:
        return {"ticker": ticker, "impact": 0.0, "band": "LOW",
                "article_count": 0, "evidence": None, "components": []}

    weighted = 0.0
    weights = 0.0
    best = None
    for score, magnitude, published, source, sector, title, article_id in rows:
        comp = article_impact(float(score), sector or "UNKNOWN", source or "",
                              age_minutes(published, now))
        w = 0.5 + 0.5 * float(magnitude or 0.0)
        weighted += comp["impact"] * w
        weights += w
        if best is None or abs(comp["impact"]) > abs(best["impact"]):
            best = {**comp, "title": title, "article_id": str(article_id)}
    impact = weighted / weights if weights > 0 else 0.0
    return {"ticker": ticker, "impact": round(impact, 5),
            "band": classify_band(impact), "article_count": len(rows),
            "evidence": best}


async def _push_alert(user_id, ticker: str, band: str, impact: float,
                      evidence: dict | None) -> None:
    try:
        import json
        payload = json.dumps({
            "ticker": ticker, "band": band, "impact": impact,
            "headline": (evidence or {}).get("title", "")[:160],
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        key = f"{ALERTS_KEY_PREFIX}{user_id}"
        async with redis_client.pipeline() as pipe:
            await pipe.lpush(key, payload)
            await pipe.ltrim(key, 0, ALERT_CAP - 1)
            await pipe.expire(key, ALERT_TTL_S)
            await pipe.execute()
    except Exception as exc:
        logger.warning("Alert push failed for %s: %s", ticker, exc)


async def get_alerts(user_id) -> list[dict]:
    import json
    try:
        raw = await redis_client.lrange(f"{ALERTS_KEY_PREFIX}{user_id}", 0, ALERT_CAP - 1)
        out = []
        for item in raw or []:
            try:
                out.append(json.loads(item))
            except (ValueError, TypeError):
                continue
        return out
    except Exception:
        return []


async def _entry_settlement(db: AsyncSession, user_id, ticker: str):
    """Settlement of the user's most recent filled entry order (SLs inherit it)."""
    from app.models.order import SettlementType
    o = (await db.execute(
        select(Order).where(Order.user_id == user_id, Order.ticker == ticker,
                            Order.status == OrderStatus.FILLED)
        .order_by(Order.filled_at.desc(), Order.created_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    if o is not None and getattr(o, "settlement_type", None) is not None:
        return o.settlement_type
    return SettlementType.INTRADAY


async def _pause_strategy(db: AsyncSession, strategy: Strategy,
                          evidence: dict | None) -> bool:
    """HIGH action 1: park the strategy, pinning the evidence headline."""
    key = f"{ACTION_KEY_PREFIX}{strategy.id}:pause"
    if not await _cooldown_acquire(key, _cooldown_s("pause")):
        return False
    headline = ((evidence or {}).get("title") or "high-impact news")[:200]
    strategy.status = StrategyStatus.PAUSED
    strategy.paused_reason = f"NEWS: {headline}"[:255]
    try:
        await redis_client.set(f"strategy_state:{strategy.id}", "0")
    except Exception as exc:
        logger.warning("Could not reset strategy edge state for %s: %s", strategy.id, exc)
    if evidence and evidence.get("article_id"):
        try:
            import uuid as _uuid
            strategy.news_event_id = _uuid.UUID(evidence["article_id"])
        except (ValueError, AttributeError):
            pass
    logger.info("News pause: strategy %s (%s) on HIGH impact",
                strategy.id, strategy.ticker)
    return True


async def _reduce_multiplier(db: AsyncSession, strategy: Strategy,
                             impact: float, high: bool) -> bool:
    """HIGH/MEDIUM action 4: shrink next-order size. Absolute set (idempotent)."""
    key = f"{ACTION_KEY_PREFIX}{strategy.id}:lot"
    if not await _cooldown_acquire(key, _cooldown_s("lot")):
        return False
    scale = 0.6 if high else settings.NEWS_MED_REDUCTION
    new_mult = max(0.1, 1.0 - abs(float(impact)) * scale)
    strategy.quantity_multiplier = new_mult
    strategy.multiplier_set_at = datetime.now(timezone.utc)
    logger.info("News lot-size: strategy %s multiplier -> %.4f",
                strategy.id, new_mult)
    return True


async def _maybe_resume(db: AsyncSession, now: datetime) -> dict:
    """
    Resume news-paused strategies after calm cycles or timeout, and
    restore lot multipliers after their timeout. Returns counts.
    """
    resumed = restored = 0
    calm_needed = settings.NEWS_RESUME_CALM_CYCLES
    timeout = timedelta(minutes=settings.NEWS_MULTIPLIER_RESTORE_MIN)

    paused = (await db.execute(
        select(Strategy).where(Strategy.status == StrategyStatus.PAUSED,
                               Strategy.paused_reason.is_not(None))
    )).scalars().all()
    for s in paused:
        if not str(s.paused_reason or "").startswith("NEWS:"):
            continue  # user-paused: hands off
        try:
            calm = int(await redis_client.get(f"{CALM_KEY_PREFIX}{s.ticker}") or 0)
        except Exception:
            calm = 0
        aged_out = (s.multiplier_set_at is not None
                    and now - s.multiplier_set_at.replace(tzinfo=timezone.utc) > timeout)
        # Fall back to updated_at when the pause predates multiplier timing.
        if s.multiplier_set_at is None:
            updated = (s.updated_at or now).replace(tzinfo=timezone.utc) \
                if getattr(s.updated_at, "tzinfo", None) is None else s.updated_at
            aged_out = now - updated > timeout
        if calm >= calm_needed or aged_out:
            s.status = StrategyStatus.ACTIVE
            s.paused_reason = None
            s.news_event_id = None
            resumed += 1

    stale = (await db.execute(
        select(Strategy).where(Strategy.multiplier_set_at.is_not(None))
    )).scalars().all()
    for s in stale:
        try:
            mult = float(s.quantity_multiplier or 1.0)
        except (TypeError, ValueError):
            continue
        if mult == 1.0:
            s.multiplier_set_at = None
            continue
        set_at = s.multiplier_set_at
        if set_at.tzinfo is None:
            set_at = set_at.replace(tzinfo=timezone.utc)
        if now - set_at > timeout:
            s.quantity_multiplier = 1.0
            s.multiplier_set_at = None
            restored += 1
    if resumed or restored:
        await db.commit()
    return {"resumed": resumed, "multipliers_restored": restored}


async def evaluate_news_actions(db: AsyncSession) -> dict:
    """
    One engine pass over the watchlist (called from the 5-min news
    cycle after snapshots persist). Returns a per-band action summary.
    """
    from app.config import settings as _s
    now = datetime.now(timezone.utc)
    summary: dict = {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "paused": 0,
                     "sl": [], "alerts": 0}

    for ticker in _s.WATCHLIST_TICKERS:
        try:
            agg = await ticker_impact(db, ticker, now)
        except Exception as exc:
            logger.warning("Impact calc failed for %s: %s", ticker, exc)
            continue
        band, impact, n = agg["band"], agg["impact"], agg["article_count"]
        summary[band] = summary.get(band, 0) + 1

        # Calm-cycle accounting drives auto-resume (HIGH resets it).
        try:
            if band == "HIGH":
                await redis_client.set(f"{CALM_KEY_PREFIX}{ticker}", 0,
                                       ex=24 * 3600)
            else:
                await redis_client.incr(f"{CALM_KEY_PREFIX}{ticker}")
                await redis_client.expire(f"{CALM_KEY_PREFIX}{ticker}", 24 * 3600)
        except Exception:
            pass

        if band == "LOW" or n < _s.NEWS_MIN_ARTICLES:
            continue

        strategies = (await db.execute(
            select(Strategy).where(Strategy.ticker == ticker,
                                   Strategy.status == StrategyStatus.ACTIVE)
        )).scalars().all()
        user_ids = {s.user_id for s in strategies}

        if band == "HIGH":
            for s in strategies:
                is_opposed = (
                    (impact < 0 and s.action_side == OrderSide.BUY)
                    or (impact > 0 and s.action_side == OrderSide.SELL)
                )
                if is_opposed and await _pause_strategy(db, s, agg["evidence"]):
                    summary["paused"] += 1
                await _reduce_multiplier(db, s, impact, high=True)
            # News may pause opposing strategies and show a user-confirmed
            # exit proposal; it must not create or modify orders itself.
            await db.commit()
        elif band == "MEDIUM":
            for s in strategies:
                await _reduce_multiplier(db, s, impact, high=False)
            for uid in user_ids:
                await _push_alert(uid, ticker, band, impact, agg["evidence"])
                summary["alerts"] += 1
            await db.commit()

    try:
        summary["resume"] = await _maybe_resume(db, now)
    except Exception as exc:
        logger.warning("News resume pass failed: %s", exc)
    # Calibration log: one structured line per cycle for percentile refits.
    logger.info("News impact distribution: HIGH=%s MEDIUM=%s LOW=%s paused=%s alerts=%s %s",
                summary.get("HIGH", 0), summary.get("MEDIUM", 0),
                summary.get("LOW", 0), summary.get("paused", 0),
                summary.get("alerts", 0), summary.get("resume", {}))
    return summary


async def _exit_open_position(
    db: AsyncSession,
    user: User,
    ticker: str,
    triggered_by: TriggeredBy,
    updated_reason: str,
) -> Order:
    """
    Create a full-quantity MARKET exit through the standard fill path.
    """
    from app.services.order_service import (
        InsufficientBalanceError,
        PriceUnavailableError,
    )
    ticker = ticker.strip().upper()
    pos = (await db.execute(
        select(Position).where(Position.user_id == user.id,
                               Position.ticker == ticker,
                               Position.status == PositionStatus.OPEN)
    )).scalar_one_or_none()
    if pos is None or int(pos.quantity or 0) == 0:
        raise PriceUnavailableError(f"No open position in {ticker}")
    qty = abs(int(pos.quantity))
    side = OrderSide.SELL if int(pos.quantity) > 0 else OrderSide.BUY
    req = OrderCreateRequest(
        ticker=ticker, order_type=OrderType.MARKET, side=side,
        settlement_type=await _entry_settlement(db, user.id, ticker),
        quantity=qty,
    )
    order = await create_order_service(db=db, user=user, request=req,
                                       triggered_by=triggered_by)
    order.updated_reason = updated_reason
    await db.commit()
    await db.refresh(order)
    return order


async def exit_position_on_news(db: AsyncSession, user: User, ticker: str) -> Order:
    """User-triggered full MARKET exit recorded as a news-event action."""
    return await _exit_open_position(
        db, user, ticker, TriggeredBy.NEWS_EVENT, "USER_EXIT_NEWS"
    )


async def exit_position_manually(db: AsyncSession, user: User, ticker: str) -> Order:
    """User-triggered full MARKET exit recorded as a manual action."""
    return await _exit_open_position(
        db, user, ticker, TriggeredBy.USER, "USER_MANUAL_EXIT"
    )
