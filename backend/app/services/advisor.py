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
    market = context.get("market_snapshot") or {}
    news_signal = context.get("news_signal") or {}
    trend = market.get("daily_trend", "unknown")
    quote = market.get("cached_quote")
    rsi = market.get("rsi_14")
    score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else "unavailable"
    conditions = (
        f"Daily trend: {trend}; RSI(14): {rsi if rsi is not None else 'unavailable'}; "
        f"news sentiment: {sentiment} ({score_text}); "
        f"1-hour signal: {news_signal.get('status', 'unavailable')} "
        f"(score {news_signal.get('score', 'unavailable')}, "
        f"impact {news_signal.get('impact', 'unavailable')})."
    )
    if quote is None:
        action = "Stay flat. A fresh cached quote is unavailable; re-check during market hours."
        risk = "Do not enter without a current quote and a defined stop/invalidation level."
        reason = "The available news and historical bars are insufficient to validate a live entry."
        confidence = "Low — current quote unavailable."
    elif news_signal.get("status") != "available":
        action = "Stay flat. A sufficiently corroborated 1-hour news signal is unavailable."
        risk = "Wait for the minimum article count and a refreshed cached quote before considering a position."
        reason = "A missing or quiet aggregate signal is not evidence of a positive or negative catalyst."
        confidence = "Low — insufficient corroborated news."
    elif trend == "bullish" and sentiment == "POS":
        if float(news_signal.get("score") or 0) < 0.2:
            action = "Wait for confirmation; the aggregate news signal does not confirm the positive article sentiment."
            risk = "Stay flat until the 1-hour signal and daily trend align."
            reason = "Recent article sentiment and the aggregate 1-hour news signal are not sufficiently aligned."
            confidence = "Low — news confirmation is missing."
        else:
            action = "Consider a small paper BUY only after price confirms above a defined trigger; user confirmation required."
            risk = "Place a stop below the recent swing low; size conservatively and skip if price loses SMA(20)."
            reason = "The cached quote is available and the latest stored daily-bar trend and corroborated news sentiment align bullishly."
            confidence = "Low — trend/news alignment is not a price prediction."
    elif trend == "bearish" and sentiment == "NEG":
        if float(news_signal.get("score") or 0) > -0.2:
            action = "Wait for confirmation; the aggregate news signal does not confirm the negative article sentiment."
            risk = "Stay flat until the 1-hour signal and daily trend align."
            reason = "Recent article sentiment and the aggregate 1-hour news signal are not sufficiently aligned."
            confidence = "Low — news confirmation is missing."
        else:
            action = "Avoid new longs; consider a paper SELL only after downside confirmation and user review."
            risk = "Define a stop above the recent swing high; avoid short exposure if the instrument or account cannot support it."
            reason = "The latest stored daily-bar trend and corroborated news sentiment align bearishly, but the setup needs confirmation."
            confidence = "Low — trend/news alignment is not a price prediction."
    else:
        action = "Wait for confirmation; do not open a position while the news and daily trend are mixed or unavailable."
        risk = "Stay flat until a current quote, directional confirmation, and a clear invalidation level are available."
        reason = "The current evidence does not show aligned news sentiment and daily trend."
        confidence = "Low — no aligned setup."
    return (
        "Strategy Name: News + Trend Confirmation\n"
        f"Market/Event: {headline}\n"
        f"Symbol: {ticker}\n"
        f"Sector: {sector}\n"
        f"Market snapshot: cached quote ₹{quote if quote is not None else 'unavailable'}; "
        f"daily trend from stored OHLCV bars {trend}; RSI(14) {rsi if rsi is not None else 'unavailable'}; "
        f"1-hour news signal {news_signal.get('status', 'unavailable')}.\n"
        f"Conditions: {conditions}\n"
        f"Action: {action}\n"
        f"Risk Management: {risk}\n"
        f"Reason: {reason}\n"
        f"Confidence: {confidence}\n"
        "This is advisory-only paper-trading guidance, not a guaranteed forecast or financial advice. "
        "No order is placed; review and confirm any trade yourself."
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
        "Use only the supplied news intelligence, cached quote, and latest available daily-bar indicators. "
        "Do not claim you have any other live data, and explicitly call the quote cached. "
        "If the quote or corroborated 1-hour news signal is unavailable/quiet, or trend/news conflict, "
        "recommend WAIT/STAY FLAT, not a forced trade. Treat impact band and explanation as context, not certainty. "
        "If strategy or portfolio context is provided, account for it without treating it as a command to trade. "
        "Generate 1-3 implementable paper-trading strategy ideas that can be mapped to the existing strategy builder. "
        "For each idea include: Strategy Name, Market/Event, Symbol, Sector, Conditions, "
        "Action, Risk Management, Reason, Confidence. State that this is a paper-trading idea, "
        "not guaranteed financial advice. No order may be placed; require human confirmation. "
        "If information is missing, clearly say it is unavailable. "
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
