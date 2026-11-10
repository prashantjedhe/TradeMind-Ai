"""Build cautious, confirm-before-submit paper-trade proposals from news signals."""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd

from app.config import settings
from app.services.advisor_market_context import build_market_snapshot


def build_trade_proposal(
    signal: dict | None,
    cached_price: Decimal | None,
    daily_bars: pd.DataFrame,
    market_trend: str,
    market_sentiment: str,
    market_last_bar_at: datetime | str | None,
    *,
    open_long_quantity: int = 0,
    now: datetime | None = None,
) -> dict | None:
    """Return a confirmed-direction setup, limiting bearish proposals to long exits."""
    if signal is None or cached_price is None:
        return None

    now = now or datetime.now(timezone.utc)
    if not cached_price.is_finite() or cached_price <= 0:
        return None
    timestamp = signal["timestamp"]
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    age_seconds = (now - timestamp).total_seconds()
    impact = float(signal["impact"])
    score = float(signal["score"])
    if not math.isfinite(impact) or not math.isfinite(score):
        return None
    direction = (
        "bullish" if impact > 0 and score >= 0.15
        else "bearish" if impact < 0 and score <= -0.15
        else None
    )

    if (
        age_seconds < 0
        or age_seconds > settings.NEWS_SIGNAL_TTL_SECONDS
        or int(signal["article_count"]) < settings.NEWS_MIN_ARTICLES
        or abs(impact) < settings.NEWS_MED_THRESHOLD
        or signal["band"] not in ("MEDIUM", "HIGH")
        or direction is None
        or (direction == "bearish" and open_long_quantity <= 0)
        or (
            direction == "bullish"
            and (
                market_trend != "bullish"
                or market_sentiment != "bullish"
                or market_last_bar_at is None
            )
        )
    ):
        return None

    if direction == "bullish":
        market_bar = pd.Timestamp(market_last_bar_at)
        if market_bar.tzinfo is None:
            market_bar = market_bar.tz_localize(timezone.utc)
        market_bar_age = (now - market_bar.to_pydatetime()).total_seconds()
        if market_bar_age < 0 or market_bar_age > 7 * 24 * 60 * 60:
            return None

    ticker = str(signal["ticker"]).strip().upper()
    if daily_bars is None or daily_bars.empty:
        return None
    last_bar = pd.Timestamp(daily_bars.index[-1])
    if last_bar.tzinfo is None:
        last_bar = last_bar.tz_localize(timezone.utc)
    ticker_bar_age = (now - last_bar.to_pydatetime()).total_seconds()
    if ticker_bar_age < 0 or ticker_bar_age > 7 * 24 * 60 * 60:
        return None
    market = build_market_snapshot(ticker, cached_price, daily_bars)
    if market["daily_trend"] != direction:
        return None

    limit_price = cached_price.quantize(Decimal("0.01"))
    side = "BUY" if direction == "bullish" else "SELL"
    quantity = 1 if side == "BUY" else open_long_quantity
    signal_id = str(signal["id"])
    proposal_id = hashlib.sha256(
        f"{signal_id}|{ticker}|{side}|{quantity}|{limit_price}".encode("utf-8")
    ).hexdigest()[:32]
    return {
        "proposal_id": proposal_id,
        "signal_id": signal_id,
        "ticker": ticker,
        "side": side,
        "order_type": "LIMIT",
        "quantity": quantity,
        "settlement_type": "INTRADAY",
        "limit_price": float(limit_price),
        "current_price": float(cached_price),
        "impact": round(impact, 4),
        "impact_band": signal["band"],
        "sentiment_score": round(score, 4),
        "article_count": int(signal["article_count"]),
        "signal_timestamp": timestamp.isoformat(),
        "market_trend": market_trend,
        "ticker_trend": market["daily_trend"],
        "rationale": (
            f"{ticker} has corroborated {direction} news impact and its daily trend "
            "aligns with broad-market sentiment and the NIFTY trend."
            if side == "BUY"
            else f"{ticker} has fresh, corroborated bearish news and a bearish daily trend; this SELL only proposes reducing your existing long position, even if the broad market trend differs."
        ),
        "risk_note": (
            "This paper LIMIT order may remain pending or fill later. "
            + (
                "It is limited to your existing long holding and will be canceled if that holding changes before execution. "
                if side == "SELL"
                else ""
            )
            + "No stop-loss is attached; review the order and manage risk yourself."
        ),
    }
