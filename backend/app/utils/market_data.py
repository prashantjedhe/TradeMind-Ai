"""
Market data client for fetching NSE stock prices via yFinance.

Design notes:
- All NSE tickers must use the .NS suffix (e.g. "RELIANCE.NS").
- yfinance >= 1.x manages curl_cffi browser impersonation internally
  to reduce Yahoo Finance's bot-detection rate limiting (429 errors).
  We deliberately do NOT pass a manual session - yfinance handles
  this itself, and manually overriding it causes internal errors.
- yfinance returns prices as Python floats, which can carry binary
  floating-point noise (e.g. 1327.199951171875 instead of 1327.20).
  We quantize to 2 decimal places (NSE trades in paise) immediately
  on ingest, so no float noise ever enters the rest of the system.
- This module does NOT cache; caching is handled by the Celery task
  that calls this module and writes to Redis. Keeping this module
  pure I/O makes it independently testable.
- Returns None on any failure rather than raising - callers must
  treat None as "no price available" and must NOT execute orders
  against a None price.
"""

import logging
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import yfinance as yf

logger = logging.getLogger(__name__)

NSE_SUFFIX = ".NS"
PRICE_QUANTIZE = Decimal("0.01")  # 2 decimal places (paise)


def to_nse_ticker(ticker: str) -> str:
    """Ensure a ticker has the .NS suffix for NSE lookups."""
    ticker = ticker.strip().upper()
    if ticker == "NIFTY":
        return "^NSEI"
    if ticker == "BANKNIFTY":
        return "^NSEBANK"
    if not ticker.endswith(NSE_SUFFIX):
        ticker = f"{ticker}{NSE_SUFFIX}"
    return ticker


def _clean_price(raw_price: float) -> Decimal:
    """
    Convert a raw float price from yfinance into a clean Decimal
    rounded to 2 decimal places, eliminating binary float noise.
    """
    return Decimal(str(raw_price)).quantize(PRICE_QUANTIZE, rounding=ROUND_HALF_UP)


def fetch_latest_price(ticker: str) -> Decimal | None:
    """
    Fetch the latest traded price for a single NSE ticker.

    Returns None if the price could not be fetched (network issue,
    invalid ticker, market data unavailable, rate limited) rather
    than raising - callers must handle None explicitly.
    """
    nse_ticker = to_nse_ticker(ticker)
    try:
        stock = yf.Ticker(nse_ticker)
        price = stock.fast_info.get("lastPrice")

        if price is None:
            logger.warning("No lastPrice returned for %s", nse_ticker)
            return None

        return _clean_price(price)

    except (InvalidOperation, ValueError) as exc:
        logger.error("Invalid price value for %s: %s", nse_ticker, exc)
        return None
    except Exception as exc:
        logger.error("Failed to fetch price for %s: %s", nse_ticker, exc)
        return None


def fetch_latest_prices(tickers: list[str]) -> dict[str, Decimal | None]:
    """
    Fetch latest prices for multiple tickers.

    Each ticker is fetched independently so a single failure doesn't
    block the rest of the batch.
    """
    results: dict[str, Decimal | None] = {}
    for ticker in tickers:
        results[ticker] = fetch_latest_price(ticker)
    return results
