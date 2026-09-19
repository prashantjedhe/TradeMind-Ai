import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.news import NewsArticle, NewsSentiment
from app.models.order import Order
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


@router.get("/latest")
async def get_latest_news(
    ticker: str = Query(..., description="Equity ticker, e.g. RELIANCE"),
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Latest scored headlines for a ticker (EN + HI) with enough context for the UI."""
    ticker = ticker.strip().upper()
    rows = (await db.execute(
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
        .where(NewsSentiment.ticker == ticker)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    )).all()
    return {
        "ticker": ticker,
        "articles": [{
            "title": title,
            "url": url,
            "language": language,
            "published_at": published_at.isoformat() if published_at else None,
            "source": source,
            "sector": sector or "UNKNOWN",
            "tickers": list(tickers or []),
            "score": float(score) if score is not None else 0.0,
            "label": label,
            "magnitude": float(magnitude) if magnitude is not None else 0.0,
            "keywords": (spans or {}).get("keywords") if isinstance(spans, dict) else None,
        } for title, url, language, published_at, source, sector, tickers, score, label, magnitude, spans in rows],
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
    """All-window mood snapshot + evidence headlines for a ticker."""
    ticker = ticker.strip().upper()
    windows = []
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
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
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

    class Config:
        from_attributes = True


async def _strategy_context(db: AsyncSession, user: User,
                            strategy_id: uuid.UUID | None) -> dict:
    """Structured, bounded context for the advisor. No live prices."""
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
        news_context = {
            "ticker": ticker or (payload.headline or "UNKNOWN").strip().upper(),
            "headline": payload.headline,
            "sector": payload.sector,
            "sentiment_score": payload.sentiment_score,
            "sentiment_label": payload.sentiment_label,
            "article_url": payload.article_url,
            "news_items": [{
                "title": title,
                "source": source,
                "published_at": published_at.isoformat() if published_at else None,
                "sector": sector,
                "url": url,
                "score": float(score) if score is not None else 0.0,
                "label": label,
                "keywords": (spans or {}).get("keywords") if isinstance(spans, dict) else None,
            } for title, source, published_at, sector, url, score, label, spans in latest],
        }
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
                "body": result["body"], "journal_id": str(entry.id)}

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
