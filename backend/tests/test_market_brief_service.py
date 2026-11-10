from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd

from app.services.market_brief_service import build_market_brief


def _bars(closes: list[float]) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=len(closes), freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": closes,
            "high": closes,
            "low": closes,
            "close": closes,
            "volume": [1000] * len(closes),
        },
        index=index,
    )


def _articles(now: datetime, score: float) -> list[tuple]:
    return [
        (f"Market update {i}", now - timedelta(minutes=i * 5), "INDEX", "Reuters", score, "POS" if score > 0 else "NEG")
        for i in range(3)
    ]


def test_market_brief_suggests_confirmation_setup_for_aligned_positive_news():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)

    result = build_market_brief(
        _articles(now, 0.6),
        Decimal("22500"),
        _bars([100 + i for i in range(60)]),
        now=now,
    )

    assert result["news_status"] == "available"
    assert result["sentiment"] == "bullish"
    assert result["market_snapshot"]["daily_trend"] == "bullish"
    assert "breakout" in result["strategy"]
    assert "stop" in result["action"]
    assert result["advisory_only"] is True
    assert len(result["headlines"]) == 3


def test_market_brief_does_not_recommend_trade_when_quote_is_missing():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)

    result = build_market_brief(
        _articles(now, 0.6),
        None,
        _bars([100 + i for i in range(60)]),
        now=now,
    )

    assert result["sentiment"] == "bullish"
    assert "Wait for a fresh NIFTY quote" in result["action"]
    assert result["strategy"] == "No confirmed setup — stay flat."


def test_market_brief_distinguishes_available_quote_from_unconfirmed_daily_trend():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)

    result = build_market_brief(
        _articles(now, 0.6),
        Decimal("22500"),
        _bars([100 + i for i in range(30)]),
        now=now,
    )

    assert result["market_snapshot"]["quote_status"] == "available"
    assert result["market_snapshot"]["daily_trend"] == "unknown"
    assert "cached quote is ₹22,500.00" in result["summary"]
    assert "not enough stored history" in result["summary"]
    assert "Wait for enough daily history" in result["action"]


def test_market_brief_requires_minimum_news_and_index_trend_alignment():
    now = datetime(2026, 4, 1, tzinfo=timezone.utc)
    result = build_market_brief(
        _articles(now, -0.6),
        Decimal("22500"),
        _bars([200 - i for i in range(60)]),
        now=now,
        minimum_articles=4,
    )

    assert result["news_status"] == "insufficient"
    assert result["sentiment"] == "bearish"
    assert result["strategy"] == "No strategy signal — stay flat."
    assert result["advisory_only"] is True
