"""Build a compact market snapshot for on-demand strategy advice."""

from decimal import Decimal

import pandas as pd

from app.utils.indicators import compute_indicator


def build_market_snapshot(ticker: str, cached_price: Decimal | None, bars: pd.DataFrame) -> dict:
    snapshot = {
        "ticker": ticker.strip().upper(),
        "cached_quote": float(cached_price) if cached_price is not None else None,
        "quote_status": "available" if cached_price is not None else "unavailable",
        "quote_note": (
            "Latest cached quote; it may be unavailable outside market hours."
            if cached_price is not None
            else "No cached quote is available. Do not recommend an entry until a quote is available."
        ),
        "daily_trend": "unknown",
        "daily_change_pct": None,
        "rsi_14": None,
        "sma_20": None,
        "sma_50": None,
        "last_daily_bar_at": None,
    }
    if bars is None or bars.empty:
        snapshot["history_status"] = "unavailable"
        return snapshot

    closes = bars["close"]
    snapshot["history_status"] = "available"
    snapshot["last_daily_bar_at"] = pd.Timestamp(bars.index[-1]).isoformat()
    if len(closes) >= 2 and float(closes.iloc[-2]) != 0:
        snapshot["daily_change_pct"] = round(
            (float(closes.iloc[-1]) / float(closes.iloc[-2]) - 1) * 100, 3
        )

    rsi = compute_indicator(bars, "RSI", {"period": 14}).iloc[-1]
    sma_20 = compute_indicator(bars, "SMA", {"period": 20}).iloc[-1]
    sma_50 = compute_indicator(bars, "SMA", {"period": 50}).iloc[-1]
    snapshot["rsi_14"] = round(float(rsi), 2) if pd.notna(rsi) else None
    snapshot["sma_20"] = round(float(sma_20), 2) if pd.notna(sma_20) else None
    snapshot["sma_50"] = round(float(sma_50), 2) if pd.notna(sma_50) else None

    close = float(closes.iloc[-1])
    if snapshot["sma_20"] is not None and snapshot["sma_50"] is not None:
        if close > snapshot["sma_20"] > snapshot["sma_50"]:
            snapshot["daily_trend"] = "bullish"
        elif close < snapshot["sma_20"] < snapshot["sma_50"]:
            snapshot["daily_trend"] = "bearish"
        else:
            snapshot["daily_trend"] = "mixed"
    return snapshot
