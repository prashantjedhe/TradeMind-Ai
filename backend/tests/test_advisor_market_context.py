from decimal import Decimal

import pandas as pd

from app.services.advisor import _local_news_strategy
from app.services.advisor_market_context import build_market_snapshot


def _bars(closes: list[float]) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=len(closes), freq="D", tz="UTC")
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


def test_market_snapshot_includes_quote_and_closed_bar_indicators():
    bars = _bars([100 + value for value in range(60)])

    result = build_market_snapshot("reliance", Decimal("160.50"), bars)

    assert result["ticker"] == "RELIANCE"
    assert result["cached_quote"] == 160.5
    assert result["quote_status"] == "available"
    assert result["daily_trend"] == "bullish"
    assert result["rsi_14"] == 100.0
    assert result["daily_change_pct"] is not None
    assert result["last_daily_bar_at"] == bars.index[-1].isoformat()


def test_market_snapshot_marks_missing_quote_and_history_unavailable():
    result = build_market_snapshot("RELIANCE", None, pd.DataFrame())

    assert result["quote_status"] == "unavailable"
    assert result["cached_quote"] is None
    assert result["history_status"] == "unavailable"
    assert result["daily_trend"] == "unknown"
    assert result["rsi_14"] is None
    assert "Do not recommend an entry" in result["quote_note"]


def test_local_fallback_does_not_recommend_trade_without_quote():
    result = _local_news_strategy(
        {
            "ticker": "RELIANCE",
            "sentiment_label": "POS",
            "sentiment_score": 0.9,
            "market_snapshot": {"cached_quote": None, "daily_trend": "bullish"},
        }
    )

    assert "Stay flat" in result
    assert "quote unavailable" in result
    assert "No order is placed" in result


def test_local_fallback_waits_when_news_and_trend_conflict():
    result = _local_news_strategy(
        {
            "ticker": "RELIANCE",
            "sentiment_label": "POS",
            "sentiment_score": 0.8,
            "market_snapshot": {"cached_quote": 100, "daily_trend": "bearish"},
            "news_signal": {"status": "available", "score": 0.7},
        }
    )

    assert "Wait for confirmation" in result
    assert "aligned" in result


def test_local_fallback_requires_corroborated_signal_before_directional_advice():
    result = _local_news_strategy(
        {
            "ticker": "RELIANCE",
            "sentiment_label": "POS",
            "sentiment_score": 0.8,
            "market_snapshot": {"cached_quote": 100, "daily_trend": "bullish"},
            "news_signal": {"status": "quiet", "score": 0.8},
        }
    )

    assert "Stay flat" in result
    assert "corroborated 1-hour news signal is unavailable" in result


def test_local_fallback_only_considers_aligned_directional_signal():
    result = _local_news_strategy(
        {
            "ticker": "RELIANCE",
            "sentiment_label": "POS",
            "sentiment_score": 0.8,
            "market_snapshot": {"cached_quote": 100, "daily_trend": "bullish"},
            "news_signal": {"status": "available", "score": 0.7, "impact": 0.6},
        }
    )

    assert "paper BUY" in result
    assert "No order is placed" in result
