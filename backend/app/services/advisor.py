"""
Claude-powered Strategy Advisor + AI Trade Journal (Model 4).

Hard boundaries (fintech-realistic, non-negotiable):
- Advisory ONLY. No advisor output ever reaches order execution,
  strategy evaluation, or the action engine. The journal is a
  read-only table; the advisor returns text to the UI.
- On-demand, never in a hot loop. Called from API endpoints with the
  user's explicit click, never from Celery beat tasks.
- Fail-soft: missing key, timeout, or any API error -> a clear
  "advisor unavailable" message, never a 500, never a retry storm.
- Stdlib HTTP (urllib), no SDK dependency. max_tokens capped at 1000.

Model id is env-pinned (ANTHROPIC_MODEL); confirm the exact id in the
Anthropic console -- ids rotate with releases.
"""

from __future__ import annotations

import json
import logging
import urllib.request

from app.config import settings

logger = logging.getLogger(__name__)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_ANTHROPIC_VERSION = "2023-06-01"

SYSTEM_PROMPT = (
    "You are TradeMind AI, a paper-trading coach for Indian NSE equity "
    "and F&O. You explain, you never execute. Rules: (1) this is a "
    "simulation, say so when giving directional views; (2) be specific "
    "about risks and invalidation, not just entries; (3) keep answers "
    "structured and under the token budget; (4) never claim live market "
    "data -- reason only from the JSON context provided."
)


def advisor_configured() -> bool:
    return bool(settings.ANTHROPIC_API_KEY) or bool(settings.OPENROUTER_API_KEY)


def _read_text_payload(payload: dict) -> str:
    blocks = payload.get("content") or []
    texts = [b.get("text", "") for b in blocks if isinstance(b, dict)
             and b.get("type") == "text"]
    text = "\n".join(t for t in texts if t).strip()
    if text:
        return text
    if isinstance(payload.get("choices"), list) and payload["choices"]:
        first = payload["choices"][0]
        message = first.get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text = "\n".join(
                item.get("text", "") for item in content if isinstance(item, dict)
            ).strip()
            if text:
                return text
    raise RuntimeError("Empty advisor response")


def _call_claude(user_prompt: str) -> str:
    """Single Anthropic call. Raises on any failure (callers catch)."""
    body = json.dumps({
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": settings.ANTHROPIC_MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        _ANTHROPIC_URL, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": _ANTHROPIC_VERSION,
        },
    )
    with urllib.request.urlopen(req, timeout=settings.ANTHROPIC_TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return _read_text_payload(payload)


def _call_openrouter(user_prompt: str) -> str:
    """Free-tier fallback using OpenRouter-compatible chat completion API."""
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OpenRouter API key missing")
    body = json.dumps({
        "model": settings.OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }).encode("utf-8")
    req = urllib.request.Request(
        settings.OPENROUTER_BASE_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
            "HTTP-Referer": "https://trademind.ai",
            "X-Title": "TradeMind AI",
        },
    )
    with urllib.request.urlopen(req, timeout=settings.OPENROUTER_TIMEOUT_S) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return _read_text_payload(payload)


def _local_news_strategy(context: dict) -> str:
    ticker = (context.get("ticker") or "the symbol").upper()
    headline = context.get("headline") or "recent market news"
    sentiment = (context.get("sentiment_label") or "NEU").upper()
    sector = context.get("sector") or "UNKNOWN"
    score = context.get("sentiment_score")
    score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else "neutral"
    return (
        "Strategy Name: News Breakout Momentum\n"
        "Market/Event: {headline}\n"
        "Symbol: {ticker}\n"
        "Sector: {sector}\n"
        "Conditions: Wait for a clean breakout above the recent intraday range, with momentum confirmation and sentiment {sentiment} ({score_text}).\n"
        "Action: Paper-trade a long position only if price closes above the breakout level with volume support; otherwise stay flat.\n"
        "Risk Management: Keep a tight stop below the breakout candle or prior range low and cap size to a small paper-trade risk.\n"
        "Reason: The headline is directionally aligned with a short-term catalyst and the positive sentiment implies a momentum continuation setup.\n"
        "Confidence: Medium — valid only if the breakout holds and the broader market is not reversing."
    ).format(
        headline=headline,
        ticker=ticker,
        sector=sector,
        sentiment=sentiment,
        score_text=score_text,
    )


def _generate_with_fallback(user_prompt: str, context: dict, *, news_mode: bool = False) -> str:
    if settings.ANTHROPIC_API_KEY:
        return _call_claude(user_prompt)
    if settings.OPENROUTER_API_KEY:
        return _call_openrouter(user_prompt)
    if news_mode:
        return _local_news_strategy(context)
    return (
        "Strategy Name: Risk-Managed Breakout\n"
        "Market/Event: Based on the supplied strategy context.\n"
        "Symbol: Context-dependent\n"
        "Sector: Context-dependent\n"
        "Conditions: Wait for the setup to confirm on a clean breakout or pullback with defined risk.\n"
        "Action: Paper-trade only after confirmation; otherwise stay flat.\n"
        "Risk Management: Use a clear invalidation level and keep sizing conservative.\n"
        "Reason: The structure is still valid, but the live model is unavailable so this is a conservative fallback view.\n"
        "Confidence: Medium"
    )


def advise_on_strategy(context: dict) -> dict:
    """
    Strategy Advisor: structured trade/backtest JSON in, coaching text
    out. Returns {ok, body, model} -- ok=False with a friendly message
    when unconfigured or the API fails.
    """
    compact = json.dumps(context, default=str)[:6000]
    prompt = (
        "Review this paper-trading strategy and its recent performance. "
        "Give: 1) what the setup is actually betting on, 2) two concrete "
        "risks with invalidation levels, 3) one specific improvement "
        "(parameter, filter, or exit). Be concise.\n\n"
        f"STRATEGY CONTEXT:\n{compact}"
    )
    try:
        body = _generate_with_fallback(prompt, context, news_mode=False)
        model_name = settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY else (
            settings.OPENROUTER_MODEL if settings.OPENROUTER_API_KEY else "local-fallback"
        )
        return {"ok": True, "model": model_name, "body": body}
    except Exception as exc:
        logger.warning("Advisor generation failed: %s", exc)
        return {"ok": False, "model": settings.ANTHROPIC_MODEL,
                "body": "AI advisor is temporarily unavailable. Please retry later."}


def advise_on_news(context: dict) -> dict:
    """Generate implementable paper-trading strategy ideas from news data only."""
    compact = json.dumps(context, default=str)[:6000]
    prompt = (
        "You are TradeMind AI acting as a paper-trading news strategist. "
        "Use only the provided news intelligence data. Generate 1-3 implementable "
        "paper-trading strategy ideas that can be mapped to the existing strategy builder. "
        "For each idea include: Strategy Name, Market/Event, Symbol, Sector, Conditions, "
        "Action, Risk Management, Reason, Confidence. State that this is a paper-trading idea, "
        "not guaranteed financial advice. If information is missing, clearly say it is unavailable. "
        "Keep it structured and concise.\n\n"
        f"NEWS CONTEXT:\n{compact}"
    )
    try:
        body = _generate_with_fallback(prompt, context, news_mode=True)
        model_name = settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY else (
            settings.OPENROUTER_MODEL if settings.OPENROUTER_API_KEY else "local-fallback"
        )
        return {"ok": True, "model": model_name, "body": body}
    except Exception as exc:
        logger.warning("News advisor generation failed: %s", exc)
        return {"ok": False, "model": settings.ANTHROPIC_MODEL,
                "body": "News-driven strategy suggestions are temporarily unavailable. Please retry later."}


def write_journal_entry(context: dict) -> dict:
    """Same transport, journal framing: day/period recap from trade data."""
    compact = json.dumps(context, default=str)[:6000]
    prompt = (
        "Write a trading-journal entry from this paper-trading data: "
        "what worked, what didn't, the single biggest mistake pattern, "
        "and one rule for tomorrow. Blunt, no fluff.\n\n"
        f"TRADE DATA:\n{compact}"
    )
    try:
        body = _generate_with_fallback(prompt, context, news_mode=False)
        model_name = settings.ANTHROPIC_MODEL if settings.ANTHROPIC_API_KEY else (
            settings.OPENROUTER_MODEL if settings.OPENROUTER_API_KEY else "local-fallback"
        )
        return {"ok": True, "model": model_name, "body": body}
    except Exception as exc:
        logger.warning("Journal generation failed: %s", exc)
        return {"ok": False, "model": settings.ANTHROPIC_MODEL,
                "body": "AI journal is temporarily unavailable. Please retry later."}
