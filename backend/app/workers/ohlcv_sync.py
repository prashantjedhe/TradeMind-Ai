"""
OHLCV historical bar sync tasks.

Two distinct jobs:
1. backfill_all_history() - a ONE-TIME deep historical pull (called
   manually, not on a schedule) across the full watchlist, for both
   daily and 15-min intervals, using each interval's maximum
   supported lookback period.
2. sync_recent_bars (Celery task) - lightweight ONGOING sync that
   runs on a schedule, fetching only a small recent window per
   interval, to catch new bars as they form. Kept lightweight
   deliberately, since yfinance/Yahoo Finance rate-limits aggressive
   request patterns (a real constraint we hit and solved earlier in
   this project for live price fetching).
"""

import asyncio
import logging

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.ohlcv import BarInterval
from app.services.ohlcv_service import fetch_historical_bars, upsert_bars, MAX_PERIOD_BY_INTERVAL
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Small, recent-only windows for the ongoing sync task - NOT the full
# historical depth (that's what backfill_all_history is for).
RECENT_SYNC_PERIOD = {
    BarInterval.ONE_DAY: "5d",
    BarInterval.FIFTEEN_MIN: "1d",
}


async def _sync_tickers(tickers: list[str], intervals: list[BarInterval], period_map: dict) -> dict:
    total_fetched = 0
    total_inserted = 0
    failed_tickers = []

    async with AsyncSessionLocal() as db:
        for ticker in tickers:
            for interval in intervals:
                period = period_map[interval]
                bars = fetch_historical_bars(ticker, interval, period=period)

                if not bars:
                    failed_tickers.append(f"{ticker}:{interval.value}")
                    continue

                inserted = await upsert_bars(db, bars)
                total_fetched += len(bars)
                total_inserted += inserted

    return {
        "tickers_processed": len(tickers),
        "total_fetched": total_fetched,
        "total_inserted": total_inserted,
        "failed": failed_tickers,
    }


async def backfill_all_history() -> dict:
    """
    ONE-TIME deep historical backfill for the full watchlist, both
    intervals, using maximum available lookback per interval.
    Call this manually (not scheduled) when setting up OHLCV storage
    for the first time, or if you need to re-backfill after adding
    new tickers to the watchlist.
    """
    try:
        return await _sync_tickers(
            tickers=settings.WATCHLIST_TICKERS,
            intervals=[BarInterval.ONE_DAY, BarInterval.FIFTEEN_MIN],
            period_map=MAX_PERIOD_BY_INTERVAL,
        )
    finally:
        await engine.dispose()


async def _sync_recent() -> dict:
    try:
        return await _sync_tickers(
            tickers=settings.WATCHLIST_TICKERS,
            intervals=[BarInterval.ONE_DAY, BarInterval.FIFTEEN_MIN],
            period_map=RECENT_SYNC_PERIOD,
        )
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.ohlcv_sync.sync_recent_bars")
def sync_recent_bars():
    result = asyncio.run(_sync_recent())
    logger.info("OHLCV recent sync complete: %s", result)
    return result
