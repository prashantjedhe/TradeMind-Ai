"""
Celery task: check all PENDING (LIMIT/SL/TP) orders against the
latest cached prices, and execute any whose trigger condition has
been met.

Runs on the same event-loop-per-invocation pattern as
workers/market_data.py, and disposes the engine's connection pool
for the same reason (asyncpg connections are bound to the event loop
they were created in).
"""

import asyncio
import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal, engine
from app.models.order import Order, OrderStatus
from app.services.order_service import try_trigger_pending_order
from app.services.price_cache_service import get_cached_price
from app.api.deps import redis_client
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _process_pending_orders() -> dict:
    try:
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Order).where(Order.status == OrderStatus.PENDING)
            )
            pending_orders = result.scalars().all()

            triggered = 0
            skipped = 0
            price_unavailable = 0

            for order in pending_orders:
                current_price = await get_cached_price(order.ticker)

                if current_price is None:
                    price_unavailable += 1
                    continue

                filled_order = await try_trigger_pending_order(db, order, current_price)

                if filled_order is not None:
                    triggered += 1
                    logger.info(
                        "Pending order triggered: %s %s %s x%s at %s",
                        order.id, order.order_type.value, order.side.value,
                        order.quantity, filled_order.executed_price,
                    )
                else:
                    skipped += 1

            return {
                "checked": len(pending_orders),
                "triggered": triggered,
                "skipped": skipped,
                "price_unavailable": price_unavailable,
            }
    finally:
        await engine.dispose()
        try:
            await redis_client.aclose()
        except Exception:
            pass


@celery_app.task(name="app.workers.pending_orders.check_pending_orders")
def check_pending_orders():
    result = asyncio.run(_process_pending_orders())
    if result["checked"] > 0:
        logger.info("Pending order check complete: %s", result)
    return result
