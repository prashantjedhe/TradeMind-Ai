"""Periodic persistence of closed-bar outcomes for news signal baselines."""

import asyncio
import logging

from app.database import AsyncSessionLocal, engine
from app.services.news_outcomes import record_due_outcomes
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _evaluate_news_outcomes() -> dict[str, int]:
    try:
        async with AsyncSessionLocal() as db:
            return await record_due_outcomes(db)
    finally:
        await engine.dispose()


@celery_app.task(name="app.workers.news_outcomes.evaluate_news_outcomes")
def evaluate_news_outcomes() -> dict[str, int]:
    result = asyncio.run(_evaluate_news_outcomes())
    logger.info("News outcome evaluation complete: %s", result)
    return result
