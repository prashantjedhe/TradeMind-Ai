"""
Celery task: free-RSS news ingest + scoring + signal aggregation.

Runs every 5 minutes (see celery_app beat schedule), independent of
the 15s price loop and the 60s strategy loop. One invocation does a
full pass: fetch RSS (EN+HI) -> dedupe insert -> score -> aggregate
per ticker/window -> persist rows + Redis snapshots.

Same event-loop-per-invocation pattern as the other workers:
asyncio.run() per task, engine + redis pools disposed at the end.
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.api.deps import redis_client
from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.services.news_ingest import ingest_cycle
from app.services.news_signal_service import aggregate_ticker, persist_snapshots
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _run_news_cycle() -> dict:
    if not settings.NEWS_ENABLED:
        return {"skipped": True, "reason": "NEWS_ENABLED=false"}
    try:
        async with AsyncSessionLocal() as db:
            ingest_stats = await ingest_cycle(db)

            now = datetime.now(timezone.utc)
            snapshots: list[dict] = []
            for ticker in settings.WATCHLIST_TICKERS:
                try:
                    snapshots.extend(
                        await aggregate_ticker(db, ticker, now))
                except Exception as exc:
                    logger.warning("News aggregate failed for %s: %s", ticker, exc)
            await persist_snapshots(db, snapshots)

            # Action Engine pass (pause/tighten/lot-size/alerts/resume).
            # Guarded per-action cooldowns inside; failures here must
            # never fail the ingest cycle itself.
            actions: dict = {}
            try:
                from app.services.news_actions import evaluate_news_actions
                actions = await evaluate_news_actions(db)
            except Exception as exc:
                logger.warning("News action pass failed: %s", exc)

            return {**ingest_stats, "signals_written": len(snapshots),
                    "actions": actions}
    finally:
        await engine.dispose()
        try:
            await redis_client.aclose()
        except Exception:
            pass


@celery_app.task(name="app.workers.news_ingest.ingest_news")
def ingest_news():
    result = asyncio.run(_run_news_cycle())
    logger.info("News cycle complete: %s", result)
    return result
