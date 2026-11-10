"""
Celery task: evaluate every ACTIVE strategy against its ticker's
latest OHLCV bars and propose an action when the
strategy's condition tree turns True.

Edge-triggering: a proposal is created when its root condition goes
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

from sqlalchemy import and_, or_, select

from app.api.deps import redis_client
from app.database import AsyncSessionLocal, engine
from app.models.strategy import Strategy, StrategyStatus
from app.services.strategy_service import (
    evaluate_strategy,
    fire_action,
    opposing_strategy_context,
)
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
                select(Strategy).where(
                    or_(
                        Strategy.status == StrategyStatus.ACTIVE,
                        and_(
                            Strategy.status == StrategyStatus.PAUSED,
                            Strategy.paused_reason.like("MARKET:%"),
                        ),
                    )
                )
            )
            strategies = list(result.scalars().all())

            evaluated = 0
            proposed = 0
            skipped = 0
            errored = 0
            paused = 0

            for strategy in strategies:
                evaluated += 1

                was_market_paused = (
                    strategy.status == StrategyStatus.PAUSED
                    and str(strategy.paused_reason or "").startswith("MARKET:")
                )
                try:
                    conflict = await opposing_strategy_context(db, strategy)
                except Exception as exc:
                    logger.error(
                        "Strategy %s context guard failed: %s", strategy.id, exc
                    )
                    errored += 1
                    continue
                if conflict:
                    if not was_market_paused or strategy.paused_reason != conflict:
                        strategy.status = StrategyStatus.PAUSED
                        strategy.paused_reason = conflict[:255]
                        await db.commit()
                    await redis_client.set(_state_key(strategy.id), EVAL_STATE_FALSE)
                    if not was_market_paused:
                        paused += 1
                    continue
                if was_market_paused:
                    strategy.status = StrategyStatus.ACTIVE
                    strategy.paused_reason = None
                    await db.commit()
                    await redis_client.set(_state_key(strategy.id), EVAL_STATE_FALSE)

                try:
                    current = await evaluate_strategy(db, strategy)
                except Exception as exc:
                    logger.error("Strategy %s evaluation failed: %s", strategy.id, exc)
                    errored += 1
                    continue

                key = _state_key(strategy.id)
                previous = await redis_client.get(key)

                # Create a proposal only on a fresh False -> True transition.
                if current and previous != EVAL_STATE_TRUE:
                    proposal_created = await fire_action(db, strategy)
                    if proposal_created:
                        proposed += 1
                    else:
                        skipped += 1
                    await redis_client.set(key, EVAL_STATE_TRUE)
                elif not current:
                    await redis_client.set(key, EVAL_STATE_FALSE)

            return {
                "active_strategies": evaluated,
                "proposed": proposed,
                "skipped": skipped,
                "errored": errored,
                "paused": paused,
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