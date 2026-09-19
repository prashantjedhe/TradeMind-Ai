"""
Keyword extraction for news evidence (Model 2: RAKE).

RAKE (rake-nltk) is a statistical algorithm, not ML: min_length=1,
max_length=4, top_n=15, <5ms per article. English only -- RAKE ships
no Hindi stopwords, so Hindi articles fall back to the lexicon hit
terms already captured as evidence spans.

Output feeds NewsSentiment.spans["keywords"] (audit trail) and can
supplement ticker attribution downstream. NLTK stopwords are baked
into the Docker image (see Dockerfile); missing corpus degrades to
[] rather than crashing the ingest cycle.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


def extract_keywords(text: str, language: str = "en", top_n: int = 15) -> list[str]:
    """Top key phrases for evidence. Never raises."""
    text = (text or "").strip()
    if not text:
        return []
    if language != "en":
        return []
    try:
        from rake_nltk import Rake
        rake = Rake(min_length=1, max_length=4)
        rake.extract_keywords_from_text(text)
        return [p for p in rake.get_ranked_phrases()[:top_n] if len(p) > 1]
    except Exception as exc:
        logger.debug("RAKE unavailable, keywords skipped: %s", exc)
        return []


def finance_tags(text: str) -> list[str]:
    """Cheap event-type tags from the same finance vocabulary, both languages."""
    lowered = text.lower()
    tags: list[str] = []
    rules = [
        ("results", ["result", "quarter", "q1", "q2", "q3", "q4", "नतीजे", "तिमाही"]),
        ("rating", ["upgrade", "downgrade", "outperform", "अपग्रेड"]),
        ("regulatory", ["sebi", "rbi", "probe", "investigation", "notice", "जांच", "जुर्माना"]),
        ("corporate-action", ["dividend", "buyback", "split", "bonus", "डिविडेंड", "बायबैक"]),
        ("mna", ["merger", "acquisition", "takeover", "stake"]),
        ("debt", ["default", "bankruptcy", "downgrade", "डिफॉल्ट", "दिवालिया"]),
        ("orders", ["order win", "contract", "deal", "ऑर्डर"]),
    ]
    for tag, keys in rules:
        if any(k in lowered for k in keys):
            tags.append(tag)
    return tags
