"""
Bilingual (English + Hindi) finance sentiment scorer — hybrid pipeline.

Routing (the realistic correction for FinBERT being English-only):
- English text  -> FinBERT (ProsusAI/finbert), lazy singleton per
  worker process, CPU inference, truncation at 512 tokens.
- Hindi text    -> bilingual lexicon below (Devanagari + transliterated).
- FinBERT unavailable (no torch/model/timeout) -> lexicon for all.

Output contract (both paths): score in [-1, +1] (SIGNED polarity),
magnitude/confidence in [0, 1], label POS/NEG/NEU, evidence spans,
detected language, model id. The impact engine consumes `polarity`
(= score) and keeps confidence separate from direction.

Lexicon coverage:
- English finance terms (rally/surge/beat/upgrade vs plunge/miss/
  downgrade/probe/default ...).
- Hindi Devanagari terms (बढ़त/मुनाफा/तेजी vs गिरावट/घाटा/जांच ...).
- Transliterated Hindi in Latin script (tezi/munafa vs giravat/ghata),
  common in Indian business headlines.
- Negation (not/never/n't, नहीं/ना/बिना) flips the next 3 tokens;
  intensifiers (very/record/बहुत/भारी) scale ×1.5.
"""

from __future__ import annotations

import logging
import re
import threading
import time

MODEL_VERSION = "lexicon-bilingual-v2"
FINBERT_MODEL_VERSION = "finbert-ProsusAI-v2"

logger = logging.getLogger(__name__)

# Lazy singleton: loaded once per worker process on first EN article,
# never inside the per-invocation asyncio task body (a 110M-param
# reload every 5 minutes would blow the cycle budget).
_FINBERT = {"tokenizer": None, "model": None, "ok": False, "attempted": False}
_FINBERT_LOCK = threading.Lock()
_FINBERT_SPENT_S = 0.0  # per-process cycle budget guard (reset by ingest)


def warmup_finbert() -> bool:
    """Load FinBERT now (called once at worker startup). Returns ok."""
    return _ensure_finbert()


def _ensure_finbert() -> bool:
    if _FINBERT["ok"]:
        return True
    if _FINBERT["attempted"] and not _FINBERT["ok"]:
        return False
    with _FINBERT_LOCK:
        if _FINBERT["ok"]:
            return True
        if _FINBERT["attempted"]:
            return False
        _FINBERT["attempted"] = True
        try:
            from transformers import (  # local import: backend stays importable without torch
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            from app.config import settings

            t0 = time.monotonic()
            _FINBERT["tokenizer"] = AutoTokenizer.from_pretrained(settings.NEWS_FINBERT_ID)
            _FINBERT["model"] = AutoModelForSequenceClassification.from_pretrained(
                settings.NEWS_FINBERT_ID
            )
            _FINBERT["model"].eval()
            _FINBERT["ok"] = True
            logger.info("FinBERT loaded in %.1fs (%s)",
                        time.monotonic() - t0, settings.NEWS_FINBERT_ID)
        except Exception as exc:
            logger.warning("FinBERT unavailable, lexicon fallback active: %s", exc)
            _FINBERT["ok"] = False
    return _FINBERT["ok"]


def finbert_available() -> bool:
    return _FINBERT["ok"]


def reset_finbert_budget() -> None:
    """Reset the per-cycle inference time budget (called per ingest run)."""
    global _FINBERT_SPENT_S
    _FINBERT_SPENT_S = 0.0


def _sentiment_from_probabilities(probabilities: dict[str, float]) -> dict:
    p_pos = probabilities.get("positive", 0.0)
    p_neg = probabilities.get("negative", 0.0)
    p_neu = probabilities.get("neutral", 0.0)
    polarity = max(-1.0, min(1.0, p_pos - p_neg))
    label = "POS" if polarity > 0.15 else ("NEG" if polarity < -0.15 else "NEU")
    confidence = max(p_pos, p_neg, p_neu)
    return {"score": round(polarity, 4), "magnitude": round(confidence, 4),
            "polarity": round(polarity, 4), "confidence": round(confidence, 4),
            "label": label}


def score_text_finbert(text: str) -> dict:
    """
    FinBERT inference, English only. The score is expected polarity:
    P(positive) - P(negative), rather than the winning class probability.
    The winning probability is retained separately as confidence.
    Raises on any failure so callers fall back to the lexicon.
    """
    import torch

    from app.config import settings

    if not _ensure_finbert():
        raise RuntimeError("FinBERT not loaded")
    tokenizer = _FINBERT["tokenizer"]
    model = _FINBERT["model"]

    inputs = tokenizer(
        text, return_tensors="pt", truncation=True,
        max_length=settings.NEWS_FINBERT_MAX_TOKENS,
    )
    t0 = time.monotonic()
    with torch.no_grad():
        logits = model(**inputs).logits[0]
    global _FINBERT_SPENT_S
    _FINBERT_SPENT_S += time.monotonic() - t0
    probs = logits.softmax(dim=-1).tolist()

    id2label = {int(k): str(v).lower() for k, v in model.config.id2label.items()}
    p = {id2label.get(i, f"label_{i}"): float(probs[i]) for i in range(len(probs))}
    return {**_sentiment_from_probabilities(p),
            "spans": [], "language": "en",
            "model": FINBERT_MODEL_VERSION}

_TOKEN_RE = re.compile(r"[\w\u0900-\u097F']+", re.UNICODE)

# term -> weight. Multi-word phrases are matched on the joined text too.
EN_POSITIVE: dict[str, float] = {
    "rally": 1.5, "rallies": 1.5, "surge": 1.5, "surges": 1.5, "soar": 1.5,
    "jump": 1.2, "jumps": 1.2, "gain": 1.0, "gains": 1.0, "beat": 1.5,
    "beats": 1.5, "upgrade": 1.5, "upgraded": 1.5, "outperform": 1.5,
    "bullish": 1.5, "breakout": 1.2, "record profit": 2.0, "strong results": 1.5,
    "profit": 1.0, "growth": 1.0, "approval": 1.0, "order win": 1.5,
    "dividend": 1.0, "buyback": 1.2, "all-time high": 1.5, "rebound": 1.0,
    "optimistic": 1.0, "expansion": 0.8, "merger": 0.5, "acquisition": 0.5,
}

EN_NEGATIVE: dict[str, float] = {
    "plunge": -1.5, "plunges": -1.5, "slump": -1.5, "crash": -2.0,
    "miss": -1.5, "misses": -1.5, "downgrade": -1.5, "downgraded": -1.5,
    "fraud": -2.0, "probe": -1.2, "investigation": -1.2, "default": -2.0,
    "bankruptcy": -2.0, "loss": -1.0, "losses": -1.0, "bearish": -1.5,
    "penalty": -1.2, "fine": -1.0, "scam": -2.0, "selloff": -1.5,
    "sell-off": -1.5, "warning": -1.0, "layoff": -1.0, "strike": -1.0,
    "sebi notice": -1.5, "fire": -0.8, "concern": -0.8, "risk": -0.6,
    "fall": -1.0, "falls": -1.0, "drop": -1.0, "drops": -1.0, "decline": -1.0,
}

HI_POSITIVE: dict[str, float] = {
    "बढ़त": 1.5, "उछाल": 1.5, "मुनाफा": 1.5, "लाभ": 1.2, "तेजी": 1.5,
    "रिकॉर्ड": 1.2, "बढ़िया": 1.0, "नतीजे": 0.5, "अपग्रेड": 1.5,
    "खरीद": 1.0, "डिविडेंड": 1.0, "बायबैक": 1.2, "ऑर्डर": 1.0,
    "मंजूरी": 1.0, "फायदा": 1.0, "मजबूत": 1.0, "ऊपर": 0.6, "चढ़ा": 1.0,
}

HI_NEGATIVE: dict[str, float] = {
    "गिरावट": -1.5, "घाटा": -1.5, "नुकसान": -1.5, "मंदी": -1.5,
    "धोखाधड़ी": -2.0, "जांच": -1.2, "जुर्माना": -1.2, "दिवालिया": -2.0,
    "डिफॉल्ट": -2.0, "घोटाला": -2.0, "दबाव": -0.8, "बिक्री": -1.0,
    "गिरा": -1.0, "गिरे": -1.0, "टूटा": -1.2, "खतरा": -0.8, "चिंता": -0.8,
}

# Transliterated Hindi (Latin script) seen in Indian business headlines.
TRANSLIT_POSITIVE: dict[str, float] = {
    "badhat": 1.2, "uchhal": 1.2, "munafa": 1.2, "tezi": 1.2,
    "record": 1.0, "faayda": 1.0, "majboot": 1.0,
}
TRANSLIT_NEGATIVE: dict[str, float] = {
    "giravat": -1.2, "ghata": -1.2, "nuksan": -1.2, "nuksaan": -1.2,
    "mandi": -1.2, "ghotala": -1.5, "jaanch": -1.0,
}

NEGATIONS = {"not", "no", "never", "n't", "hardly", "barely",
             "नहीं", "न", "ना", "बिना", "मत"}
INTENSIFIERS = {"very", "strong", "sharp", "sharply", "record",
                "बहुत", "भारी", "तेज", "रिकॉर्ड"}

_PHRASES: dict[str, float] = {}
for _d in (EN_POSITIVE, EN_NEGATIVE, HI_POSITIVE, HI_NEGATIVE,
           TRANSLIT_POSITIVE, TRANSLIT_NEGATIVE):
    _PHRASES.update(_d)
# longest-first so "record profit" wins over "record".
_SORTED_PHRASES = sorted(_PHRASES.items(), key=lambda kv: -len(kv[0]))


def detect_language(text: str) -> str:
    """'hi' if any Devanagari codepoint present, else 'en'."""
    return "hi" if re.search(r"[\u0900-\u097F]", text) else "en"


def score_text(text: str) -> dict:
    """
    Score free text. Returns {score, magnitude, label, spans, language}.
    Deterministic and dependency-free.
    """
    lowered = text.lower()
    language = detect_language(text)
    tokens = _TOKEN_RE.findall(lowered)

    total = 0.0
    abs_total = 0.0
    spans: list[str] = []
    negate_left = 0
    boost_next = False

    # Phrase pass (multi-word terms like "record profit", "sebi notice").
    phrase_hits: list[tuple[str, float]] = []
    for phrase, weight in _SORTED_PHRASES:
        if " " in phrase and phrase in lowered:
            phrase_hits.append((phrase, weight))
            lowered = lowered.replace(phrase, " ", 1)  # avoid double count
    tokens = _TOKEN_RE.findall(lowered)

    single = {**EN_POSITIVE, **EN_NEGATIVE, **HI_POSITIVE, **HI_NEGATIVE,
              **TRANSLIT_POSITIVE, **TRANSLIT_NEGATIVE}

    def apply(weight: float, evidence: str) -> None:
        nonlocal total, abs_total, boost_next
        if negate_left > 0:
            weight = -weight
        if boost_next:
            weight *= 1.5
            boost_next = False
        total += weight
        abs_total += abs(weight)
        spans.append(evidence)

    for phrase, weight in phrase_hits:
        apply(weight, phrase)

    for i, tok in enumerate(tokens):
        if tok in NEGATIONS:
            negate_left = 3
            continue
        if tok in INTENSIFIERS:
            boost_next = True
            continue
        weight = single.get(tok)
        if weight is not None:
            ctx = " ".join(tokens[max(0, i - 2): i + 3])
            apply(weight, ctx)
        if negate_left > 0:
            negate_left -= 1

    if abs_total == 0:
        return {"score": 0.0, "magnitude": 0.0, "label": "NEU",
                "spans": [], "language": language}

    score = max(-1.0, min(1.0, total / (abs_total + 3.0)))
    magnitude = min(1.0, abs_total / 6.0)
    label = "POS" if score > 0.15 else ("NEG" if score < -0.15 else "NEU")
    return {"score": round(score, 4), "magnitude": round(magnitude, 4),
            "label": label, "spans": spans[:5], "language": language}


def score_article(title: str, body: str = "") -> dict:
    """Title counts 2x — headlines carry the signal in RSS feeds."""
    t = score_text(title or "")
    if not body:
        return {**t, "polarity": t["score"], "confidence": t["magnitude"],
                "model": MODEL_VERSION}
    b = score_text(body)
    combined = (t["score"] * 2 + b["score"]) / 3
    magnitude = min(1.0, max(t["magnitude"], b["magnitude"]))
    label = "POS" if combined > 0.15 else ("NEG" if combined < -0.15 else "NEU")
    return {"score": round(max(-1.0, min(1.0, combined)), 4),
            "magnitude": round(magnitude, 4), "label": label,
            "spans": (t["spans"] + b["spans"])[:5],
            "language": t["language"], "polarity": round(max(-1.0, min(1.0, combined)), 4),
            "confidence": round(magnitude, 4), "model": MODEL_VERSION}


def score_article_hybrid(title: str, body: str = "", budget_s: float = 120.0) -> dict:
    """
    Production router: EN -> FinBERT, HI -> lexicon, FinBERT failure
    or exhausted time budget -> lexicon. Always returns the output
    contract (never raises).
    """
    text = f"{title or ''} {body or ''}".strip()
    lang = detect_language(text)
    if lang == "en":
        try:
            if _FINBERT_SPENT_S < budget_s:
                out = score_text_finbert(f"{title or ''}. {body or ''}".strip() or title)
                out["language"] = "en"
                return out
        except Exception as exc:
            logger.debug("FinBERT miss, lexicon fallback: %s", exc)
    out = score_article(title, body)
    out["language"] = lang
    return out
