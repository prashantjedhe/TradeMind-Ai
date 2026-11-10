import numpy as np
import pandas as pd
import pytest

from app.utils.indicators import sma, ema, rsi, macd, volume_sma


@pytest.fixture
def sample_price_series():
    # 50 days of deterministic price movement
    np.random.seed(42)
    base = 100.0
    returns = np.random.normal(0.001, 0.02, 50)
    prices = base * np.cumprod(1 + returns)
    dates = pd.date_range("2026-01-01", periods=50, freq="D")
    return pd.Series(prices, index=dates)


def test_sma_calculation(sample_price_series):
    period = 10
    ma = sma(sample_price_series, period)
    # First (period - 1) bars must be NaN
    assert ma.iloc[:period - 1].isna().all()
    # 10th bar must match simple mean
    expected = sample_price_series.iloc[:period].mean()
    assert np.isclose(ma.iloc[period - 1], expected)


def test_ema_calculation(sample_price_series):
    period = 12
    em = ema(sample_price_series, period)
    assert em.iloc[:period - 1].isna().all()
    assert not np.isnan(em.iloc[period - 1])
    assert len(em) == len(sample_price_series)


def test_rsi_range_bounds(sample_price_series):
    rsi_vals = rsi(sample_price_series, 14)
    valid_rsi = rsi_vals.dropna()
    # RSI must strictly lie between 0 and 100
    assert (valid_rsi >= 0.0).all()
    assert (valid_rsi <= 100.0).all()


def test_macd_structure(sample_price_series):
    df_macd = macd(sample_price_series, fast=12, slow=26, signal=9)
    assert "macd" in df_macd.columns
    assert "signal" in df_macd.columns
    assert "histogram" in df_macd.columns
    # Histogram must equal macd - signal
    valid = df_macd.dropna()
    diff = (valid["macd"] - valid["signal"]) - valid["histogram"]
    assert np.isclose(diff, 0.0).all()
