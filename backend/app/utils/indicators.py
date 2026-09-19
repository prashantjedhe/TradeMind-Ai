"""
app/utils/indicators.py

Technical indicator engine for TradeMind AI strategy evaluation.

All functions take a pandas Series/DataFrame of OHLCV bars (columns:
open, high, low, close, volume; indexed by timestamp, sorted
ascending) and return a pandas Series (or DataFrame for MACD)
aligned to that index.

Standards locked for consistency with TradingView / Zerodha Kite:
- RSI  : Wilder's original 1978 smoothing -- SEEDED with a simple
         average of the first `period` gains/losses, THEN recursive
         smoothing after that. A plain `.ewm(alpha=1/period,
         adjust=False)` from bar 0 (a common shortcut, used by some
         libraries) is NOT equivalent and diverges from TradingView.
- EMA  : adjust=False. pandas' default (adjust=True) weights early
         bars differently and will NOT match TradingView/Kite.
- MACD : fast EMA - slow EMA; signal = EMA(signal) of the MACD line,
         same adjust=False convention throughout (MACD's signal EMA
         is a plain EMA, not Wilder-seeded like RSI).

Indicators return NaN during warm-up rather than raising, so one
illiquid/new ticker doesn't crash the Celery evaluator loop for
every other strategy. Callers MUST check min_bars_required() first.
"""

from __future__ import annotations
import pandas as pd
import numpy as np
from typing import Optional


# ── Simple Moving Average ─────────────────────────────────────────
def sma(series: pd.Series, period: int) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return series.rolling(window=period, min_periods=period).mean()


# ── Exponential Moving Average ────────────────────────────────────
def ema(series: pd.Series, period: int) -> pd.Series:
    if period < 1:
        raise ValueError("period must be >= 1")
    return series.ewm(span=period, adjust=False, min_periods=period).mean()


# ── RSI (Wilder's smoothing) ──────────────────────────────────────
def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    True Wilder RSI: the first avg_gain/avg_loss is a SIMPLE AVERAGE
    of the first `period` gains/losses, and only bars AFTER that seed
    use the recursive smoothing formula.

    This is NOT the same as a plain `.ewm(alpha=1/period, adjust=False)`
    applied to the whole series from bar 0 -- that shortcut (used by
    several popular libraries, including 'ta') runs the recursion from
    the very first bar and diverges from Wilder's book definition and
    from TradingView's documented ta.rma() behavior for a meaningful
    number of bars after warm-up (empirically 10-15+ RSI points off
    near the seed point). Since matching TradingView/Kite is the
    correctness target here, this explicit-seed version is required,
    not the shortcut.
    """
    if period < 1:
        raise ValueError("period must be >= 1")

    delta = series.diff()
    gain = delta.clip(lower=0).fillna(0.0).to_numpy()
    loss = (-delta.clip(upper=0)).fillna(0.0).to_numpy()
    n = len(series)

    values = np.full(n, np.nan)
    if n <= period:
        return pd.Series(values, index=series.index)

    # Seed: simple average of the first `period` gains/losses.
    # gain/loss[0] is always 0 (diff() at bar 0 is NaN -> filled 0),
    # so the real first `period` deltas are gain/loss[1 : period+1].
    avg_gain = gain[1:period + 1].mean()
    avg_loss = loss[1:period + 1].mean()
    values[period] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    # Recursive Wilder smoothing for every bar after the seed.
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gain[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss[i]) / period
        values[i] = 100.0 if avg_loss == 0 else 100 - (100 / (1 + avg_gain / avg_loss))

    return pd.Series(values, index=series.index)


# ── MACD ───────────────────────────────────────────────────────────
def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    if fast >= slow:
        raise ValueError("fast period must be < slow period")

    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line

    return pd.DataFrame({
        "macd": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    })


# ── Volume moving average ─────────────────────────────────────────
def volume_sma(volume: pd.Series, period: int) -> pd.Series:
    return sma(volume, period)


# ── Warm-up guard ──────────────────────────────────────────────────
def min_bars_required(indicator: str, params: dict) -> int:
    """
    Minimum bars needed before this indicator's value is trustworthy.
    EMA/RSI never mathematically converge, so we use 3x period as the
    practical warm-up floor (Wilder's own rule of thumb) rather than
    the bare minimum pandas needs to stop returning NaN.
    """
    if indicator == "SMA":
        return params.get("period", 14)
    if indicator in ("EMA", "RSI"):
        return params.get("period", 14) * 3
    if indicator in ("MACD", "MACD_SIGNAL", "MACD_HIST"):
        slow = params.get("slow", 26)
        signal = params.get("signal", 9)
        return (slow + signal) * 3
    if indicator == "VOLUME":
        return params.get("period", 20)
    if indicator == "PRICE":
        return 1
    if indicator == "SENTIMENT":
        # Signal snapshots land every 5m; 2 points suffice for edge ops.
        return 2
    raise ValueError(f"Unknown indicator: {indicator}")


# ── Dispatcher ─────────────────────────────────────────────────────
def compute_indicator(df: pd.DataFrame, indicator: str, params: Optional[dict] = None) -> pd.Series:
    """
    df must have columns: open, high, low, close, volume.
    Mirrors the IndicatorRef literal in app/schemas/strategy.py --
    keep both in sync if a new indicator type is added.

    SENTIMENT is NOT computed from OHLCV -- the strategy evaluator
    loads its series from news_signals instead. Calling this with
    SENTIMENT raises; the evaluator branches before reaching here.
    """
    params = params or {}

    if indicator == "SENTIMENT":
        raise ValueError("SENTIMENT has no OHLCV series -- load via news_signal_service")

    if indicator == "PRICE":
        return df["close"]
    if indicator == "SMA":
        return sma(df["close"], params.get("period", 14))
    if indicator == "EMA":
        return ema(df["close"], params.get("period", 14))
    if indicator == "RSI":
        return rsi(df["close"], params.get("period", 14))
    if indicator == "VOLUME":
        return volume_sma(df["volume"], params.get("period", 20))

    if indicator in ("MACD", "MACD_SIGNAL", "MACD_HIST"):
        m = macd(
            df["close"],
            fast=params.get("fast", 12),
            slow=params.get("slow", 26),
            signal=params.get("signal", 9),
        )
        col = {"MACD": "macd", "MACD_SIGNAL": "signal", "MACD_HIST": "histogram"}[indicator]
        return m[col]

    raise ValueError(f"Unknown indicator: {indicator}")
