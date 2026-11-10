"""
League auto-finalization Celery task.

Runs daily at midnight IST. Finds all ACTIVE leagues whose end_date
has passed and finalizes them (computes final rankings, awards badges,
marks COMPLETED).

Design notes:
- Runs daily, not monthly — handles any league duration (7, 14, 30, 90 days)
- asyncio.run() with explicit engine disposal to prevent InterfaceError
- Logs results at INFO level for monitoring
"""

from __future__ import annotations

import asyncio
import logging

from app.workers.celery_app import celery_app
from app.database import AsyncSessionLocal, engine

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.league_reset.auto_finalize_leagues")
def auto_finalize_leagues() -> dict:
    """Daily task: finalize all expired ACTIVE leagues."""
    return asyncio.run(_run())


async def _run() -> dict:
    from app.services.league_service import check_and_finalize_expired_leagues

    async with AsyncSessionLocal() as db:
        try:
            finalized = await check_and_finalize_expired_leagues(db)
            if finalized:
                logger.info(f"Auto-finalized {len(finalized)} league(s): {finalized}")
            else:
                logger.debug("No expired leagues to finalize.")
            return {"finalized": finalized, "count": len(finalized)}
        except Exception as e:
            logger.error(f"League auto-finalization error: {e}")
            return {"finalized": [], "error": str(e)}
        finally:
            await engine.dispose()
