"""Signed, confidence-aware per-article impact scoring.

Sentiment is the signed expected polarity. Sector relevance, publisher
credibility, and recency attenuate that polarity; they must not inflate
it. Bands use absolute impact for severity and its sign for direction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


def source_weight(source: str) -> float:
    """Credibility prior, matched case-insensitively on the publisher tail."""
    text = (source or "").lower()
    tail = "".join(char for char in text.split(":")[-1] if char.isalnum())
    for key, weight in settings.NEWS_SOURCE_WEIGHTS.items():
        normalized_key = "".join(char for char in key.lower() if char.isalnum())
        if normalized_key and normalized_key in tail:
            return float(weight)
    return float(settings.NEWS_SOURCE_DEFAULT_WEIGHT)


def sector_weight(sector: str) -> float:
    return float(settings.NEWS_SECTOR_WEIGHTS.get(
        (sector or "UNKNOWN").upper(),
        settings.NEWS_SECTOR_WEIGHTS.get("UNKNOWN", 0.60)))


def recency_factor(age_minutes: float) -> float:
    """Linear decay to a floor (stale news never fully vanishes)."""
    try:
        age = max(float(age_minutes), 0.0)
    except (TypeError, ValueError):
        return settings.NEWS_RECENCY_FLOOR
    return max(settings.NEWS_RECENCY_FLOOR,
               1.0 - age / settings.NEWS_RECENCY_HALF_LIFE_MIN)


def article_impact(polarity: float, sector: str, source: str,
                   age_minutes: float) -> dict:
    """
    Signed per-article impact + auditable components. polarity MUST be
    signed already (+POS / -NEG); callers passing raw confidence here
    is the #1 integration bug this module guards against (we clamp,
    we don't abs -- direction must survive).
    """
    try:
        pol = max(-1.0, min(1.0, float(polarity)))
    except (TypeError, ValueError):
        pol = 0.0
    sec_w = sector_weight(sector)
    src_w = source_weight(source)
    rec = recency_factor(age_minutes)
    impact = pol * sec_w * src_w * rec
    return {
        "impact": round(impact, 5),
        "polarity": round(pol, 4),
        "sector_weight": round(sec_w, 4),
        "source_weight": round(src_w, 4),
        "recency_factor": round(rec, 4),
        "blend": round(sec_w * src_w * rec, 4),
        "band": classify_band(impact),
    }


def explain_article_impact(
    polarity: float,
    sector: str,
    source: str,
    age_minutes: float,
    sentiment_label: str,
) -> dict:
    """Return the impact factors and a user-readable heuristic rationale."""
    result = article_impact(polarity, sector, source, age_minutes)
    result["rationale"] = (
        f"{sentiment_label} sentiment ({result['polarity']:+.2f}) attenuated by "
        f"{sector or 'UNKNOWN'} sector relevance ({result['sector_weight']:.2f}), "
        f"publisher prior ({result['source_weight']:.2f}), and freshness "
        f"({result['recency_factor']:.2f}) gives heuristic impact "
        f"{result['impact']:+.3f}. This is not a price prediction."
    )
    return result


def classify_band(impact: float) -> str:
    """HIGH / MEDIUM / LOW on |impact|."""
    mag = abs(float(impact or 0.0))
    if mag >= settings.NEWS_HIGH_THRESHOLD:
        return "HIGH"
    if mag >= settings.NEWS_MED_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def age_minutes(published_at: datetime, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    if published_at is None:
        return 0.0
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return max((now - published_at).total_seconds() / 60.0, 0.0)
