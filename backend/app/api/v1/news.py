import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.news import NewsArticle, NewsSentiment, NewsSignal
from app.models.order import (
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SettlementType,
    TriggeredBy,
)
from app.models.portfolio import Position, PositionStatus
from app.models.strategy import Strategy
from app.models.trade_journal import TradeJournal
from app.models.user import User
from app.services import advisor as advisor_service
from app.services.news_actions import get_alerts
from app.services.news_signal_service import (
    get_signal,
    top_headlines,
    window_label,
)
from app.services.news_impact import age_minutes, explain_article_impact
from app.services.news_outcomes import get_outcome_summary
from app.services.advisor_market_context import build_market_snapshot
from app.services.market_brief_service import build_market_brief
from app.services.news_trade_proposal import build_trade_proposal
from app.services.ohlcv_service import load_bars_dataframe
from app.services.order_service import create_order as create_order_service
from app.services.price_cache_service import get_cached_price
from app.services.rate_limiter import enforce_rate_limit
from app.schemas.order import OrderCreateRequest, OrderResponse
from app.models.ohlcv import BarInterval

router = APIRouter(prefix="/api/v1/news", tags=["news"])

_WINDOW_ALIASES = {"15m": 15, "1h": 60, "1d": 1440, "24h": 1440}


def _parse_window(window: str | int) -> int:
    if isinstance(window, int):
        return window
    return _WINDOW_ALIASES.get(str(window).strip().lower(), 60)


def _regime(score: float, zscore: float | None, n: int) -> str:
    if n < settings.NEWS_MIN_ARTICLES:
        return "quiet"
    if zscore is not None and abs(zscore) >= 2.0:
        return "spike-bullish" if score > 0 else "spike-bearish"
    if score > 0.2:
        return "bullish"
    if score < -0.2:
        return "bearish"
    return "neutral"


async def _get_market_brief(db: AsyncSession, now: datetime, user_id: uuid.UUID) -> dict:
    cutoff = now - timedelta(minutes=60)
    articles = (await db.execute(
        select(
            NewsArticle.title,
            NewsArticle.published_at,
            NewsArticle.sector,
            NewsArticle.source,
            NewsSentiment.score,
            NewsSentiment.label,
        )
        .join(NewsSentiment, NewsSentiment.article_id == NewsArticle.id)
        .where(NewsArticle.published_at >= cutoff, NewsArticle.published_at <= now)
        .order_by(NewsArticle.published_at.desc())
        .limit(100)
    )).all()
    cached_price, daily_bars = await asyncio.gather(
        get_cached_price("NIFTY"),
        load_bars_dataframe(db, "NIFTY", BarInterval.ONE_DAY, limit=100),
    )
    brief = build_market_brief(
        articles,
        cached_price,
        daily_bars,
        now=now,
        minimum_articles=settings.NEWS_MIN_ARTICLES,
    )
    brief["trade_proposal"] = None
    brief["setup_reason"] = (
        f"Need at least {settings.NEWS_MIN_ARTICLES} corroborating scored headlines "
        "for a ticker-specific signal. A bullish BUY also needs current trend alignment; "
        "a bearish SELL is limited to an existing long holding."
    )
    tickers = [
        ticker for ticker in settings.WATCHLIST_TICKERS
        if ticker not in {"NIFTY", "BANKNIFTY"}
    ]
    signal_rows = (await db.execute(
        select(
            NewsSignal.id,
            NewsSignal.ticker,
            NewsSignal.timestamp,
            NewsSignal.score,
            NewsSignal.impact,
            NewsSignal.band,
            NewsSignal.article_count,
        )
        .where(
            NewsSignal.ticker.in_(tickers),
            NewsSignal.window_minutes == 60,
            NewsSignal.timestamp >= now - timedelta(seconds=settings.NEWS_SIGNAL_TTL_SECONDS),
            NewsSignal.timestamp <= now,
        )
        .order_by(NewsSignal.timestamp.desc())
    )).all()

    latest_by_ticker = {}
    for row in signal_rows:
        latest_by_ticker.setdefault(row.ticker, {
            "id": row.id,
            "ticker": row.ticker,
            "timestamp": row.timestamp,
            "score": row.score,
            "impact": row.impact,
            "band": row.band,
            "article_count": row.article_count,
        })
    candidates = sorted(
        latest_by_ticker.values(),
        key=lambda signal: abs(float(signal["impact"])),
        reverse=True,
    )
    for signal in candidates:
        if (
            signal["band"] not in ("MEDIUM", "HIGH")
            or abs(float(signal["impact"])) < settings.NEWS_MED_THRESHOLD
            or int(signal["article_count"]) < settings.NEWS_MIN_ARTICLES
        ):
            continue
        ticker = signal["ticker"]
        position_result = await db.execute(
            select(func.sum(Position.quantity)).where(
                Position.user_id == user_id,
                Position.ticker == ticker,
                Position.status == PositionStatus.OPEN,
                Position.quantity > 0,
            )
        )
        open_long_quantity = position_result.scalar_one_or_none() or 0
        quote, bars = await asyncio.gather(
            get_cached_price(ticker),
            load_bars_dataframe(db, ticker, BarInterval.ONE_DAY, limit=100),
        )
        proposal = build_trade_proposal(
            signal,
            quote,
            bars,
            brief["market_snapshot"]["daily_trend"],
            brief["sentiment"],
            brief["market_snapshot"]["last_daily_bar_at"],
            open_long_quantity=int(open_long_quantity),
            now=now,
        )
        if proposal is None:
            continue
        pending = (await db.execute(
            select(Order.id).where(
                Order.user_id == user_id,
                Order.ticker == ticker,
                Order.side == OrderSide(proposal["side"]),
                Order.status == OrderStatus.PENDING,
                Order.triggered_by == TriggeredBy.NEWS_EVENT,
                Order.updated_reason.like("NEWS_PROPOSAL:%"),
            ).limit(1)
        )).scalar_one_or_none()
        if pending is None:
            proposal["headlines"] = await top_headlines(db, ticker, 60, limit=3)
            brief["trade_proposal"] = proposal
            break
    if brief["trade_proposal"] is None and brief["market_snapshot"]["daily_trend"] in (
        "bullish",
        "bearish",
    ):
        brief["setup_reason"] = (
            "No proposal: no watchlist ticker currently meets the fresh-news, "
            "minimum-headline, impact, ticker-trend, quote, and position checks. "
            "A positive setup also needs broad news and NIFTY trend alignment; "
            "a bearish setup is shown only to reduce an existing long. "
            "Active strategies continue to be evaluated separately."
        )
    return brief


@router.get("/market-brief")
async def get_market_brief(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """News-led market summary and a conditional paper LIMIT proposal."""
    return await _get_market_brief(db, datetime.now(timezone.utc), current_user.id)


class NewsTradeConfirmationRequest(BaseModel):
    proposal_id: str = Field(min_length=32, max_length=32, pattern=r"^[0-9a-f]{32}$")
    signal_id: uuid.UUID


@router.post(
    "/market-brief/confirm",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def confirm_market_trade(
    payload: NewsTradeConfirmationRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revalidate and submit the exact current news proposal as a paper LIMIT order."""
    await enforce_rate_limit(
        key=f"orders:{current_user.id}",
        max_requests=10,
        window_seconds=60,
    )
    reason = f"NEWS_PROPOSAL:{payload.signal_id}"
    await db.execute(
        select(User).where(User.id == current_user.id).with_for_update()
    )
    existing = (await db.execute(
        select(Order).where(
            Order.user_id == current_user.id,
            Order.updated_reason == reason,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    brief = await _get_market_brief(db, datetime.now(timezone.utc), current_user.id)
    proposal = brief["trade_proposal"]
    if (
        proposal is None
        or proposal["proposal_id"] != payload.proposal_id
        or proposal["signal_id"] != str(payload.signal_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This news setup is no longer current. Refresh the market brief before confirming.",
        )

    pending_news_order = (await db.execute(
        select(Order).where(
            Order.user_id == current_user.id,
            Order.ticker == proposal["ticker"],
            Order.status == OrderStatus.PENDING,
            Order.triggered_by == TriggeredBy.NEWS_EVENT,
            Order.updated_reason.like("NEWS_PROPOSAL:%"),
        ).limit(1)
    )).scalar_one_or_none()
    if pending_news_order is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A news-proposed LIMIT order for {proposal['ticker']} is already pending.",
        )

    order_request = OrderCreateRequest(
        ticker=proposal["ticker"],
        order_type=OrderType.LIMIT,
        side=OrderSide(proposal["side"]),
        settlement_type=SettlementType.INTRADAY,
        quantity=proposal["quantity"],
        limit_price=Decimal(str(proposal["limit_price"])),
    )
    return await create_order_service(
        db=db,
        user=current_user,
        request=order_request,
        triggered_by=TriggeredBy.NEWS_EVENT,
        updated_reason=reason,
    )


@router.get("/latest")
async def get_latest_news(
    ticker: str = Query("ALL", description="Equity ticker or ALL for the Indian market"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Latest scored ticker headlines, or broad market headlines when ticker=ALL."""
    ticker = ticker.strip().upper()
    now = datetime.now(timezone.utc)
    stmt = (
        select(
            NewsArticle.title,
            NewsArticle.url,
            NewsArticle.language,
            NewsArticle.published_at,
            NewsArticle.source,
            NewsArticle.sector,
            NewsArticle.tickers,
            NewsSentiment.score,
            NewsSentiment.label,
            NewsSentiment.magnitude,
            NewsSentiment.spans,
        )
        .join(NewsSentiment, NewsSentiment.article_id == NewsArticle.id)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    )
    if ticker != "ALL":
        stmt = stmt.where(NewsSentiment.ticker == ticker)
    rows = (await db.execute(stmt)).all()
    articles = []
    for (
        title, url, language, published_at, source, sector, tickers,
        score, label, magnitude, spans,
    ) in rows:
        polarity = float(score) if score is not None else 0.0
        impact = explain_article_impact(
            polarity,
            sector or "UNKNOWN",
            source or "",
            age_minutes(published_at, now),
            label or "NEU",
        )
        sentiment_evidence = spans if isinstance(spans, dict) else {}
        articles.append({
            "title": title,
            "url": url,
            "language": language,
            "published_at": published_at.isoformat() if published_at else None,
            "source": source,
            "sector": sector or "UNKNOWN",
            "tickers": list(tickers or []),
            "ticker": ticker if ticker != "ALL" else (list(tickers or [])[0] if tickers else None),
            "score": polarity,
            "label": label,
            "magnitude": float(magnitude) if magnitude is not None else 0.0,
            "keywords": sentiment_evidence.get("keywords"),
            "event_tags": sentiment_evidence.get("tags") or [],
            "impact_score": impact["impact"],
            "impact_band": impact["band"],
            "impact_factors": {
                "polarity": impact["polarity"],
                "sector_weight": impact["sector_weight"],
                "source_weight": impact["source_weight"],
                "recency_factor": impact["recency_factor"],
            },
            "impact_rationale": impact["rationale"],
        })
    return {
        "ticker": ticker,
        "articles": articles,
    }


@router.get("/sentiment")
async def get_sentiment(
    ticker: str = Query(...),
    window: str = Query("1h", description="'15m' | '1h' | '1d'"),
    current_user: User = Depends(get_current_user),
):
    """Cached aggregated signal for one ticker + window."""
    ticker = ticker.strip().upper()
    window_minutes = _parse_window(window)
    snap = await get_signal(ticker, window_minutes)
    if snap is None:
        return {"ticker": ticker, "window": window_label(window_minutes),
                "window_minutes": window_minutes, "signal": None,
                "note": "No fresh signal yet -- ingest runs every 5 minutes."}
    return {"ticker": ticker, "window": window_label(window_minutes),
            "window_minutes": window_minutes, "signal": snap,
            "regime": _regime(float(snap.get("score", 0.0)),
                              snap.get("zscore"), int(snap.get("article_count", 0)))}


@router.get("/signal")
async def get_signal_all_windows(
    ticker: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """All-window mood snapshot + evidence headlines for a ticker or all markets."""
    ticker = ticker.strip().upper()
    windows = []
    now = datetime.now(timezone.utc)
    if ticker == "ALL":
        signal_cutoff = now - timedelta(minutes=15)
        for w in settings.NEWS_WINDOWS_MINUTES:
            signal_rows = (await db.execute(
                select(
                    NewsSignal.ticker,
                    NewsSignal.score,
                    NewsSignal.article_count,
                    NewsSignal.impact,
                    NewsSignal.timestamp,
                )
                .where(
                    NewsSignal.window_minutes == w,
                    NewsSignal.timestamp >= signal_cutoff,
                    NewsSignal.timestamp <= now,
                )
                .order_by(NewsSignal.ticker, NewsSignal.timestamp.desc())
            )).all()
            latest_by_ticker = {}
            for signal_ticker, score, article_count, impact, timestamp in signal_rows:
                latest_by_ticker.setdefault(
                    signal_ticker,
                    (float(score), int(article_count), float(impact), timestamp),
                )
            total_weight = sum(max(row[1], 1) for row in latest_by_ticker.values())
            if total_weight:
                score = sum(
                    row[0] * max(row[1], 1) for row in latest_by_ticker.values()
                ) / total_weight
                impact = sum(
                    row[2] * max(row[1], 1) for row in latest_by_ticker.values()
                ) / total_weight
                article_count = sum(row[1] for row in latest_by_ticker.values())
                snap = {
                    "score": score,
                    "impact": impact,
                    "article_count": article_count,
                    "band": "HIGH" if abs(impact) >= settings.NEWS_HIGH_THRESHOLD
                    else "MEDIUM" if abs(impact) >= settings.NEWS_MED_THRESHOLD else "LOW",
                    "timestamp": max(row[3] for row in latest_by_ticker.values()).isoformat(),
                }
                windows.append({
                    "window": window_label(w),
                    "window_minutes": w,
                    "signal": snap,
                    "regime": _regime(score, None, article_count),
                })
            else:
                windows.append({
                    "window": window_label(w),
                    "window_minutes": w,
                    "signal": None,
                    "regime": "quiet",
                })
        heads = []
        headline_rows = (await db.execute(
            select(
                NewsArticle.title,
                NewsArticle.url,
                NewsArticle.language,
                NewsArticle.published_at,
                NewsSentiment.score,
                NewsSentiment.label,
            )
            .join(NewsSentiment, NewsSentiment.article_id == NewsArticle.id)
            .where(
                NewsArticle.published_at >= now - timedelta(minutes=60),
                NewsArticle.published_at <= now,
            )
            .order_by(NewsArticle.published_at.desc())
            .limit(5)
        )).all()
        heads = [{
            "title": title,
            "url": url,
            "language": language,
            "published_at": published_at.isoformat() if published_at else None,
            "score": float(score),
            "label": label,
        } for title, url, language, published_at, score, label in headline_rows]
        day_rows = (await db.execute(
            select(NewsSentiment.label)
            .join(NewsArticle, NewsSentiment.article_id == NewsArticle.id)
            .where(
                NewsArticle.published_at >= now - timedelta(hours=24),
                NewsArticle.published_at <= now,
            )
            .limit(500)
        )).scalars().all()
    else:
        for w in settings.NEWS_WINDOWS_MINUTES:
            snap = await get_signal(ticker, w)
            if snap is None:
                windows.append({"window": window_label(w), "window_minutes": w,
                                "signal": None, "regime": "quiet"})
            else:
                windows.append({
                    "window": window_label(w), "window_minutes": w, "signal": snap,
                    "regime": _regime(float(snap.get("score", 0.0)),
                                      snap.get("zscore"), int(snap.get("article_count", 0))),
                })
        heads = await top_headlines(db, ticker, 60, limit=5)
        cutoff = now - timedelta(hours=24)
        day_rows = (await db.execute(
            select(NewsSentiment.label)
            .join(NewsArticle, NewsSentiment.article_id == NewsArticle.id)
            .where(NewsSentiment.ticker == ticker,
                   NewsArticle.published_at >= cutoff)
            .limit(500)
        )).scalars().all()
    counts = {"POS": 0, "NEG": 0, "NEU": 0}
    for lab in day_rows:
        if lab in counts:
            counts[lab] += 1
    return {"ticker": ticker, "windows": windows,
            "headlines": heads, "last_24h_counts": counts}


@router.get("/evaluation")
async def get_news_outcome_evaluation(
    ticker: str | None = Query(default=None, min_length=1, max_length=20),
    days: int = Query(default=30, ge=1, le=60),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Historical directional baseline accuracy, not a calibrated forecast."""
    normalized_ticker = ticker.strip().upper() if ticker else None
    return await get_outcome_summary(db, normalized_ticker, days)


@router.get("/alerts")
async def get_news_alerts(current_user: User = Depends(get_current_user)):
    """In-app MEDIUM/HIGH impact alerts for the current user (24h TTL)."""
    return {"alerts": await get_alerts(current_user.id)}


class AdvisorRequest(BaseModel):
    strategy_id: uuid.UUID | None = None
    note: str = Field(default="", max_length=500)
    ticker: str | None = None
    headline: str | None = Field(default=None, max_length=500)
    sector: str | None = None
    sentiment_score: float | None = None
    sentiment_label: str | None = None
    article_url: str | None = None


class JournalRequest(BaseModel):
    strategy_id: uuid.UUID | None = None
    days: int = Field(default=7, ge=1, le=30)


class JournalOut(BaseModel):
    id: uuid.UUID
    kind: str
    body: str
    model: str
    strategy_id: uuid.UUID | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


async def _strategy_context(db: AsyncSession, user: User,
                            strategy_id: uuid.UUID | None) -> dict:
    """Structured, bounded user and strategy context for the advisor."""
    ctx: dict = {"user": user.username}
    if strategy_id is not None:
        s = (await db.execute(
            select(Strategy).where(Strategy.id == strategy_id,
                                   Strategy.user_id == user.id)
        )).scalar_one_or_none()
        if s is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Strategy not found")
        ctx["strategy"] = {
            "name": s.name, "ticker": s.ticker,
            "timeframe": s.timeframe.value, "status": s.status.value,
            "root_condition": s.root_condition,
            "action": {"side": s.action_side.value,
                       "order_type": s.action_order_type.value,
                       "quantity": s.action_quantity,
                       "settlement_type": s.action_settlement_type.value},
            "paused_reason": s.paused_reason,
            "quantity_multiplier": str(s.quantity_multiplier or "1.0"),
            "last_triggered_at": s.last_triggered_at.isoformat()
            if s.last_triggered_at else None,
        }
    orders = (await db.execute(
        select(Order).where(Order.user_id == user.id)
        .order_by(Order.created_at.desc()).limit(20)
    )).scalars().all()
    ctx["recent_orders"] = [{
        "ticker": o.ticker, "side": o.side.value,
        "order_type": o.order_type.value, "quantity": o.quantity,
        "executed_price": str(o.executed_price) if o.executed_price else None,
        "status": o.status.value, "triggered_by": o.triggered_by.value,
        "total_fees": str(o.total_fees) if o.total_fees else None,
    } for o in orders]
    positions = (await db.execute(
        select(Position).where(Position.user_id == user.id,
                               Position.status == PositionStatus.OPEN)
    )).scalars().all()
    ctx["open_positions"] = [{
        "ticker": p.ticker, "quantity": p.quantity,
        "avg_entry_price": str(p.avg_entry_price),
        "realised_pnl": str(p.realised_pnl),
    } for p in positions]
    return ctx


@router.post("/advisor")
async def strategy_advisor(
    payload: AdvisorRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Strategy Advisor (Claude, advisory-only). Uses either the current
    strategy context or the latest news intelligence for the selected ticker.
    Never touches execution, and it fails softly when the API key is unset.
    """
    if payload.ticker or payload.headline:
        ticker = (payload.ticker or "").strip().upper()
        market_snapshot = None
        if ticker:
            cached_price, bars = await asyncio.gather(
                get_cached_price(ticker),
                load_bars_dataframe(db, ticker, BarInterval.ONE_DAY, limit=100),
            )
            market_snapshot = build_market_snapshot(ticker, cached_price, bars)
        latest = (await db.execute(
            select(
                NewsArticle.title,
                NewsArticle.source,
                NewsArticle.published_at,
                NewsArticle.sector,
                NewsArticle.url,
                NewsSentiment.score,
                NewsSentiment.label,
                NewsSentiment.spans,
            )
            .join(NewsSentiment, NewsSentiment.article_id == NewsArticle.id)
            .where(NewsSentiment.ticker == ticker if ticker else NewsArticle.title.ilike(f"%{payload.headline or ''}%"))
            .order_by(NewsArticle.published_at.desc())
            .limit(8)
        )).all()
        news_signal = await get_signal(ticker, 60) if ticker else None
        signal_count = int(news_signal.get("article_count", 0)) if news_signal else 0
        signal_status = (
            "unavailable" if news_signal is None
            else "quiet" if signal_count < settings.NEWS_MIN_ARTICLES
            else "available"
        )
        recent_scores = [float(row[5]) for row in latest if row[5] is not None]
        news_score = (
            payload.sentiment_score
            if payload.sentiment_score is not None
            else (sum(recent_scores) / len(recent_scores) if recent_scores else None)
        )
        news_label = payload.sentiment_label
        if news_label is None and news_score is not None:
            news_label = "POS" if news_score > 0.15 else ("NEG" if news_score < -0.15 else "NEU")
        latest_headline = payload.headline or (latest[0][0] if latest else None)
        sector = payload.sector or (latest[0][3] if latest and latest[0][3] else "UNKNOWN")
        news_summary = {
            "article_count": len(latest),
            "average_sentiment": round(news_score, 4) if news_score is not None else None,
            "sentiment_label": news_label or "NEU",
            "latest_headline": latest_headline,
            "sector": sector,
            "one_hour_signal": {
                "status": signal_status,
                "score": news_signal.get("score") if news_signal else None,
                "impact": news_signal.get("impact") if news_signal else None,
                "band": news_signal.get("band") if news_signal else None,
                "article_count": signal_count,
                "note": (
                    "A cached 1-hour signal is unavailable; do not treat this as a verified catalyst."
                    if signal_status == "unavailable"
                    else "The 1-hour signal is below the minimum article count."
                    if signal_status == "quiet"
                    else None
                ),
            },
        }
        news_context = {
            "ticker": ticker or (payload.headline or "UNKNOWN").strip().upper(),
            "headline": latest_headline,
            "sector": sector,
            "sentiment_score": news_score,
            "sentiment_label": news_label or "NEU",
            "news_summary": news_summary,
            "news_signal": news_summary["one_hour_signal"],
            "article_url": payload.article_url,
            "market_snapshot": market_snapshot,
            "news_items": [{
                "title": title,
                "source": source,
                "published_at": published_at.isoformat() if published_at else None,
                "sector": sector,
                "url": url,
                "score": float(score) if score is not None else 0.0,
                "label": label,
                "keywords": (spans or {}).get("keywords") if isinstance(spans, dict) else None,
                "impact": explain_article_impact(
                    float(score) if score is not None else 0.0,
                    sector or "UNKNOWN",
                    source or "",
                    age_minutes(published_at, datetime.now(timezone.utc)),
                    label or "NEU",
                ),
            } for title, source, published_at, sector, url, score, label, spans in latest],
        }
        if payload.strategy_id is not None:
            news_context["strategy_context"] = await _strategy_context(
                db, current_user, payload.strategy_id
            )
        if payload.note:
            news_context["user_note"] = payload.note
        result = advisor_service.advise_on_news(news_context)
        entry = TradeJournal(user_id=current_user.id,
                             strategy_id=payload.strategy_id,
                             kind="advisor", context=news_context,
                             body=result["body"], model=result["model"])
        db.add(entry)
        await db.commit()
        await db.refresh(entry)
        return {"ok": result["ok"], "model": result["model"],
                "body": result["body"], "journal_id": str(entry.id),
                "market_snapshot": market_snapshot, "news_summary": news_summary}

    ctx = await _strategy_context(db, current_user, payload.strategy_id)
    if payload.note:
        ctx["user_note"] = payload.note
    result = advisor_service.advise_on_strategy(ctx)
    entry = TradeJournal(user_id=current_user.id,
                         strategy_id=payload.strategy_id,
                         kind="advisor", context=ctx,
                         body=result["body"], model=result["model"])
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return {"ok": result["ok"], "model": result["model"],
            "body": result["body"], "journal_id": str(entry.id)}


@router.post("/journal", response_model=JournalOut, status_code=status.HTTP_201_CREATED)
async def generate_journal(
    payload: JournalRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI Trade Journal entry from recent paper-trade data (advisory-only)."""
    ctx = await _strategy_context(db, current_user, payload.strategy_id)
    result = advisor_service.write_journal_entry({**ctx, "window_days": payload.days})
    entry = TradeJournal(user_id=current_user.id,
                         strategy_id=payload.strategy_id,
                         kind="journal", context={**ctx, "window_days": payload.days},
                         body=result["body"], model=result["model"])
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


@router.get("/journal", response_model=list[JournalOut])
async def list_journal(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(
        select(TradeJournal).where(TradeJournal.user_id == current_user.id)
        .order_by(TradeJournal.created_at.desc()).limit(50)
    )).scalars().all()
    return rows
