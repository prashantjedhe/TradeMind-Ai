"""Summarize recent scored market news into cautious paper-trading guidance."""

from datetime import datetime, timezone

import pandas as pd

from app.services.advisor_market_context import build_market_snapshot
from app.services.news_impact import age_minutes, article_impact


def build_market_brief(
    articles: list[tuple],
    cached_index_price,
    daily_bars: pd.DataFrame,
    *,
    now: datetime | None = None,
    minimum_articles: int = 3,
) -> dict:
    now = now or datetime.now(timezone.utc)
    scored = []
    for title, published_at, sector, source, score, label in articles:
        impact = article_impact(
            score,
            sector or "UNKNOWN",
            source or "",
            age_minutes(published_at, now),
        )
        scored.append({
            "headline": title,
            "published_at": published_at.isoformat() if published_at else None,
            "score": float(score),
            "label": label or "NEU",
            "impact": impact["impact"],
            "band": impact["band"],
        })

    count = len(scored)
    avg_score = sum(item["score"] for item in scored) / count if count else None
    avg_impact = sum(item["impact"] for item in scored) / count if count else None
    sentiment = (
        "bullish" if avg_score is not None and avg_score >= 0.15
        else "bearish" if avg_score is not None and avg_score <= -0.15
        else "mixed" if avg_score is not None
        else "unavailable"
    )
    market = build_market_snapshot("NIFTY", cached_index_price, daily_bars)
    aligned = (
        sentiment == market["daily_trend"]
        and sentiment in ("bullish", "bearish")
    )

    if count < minimum_articles:
        summary = (
            f"Only {count} scored market headline{'s' if count != 1 else ''} found in the past hour; "
            "there is not enough corroboration to call the news direction."
        )
        action = "Wait for more independently scored headlines and a fresh NIFTY quote; do not trade from a single story."
        strategy = "No strategy signal — stay flat."
        confidence = "Low"
    elif market["quote_status"] != "available":
        summary = (
            f"Past-hour news sentiment is {sentiment} across {count} scored headlines, "
            "but a current cached NIFTY quote is unavailable."
        )
        action = "Wait for a fresh NIFTY quote and confirmed market direction before entering."
        strategy = "No confirmed setup — stay flat."
        confidence = "Low"
    elif market["daily_trend"] == "unknown":
        quote_text = f"₹{float(market['cached_quote']):,.2f}"
        daily_move = market.get("daily_change_pct")
        daily_text = (
            f" The latest stored daily bar is {daily_move:+.2f}%."
            if daily_move is not None
            else ""
        )
        summary = (
            f"Past-hour news sentiment is {sentiment} across {count} scored headlines. "
            f"NIFTY's cached quote is {quote_text}, but the daily trend is unconfirmed because "
            f"there is not enough stored history for the trend indicators.{daily_text}"
        )
        action = "Wait for enough daily history to confirm the index trend; do not take a directional trade from headlines alone."
        strategy = "No confirmed setup — stay flat until price trend and news agree."
        confidence = "Low"
    elif not aligned:
        summary = (
            f"Past-hour news sentiment is {sentiment} across {count} scored headlines, "
            f"while the latest stored NIFTY daily trend is {market['daily_trend']}."
        )
        action = "Avoid a directional entry until news and index trend agree; protect existing positions with predefined risk limits."
        strategy = "No aligned strategy signal — wait for confirmation."
        confidence = "Low"
    elif sentiment == "bullish":
        summary = (
            f"Past-hour news sentiment is bullish across {count} scored headlines "
            "and aligns with the latest stored NIFTY daily trend."
        )
        action = "Watch for a confirmed breakout or pullback hold; enter only after price confirmation with a predefined stop and small paper-trade risk."
        strategy = "Consider a confirmation-based long breakout/pullback setup; avoid chasing gaps."
        confidence = "Cautious"
    else:
        summary = (
            f"Past-hour news sentiment is bearish across {count} scored headlines "
            "and aligns with the latest stored NIFTY daily trend."
        )
        action = "Avoid new long entries; wait for price confirmation and review exposure against your predefined risk limits."
        strategy = "Defensive / stay-flat setup; do not short unless your paper strategy explicitly supports it."
        confidence = "Cautious"

    return {
        "as_of": now.isoformat(),
        "window_minutes": 60,
        "news_status": "available" if count >= minimum_articles else "insufficient",
        "article_count": count,
        "sentiment": sentiment,
        "average_sentiment": round(avg_score, 4) if avg_score is not None else None,
        "average_impact": round(avg_impact, 4) if avg_impact is not None else None,
        "summary": summary,
        "action": action,
        "strategy": strategy,
        "confidence": confidence,
        "market_snapshot": market,
        "headlines": scored[:3],
        "advisory_only": True,
        "disclaimer": "News sentiment is not a price prediction or profit guarantee. Paper trading only; no order is submitted without your explicit confirmation.",
    }
