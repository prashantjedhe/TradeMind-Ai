from app.services.news_impact import (
    article_impact,
    explain_article_impact,
    source_weight,
)
from app.services.news_outcome_math import BarPoint, find_forward_outcome
from app.services.news_sentiment import (
    _sentiment_from_probabilities,
    score_article_hybrid,
    score_text,
)
from datetime import datetime, timezone


def test_finbert_score_uses_directional_probability_difference():
    result = _sentiment_from_probabilities({
        "positive": 0.78,
        "negative": 0.12,
        "neutral": 0.10,
    })

    assert result["score"] == 0.66
    assert result["label"] == "POS"
    assert result["confidence"] == 0.78


def test_conflicting_finbert_probabilities_are_neutral_not_bullish():
    result = _sentiment_from_probabilities({
        "positive": 0.39,
        "negative": 0.31,
        "neutral": 0.30,
    })

    assert result["score"] == 0.08
    assert result["label"] == "NEU"


def test_impact_attenuates_sentiment_by_relevance_credibility_and_age(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "NEWS_SECTOR_WEIGHTS", {"BANK": 0.8})
    monkeypatch.setattr(settings, "NEWS_SOURCE_WEIGHTS", {})
    monkeypatch.setattr(settings, "NEWS_SOURCE_DEFAULT_WEIGHT", 0.5)
    monkeypatch.setattr(settings, "NEWS_RECENCY_HALF_LIFE_MIN", 120.0)
    monkeypatch.setattr(settings, "NEWS_RECENCY_FLOOR", 0.1)

    result = article_impact(0.8, "BANK", "google-news-rss:en:unknown", 0)

    assert result["impact"] == 0.32
    assert result["blend"] == 0.4


def test_source_weight_matches_publisher_names_with_spaces_and_punctuation(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "NEWS_SOURCE_WEIGHTS", {"business-standard": 0.85})
    monkeypatch.setattr(settings, "NEWS_SOURCE_DEFAULT_WEIGHT", 0.5)

    assert source_weight("google-news-rss:en:Business Standard") == 0.85


def test_negative_sentiment_keeps_negative_impact_direction():
    result = _sentiment_from_probabilities({
        "positive": 0.10,
        "negative": 0.78,
        "neutral": 0.12,
    })

    assert result["score"] == -0.68
    assert result["label"] == "NEG"


def test_impact_explanation_exposes_factors_and_disclaims_prediction(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "NEWS_SECTOR_WEIGHTS", {"BANK": 0.8})
    monkeypatch.setattr(settings, "NEWS_SOURCE_WEIGHTS", {})
    monkeypatch.setattr(settings, "NEWS_SOURCE_DEFAULT_WEIGHT", 0.5)

    explanation = explain_article_impact(
        -0.6, "BANK", "unknown", 30, "NEG"
    )

    assert explanation["impact"] < 0
    assert explanation["polarity"] == -0.6
    assert explanation["sector_weight"] == 0.8
    assert explanation["source_weight"] == 0.5
    assert explanation["recency_factor"] < 1
    assert "not a price prediction" in explanation["rationale"]


def test_lexicon_score_does_not_saturate_on_two_positive_terms():
    result = score_text("profit growth")

    assert result["score"] == 0.4
    assert result["label"] == "POS"


def test_hybrid_sentiment_falls_back_to_lexicon_when_finbert_fails(monkeypatch):
    from app.services import news_sentiment

    def fail_finbert(_text):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(news_sentiment, "score_text_finbert", fail_finbert)
    result = score_article_hybrid("The stock rally brings strong profit growth")

    assert result["model"] == news_sentiment.MODEL_VERSION
    assert result["language"] == "en"
    assert result["score"] > 0


def test_forward_outcome_uses_only_closed_bars_and_starts_after_horizon():
    signal_time = datetime(2026, 10, 2, 10, 30, tzinfo=timezone.utc)
    bars = [
        BarPoint(datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc), 100),
        BarPoint(datetime(2026, 10, 2, 10, 15, tzinfo=timezone.utc), 105),
        BarPoint(datetime(2026, 10, 2, 10, 30, tzinfo=timezone.utc), 110),
    ]

    outcome = find_forward_outcome(
        signal_time, 15, "15m", bars,
        datetime(2026, 10, 2, 10, 45, tzinfo=timezone.utc),
    )

    assert outcome is not None
    assert outcome["source_price"] == 105
    assert outcome["target_price"] == 110
    assert outcome["return_fraction"] == 110 / 105 - 1
    assert outcome["source_timestamp"] == signal_time


def test_forward_outcome_rejects_unclosed_future_target_bar():
    signal_time = datetime(2026, 10, 2, 10, 30, tzinfo=timezone.utc)
    bars = [
        BarPoint(datetime(2026, 10, 2, 10, 15, tzinfo=timezone.utc), 105),
        BarPoint(datetime(2026, 10, 2, 10, 30, tzinfo=timezone.utc), 110),
    ]

    outcome = find_forward_outcome(
        signal_time, 15, "15m", bars,
        datetime(2026, 10, 2, 10, 40, tzinfo=timezone.utc),
    )

    assert outcome is None


def test_forward_outcome_requires_a_completed_source_price():
    signal_time = datetime(2026, 10, 2, 10, 30, tzinfo=timezone.utc)
    bars = [
        BarPoint(datetime(2026, 10, 2, 10, 30, tzinfo=timezone.utc), 110),
    ]

    outcome = find_forward_outcome(
        signal_time, 15, "15m", bars,
        datetime(2026, 10, 2, 10, 45, tzinfo=timezone.utc),
    )

    assert outcome is None


def test_daily_outcome_waits_until_nse_close_for_date_stamped_candles():
    signal_time = datetime(2026, 10, 2, 10, 0, tzinfo=timezone.utc)
    bars = [
        BarPoint(datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc), 100),
        BarPoint(datetime(2026, 10, 5, 0, 0, tzinfo=timezone.utc), 105),
    ]

    before_close = find_forward_outcome(
        datetime(2026, 10, 2, 9, 59, tzinfo=timezone.utc),
        1440,
        "1d",
        bars,
        datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc),
    )
    after_horizon = find_forward_outcome(
        signal_time,
        1440,
        "1d",
        bars,
        datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc),
    )

    assert before_close is None
    assert after_horizon is not None
    assert after_horizon["source_timestamp"] == signal_time
    assert after_horizon["target_price"] == 105
