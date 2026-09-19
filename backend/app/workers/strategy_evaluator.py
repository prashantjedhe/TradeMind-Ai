"""
Celery task: evaluate every ACTIVE strategy against its ticker's
latest OHLCV bars and auto-fire the configured action when the
strategy's condition tree turns True.

Edge-triggering: a strategy fires when its root condition goes
False -> True (matching the "crosses" operators and preventing
re-firing on every consecutive bar where a plain comparison like
`RSI < 30` stays true). The last observed condition state is stored
in Redis keyed by strategy id, so the worker is stateless and the
decision survives restarts.

Runs on the same event-loop-per-invocation pattern as the other
workers, disposing the engine pool at the end (asyncpg connections
are bound to the event loop they were created in).
"""

import asyncio
import logging

from sqlalchemy import select

from app.api.deps import redis_client
from app.database import AsyncSessionLocal, engine
from app.models.strategy import Strategy, StrategyStatus
from app.services.strategy_service import evaluate_strategy, fire_action
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

STATE_KEY_PREFIX = "strategy_state:"
EVAL_STATE_TRUE = "1"
EVAL_STATE_FALSE = "0"


def _state_key(strategy_id) -> str:
    return f"{STATE_KEY_PREFIX}{strategy_id}"


async def _evaluate_active_strategies() -> dict:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Strategy).where(Strategy.status == StrategyStatus.ACTIVE)
            )
            strategies = list(result.scalars().all())

            evaluated = 0
            fired = 0
            skipped = 0
            errored = 0

            for strategy in strategies:
                evaluated += 1

                try:
                    current = await evaluate_strategy(db, strategy)
                except Exception as exc:
                    logger.error("Strategy %s evaluation failed: %s", strategy.id, exc)
                    errored += 1
                    continue

                key = _state_key(strategy.id)
                previous = await redis_client.get(key)

                # Edge-trigger: only fire on a fresh False -> True transition.
                if current and previous != EVAL_STATE_TRUE:
                    fired_flag = await fire_action(db, strategy)
                    if fired_flag:
                        fired += 1
                    else:
                        skipped += 1
                    await redis_client.set(key, EVAL_STATE_TRUE)
                elif not current:
                    await redis_client.set(key, EVAL_STATE_FALSE)

            return {
                "active_strategies": evaluated,
                "fired": fired,
                "skipped": skipped,
                "errored": errored,
            }
    finally:
        await engine.dispose()
        try:
            await redis_client.aclose()
        except Exception:
            pass


@celery_app.task(name="app.workers.strategy_evaluator.evaluate_active_strategies")
def evaluate_active_strategies():
    result = asyncio.run(_evaluate_active_strategies())
    if result["active_strategies"] > 0:
        logger.info("Strategy evaluation complete: %s", result)
    return result