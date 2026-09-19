"""
OHLCV historical bar fetching and storage.

Design notes:
- yfinance's historical data depth differs by interval: daily (1d)
  bars go back years, but intraday (15m) bars are only available for
  roughly the last 60 days - a real Yahoo Finance limitation, not a
  choice we made. Callers should request periods within these limits.
- Upserts use Postgres ON CONFLICT DO NOTHING against the
  (ticker, interval, timestamp) unique constraint, so re-running a
  sync is always safe and never creates duplicate bars.
"""

import logging
from datetime import datetime, timezone
from decimal import Decimal

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ohlcv import OHLCVBar, BarInterval
from app.utils.market_data import to_nse_ticker

logger = logging.getLogger(__name__)

PRICE_QUANTIZE = Decimal("0.01")

# Max lookback yfinance actually supports per interval (real constraint,
# not a design choice). Requesting more than this returns truncated data.
MAX_PERIOD_BY_INTERVAL = {
    BarInterval.ONE_DAY: "5y",
    BarInterval.FIFTEEN_MIN: "60d",
}


def _quantize_price(value) -> Decimal:
    return Decimal(str(value)).quantize(PRICE_QUANTIZE)


def fetch_historical_bars(ticker: str, interval: BarInterval, period: str | None = None) -> list[dict]:
    """
    Fetch historical OHLCV bars from yfinance for a single ticker.
    Returns a list of dicts ready for DB insertion. Returns an empty
    list (never raises) on any fetch failure - callers should log
    and move on to the next ticker rather than aborting a whole sync.
    """
    nse_ticker = to_nse_ticker(ticker)
    actual_period = period or MAX_PERIOD_BY_INTERVAL[interval]

    try:
        stock = yf.Ticker(nse_ticker)
        df = stock.history(period=actual_period, interval=interval.value)

        if df.empty:
            logger.warning("No historical data returned for %s (%s)", nse_ticker, interval.value)
            return []

        bars = []
        for ts, row in df.iterrows():
            # yfinance returns tz-aware timestamps already; normalize to UTC.
            ts_utc = ts.to_pydatetime().astimezone(timezone.utc)
            bars.append({
                "ticker": ticker.strip().upper(),
                "interval": interval,
                "timestamp": ts_utc,
                "open": _quantize_price(row["Open"]),
                "high": _quantize_price(row["High"]),
                "low": _quantize_price(row["Low"]),
                "close": _quantize_price(row["Close"]),
                "volume": int(row["Volume"]),
            })
        return bars

    except Exception as exc:
        logger.error("Failed to fetch historical bars for %s (%s): %s", nse_ticker, interval.value, exc)
        return []


async def upsert_bars(db: AsyncSession, bars: list[dict]) -> int:
    """
    Insert bars, skipping any that already exist (same ticker+interval+
    timestamp). Returns the number of NEW rows actually inserted.
    """
    if not bars:
        return 0

    stmt = pg_insert(OHLCVBar).values(bars)
    stmt = stmt.on_conflict_do_nothing(constraint="uq_ohlcv_ticker_interval_ts")
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def load_bars_dataframe(db: AsyncSession, ticker: str, interval: BarInterval, limit: int = 250) -> pd.DataFrame:
    """
    Load the most recent `limit` OHLCV bars for a ticker/interval into
    a pandas DataFrame sorted ascending by timestamp (the format the
    strategy condition evaluator expects). Returns an empty DataFrame
    when no bars exist yet.
    """
    result = await db.execute(
        select(OHLCVBar)
        .where(OHLCVBar.ticker == ticker.strip().upper(), OHLCVBar.interval == interval)
        .order_by(OHLCVBar.timestamp.desc())
        .limit(limit)
    )
    bars = list(reversed(result.scalars().all()))

    if not bars:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])

    return pd.DataFrame(
        {
            "open": [float(b.open) for b in bars],
            "high": [float(b.high) for b in bars],
            "low": [float(b.low) for b in bars],
            "close": [float(b.close) for b in bars],
            "volume": [int(b.volume) for b in bars],
        },
        index=pd.DatetimeIndex([b.timestamp for b in bars], name="timestamp"),
    )


async def load_bars_range(
    db: AsyncSession,
    ticker: str,
    interval: BarInterval,
    start: datetime | None = None,
    end: datetime | None = None,
) -> pd.DataFrame:
    """
    Load every stored bar for ticker/interval, optionally bounded.
    Used by the backtester so date filters are real, not 'last N bars'.
    """
    stmt = select(OHLCVBar).where(
        OHLCVBar.ticker == ticker.strip().upper(),
        OHLCVBar.interval == interval,
    )
    if start is not None:
        stmt = stmt.where(OHLCVBar.timestamp >= start)
    if end is not None:
        stmt = stmt.where(OHLCVBar.timestamp <= end)
    stmt = stmt.order_by(OHLCVBar.timestamp.asc())
    result = await db.execute(stmt)
    bars = list(result.scalars().all())
    if not bars:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    return pd.DataFrame(
        {
            "open": [float(b.open) for b in bars],
            "high": [float(b.high) for b in bars],
            "low": [float(b.low) for b in bars],
            "close": [float(b.close) for b in bars],
            "volume": [int(b.volume) for b in bars],
        },
        index=pd.DatetimeIndex([b.timestamp for b in bars], name="timestamp"),
    )
