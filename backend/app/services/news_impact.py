"""
News impact scoring (corrected, realistic formula).

Spec correction applied: the original multiplicative chain
(polarity x sector x source x recency, all <= 1) compressed every
real story into MEDIUM/LOW -- only a perfect Reuters+BANK+fresh+
0.95-confidence story could reach HIGH. The engine's headline
actions would have been dead code.

Corrected formula (weighted blend -- one weak factor can no longer
veto three strong ones):

    impact = polarity x (W_SECTOR*sector_w + W_SOURCE*source_w
                         + W_RECENCY*recency)

    polarity : SIGNED. FinBERT -> +conf (POS) / -conf (NEG) /
               P(pos)-P(neg) (NEU). Lexicon -> signed score.
    sector_w : NEWS_SECTOR_WEIGHTS (priors v1, quarterly refit).
    source_w : NEWS_SOURCE_WEIGHTS substring match, else default 0.50.
    recency  : max(FLOOR, 1 - age_minutes / HALF_LIFE_MIN).

Bands use |impact| for gating (pause/tighten) and sign(impact) for
direction. Thresholds are env-tunable defaults; the signals log
carries every impact so HIGH/MEDIUM can be recalibrated by
percentile (HIGH ~= 95th pct of |impact|).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.config import settings

logger = logging.getLogger(__name__)


def source_weight(source: str) -> float:
    """Credibility prior, matched case-insensitively on the publisher tail."""
    text = (source or "").lower()
    # Publisher is the tail segment ("google-news-rss:en:Economic Times").
    tail = text.split(":")[-1]
    for key, weight in settings.NEWS_SOURCE_WEIGHTS.items():
        if key.lower() in tail or key.lower() in text:
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
    blend = (settings.NEWS_W_SECTOR * sec_w
             + settings.NEWS_W_SOURCE * src_w
             + settings.NEWS_W_RECENCY * rec)
    impact = pol * blend
    return {
        "impact": round(impact, 5),
        "polarity": round(pol, 4),
        "sector_weight": round(sec_w, 4),
        "source_weight": round(src_w, 4),
        "recency_factor": round(rec, 4),
        "blend": round(blend, 4),
        "band": classify_band(impact),
    }


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
