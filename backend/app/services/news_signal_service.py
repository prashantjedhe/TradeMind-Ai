"""
News signal aggregation: per-ticker, per-window sentiment snapshots.

Pipeline position: ingest scores each article (news_sentiment) ->
this module aggregates the window ending NOW into one row per
(ticker, window) in `news_signals` + a Redis JSON snapshot the API
reads. The strategy evaluator reads the *series* from Postgres so
`crosses_above/below` edge semantics match OHLCV indicators.

Anti-lookahead: every query filters published_at <= bucket timestamp.
Single-rumor guard: rows with article_count < NEWS_MIN_ARTICLES still
persist (for the UI), but the evaluator treats them as missing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone

import pandas as pd
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import redis_client
from app.config import settings
from app.models.news import NewsArticle, NewsSentiment, NewsSignal

logger = logging.getLogger(__name__)

SIGNAL_KEY_PREFIX = "news:sent:"
METRICS = ("score", "zscore", "count")


def _signal_key(ticker: str, window_minutes: int) -> str:
    return f"{SIGNAL_KEY_PREFIX}{ticker.strip().upper()}:{window_minutes}"


def _decay(age_hours: float, half_life: float) -> float:
    if age_hours < 0:
        return 0.0
    return 0.5 ** (age_hours / half_life)


async def aggregate_ticker(
    db: AsyncSession, ticker: str, now: datetime,
    windows: list[int] | None = None,
) -> list[dict]:
    """
    Aggregate one ticker across windows. Returns the snapshot dicts
    (also persisted to news_signals + Redis). Pure anti-lookahead:
    only articles with published_at <= now are considered.
    """
    ticker = ticker.strip().upper()
    windows = windows or settings.NEWS_WINDOWS_MINUTES
    half_life = settings.NEWS_HALF_LIFE_HOURS
    lookback = timedelta(days=settings.NEWS_LOOKBACK_DAYS)

    rows = (await db.execute(
        select(NewsSentiment.score, NewsSentiment.magnitude, NewsArticle.published_at,
               NewsArticle.source, NewsArticle.sector)
        .join(NewsArticle, NewsSentiment.article_id == NewsArticle.id)
        .where(NewsSentiment.ticker == ticker,
               NewsArticle.published_at <= now,
               NewsArticle.published_at >= now - lookback)
        .order_by(NewsArticle.published_at.desc())
        .limit(2000)
    )).all()

    # Local import: news_impact is engine-side; keep this module's
    # import surface (used by the evaluator hot path) light.
    from app.services.news_impact import age_minutes as _age_min
    from app.services.news_impact import article_impact as _article_impact
    from app.services.news_impact import classify_band as _classify

    snapshots: list[dict] = []
    for window in windows:
        cutoff = now - timedelta(minutes=window)
        in_window = [(float(s), float(m), p, src, sec)
                     for s, m, p, src, sec in rows if p >= cutoff]
        n = len(in_window)

        if n == 0:
            score, impact = 0.0, 0.0
        else:
            num = den = 0.0
            inum = iden = 0.0
            for s, m, p, src, sec in in_window:
                age_h = max((now - p).total_seconds(), 0.0) / 3600.0
                w = _decay(age_h, half_life) * (0.5 + 0.5 * m)
                num += s * w
                den += w
                comp = _article_impact(s, sec or "UNKNOWN", src or "",
                                       _age_min(p, now))
                inum += comp["impact"] * w
                iden += w
            score = num / den if den > 0 else 0.0
            impact = inum / iden if iden > 0 else 0.0

        zscore = await _baseline_zscore(db, ticker, window, now, score)
        snapshots.append({
            "ticker": ticker, "window_minutes": window,
            "timestamp": now, "score": round(score, 5),
            "zscore": round(zscore, 4) if zscore is not None else None,
            "article_count": n,
            "impact": round(impact, 5), "band": _classify(impact),
        })
    return snapshots


async def _baseline_zscore(
    db: AsyncSession, ticker: str, window: int, now: datetime, score: float
) -> float | None:
    """z-score of `score` vs the trailing 7-day signal mean/std."""
    lookback = timedelta(days=settings.NEWS_LOOKBACK_DAYS)
    vals = (await db.execute(
        select(NewsSignal.score)
        .where(NewsSignal.ticker == ticker,
               NewsSignal.window_minutes == window,
               NewsSignal.timestamp < now - timedelta(minutes=window),
               NewsSignal.timestamp >= now - lookback)
        .order_by(NewsSignal.timestamp.desc())
        .limit(500)
    )).scalars().all()
    vals = [float(v) for v in vals]
    if len(vals) < 5:
        return None
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    if var <= 1e-12:
        return 0.0
    return (score - mean) / (var ** 0.5)


async def persist_snapshots(db: AsyncSession, snapshots: list[dict]) -> None:
    """Upsert signal rows + refresh Redis snapshots (TTL safety net)."""
    if not snapshots:
        return
    stmt = pg_insert(NewsSignal).values([
        {k: s[k] for k in ("ticker", "window_minutes", "timestamp",
                           "score", "zscore", "article_count",
                           "impact", "band")}
        for s in snapshots
    ])
    stmt = stmt.on_conflict_do_update(
        constraint="uq_news_signal_bucket",
        set_={"score": stmt.excluded.score,
              "zscore": stmt.excluded.zscore,
              "article_count": stmt.excluded.article_count,
              "impact": stmt.excluded.impact,
              "band": stmt.excluded.band},
    )
    await db.execute(stmt)
    await db.commit()

    for s in snapshots:
        payload = {**s, "timestamp": s["timestamp"].isoformat()}
        await redis_client.setex(
            _signal_key(s["ticker"], s["window_minutes"]),
            settings.NEWS_SIGNAL_TTL_SECONDS, json.dumps(payload))


async def get_signal(ticker: str, window_minutes: int) -> dict | None:
    """Read the cached signal snapshot for the API / UI."""
    raw = await redis_client.get(_signal_key(ticker, window_minutes))
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        logger.error("Corrupt news signal for %s:%s", ticker, window_minutes)
        return None


async def load_sentiment_series(
    db: AsyncSession, ticker: str, window_minutes: int,
    metric: str, limit: int = 200,
) -> pd.Series:
    """
    Time series the evaluator consumes. `metric` is score|zscore|count.
    Low-count buckets (< NEWS_MIN_ARTICLES) become NaN so the leaf
    evaluates False -- same "missing means skip" rule as OHLCV warm-up.
    """
    if metric not in METRICS:
        raise ValueError(f"Unknown sentiment metric: {metric}")
    rows = (await db.execute(
        select(NewsSignal.timestamp, NewsSignal.score,
               NewsSignal.zscore, NewsSignal.article_count)
        .where(NewsSignal.ticker == ticker.strip().upper(),
               NewsSignal.window_minutes == window_minutes)
        .order_by(NewsSignal.timestamp.desc())
        .limit(limit)
    )).all()
    rows = list(reversed(rows))
    if not rows:
        return pd.Series(dtype=float)

    min_n = settings.NEWS_MIN_ARTICLES
    values: list[float | None] = []
    for ts, score, zscore, n in rows:
        if n < min_n:
            values.append(None)
            continue
        if metric == "score":
            values.append(float(score))
        elif metric == "zscore":
            values.append(float(zscore) if zscore is not None else None)
        else:
            values.append(float(n))
    return pd.Series(values,
                     index=pd.DatetimeIndex([r[0] for r in rows], name="timestamp"),
                     dtype=float)


async def top_headlines(db: AsyncSession, ticker: str, window_minutes: int,
                        limit: int = 5) -> list[dict]:
    """Evidence headlines for the API + order audit trail."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    rows = (await db.execute(
        select(NewsArticle.title, NewsArticle.url, NewsArticle.language,
               NewsArticle.published_at, NewsSentiment.score, NewsSentiment.label)
        .join(NewsSentiment, NewsSentiment.article_id == NewsArticle.id)
        .where(NewsSentiment.ticker == ticker.strip().upper(),
               NewsArticle.published_at >= cutoff)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
    )).all()
    return [{
        "title": t, "url": u, "language": lang,
        "published_at": p.isoformat() if p else None,
        "score": float(s), "label": lab,
    } for t, u, lang, p, s, lab in rows]


def window_label(window_minutes: int) -> str:
    if window_minutes < 60:
        return f"{window_minutes}m"
    if window_minutes < 1440:
        return f"{window_minutes // 60}h"
    return f"{window_minutes // 1440}d"
