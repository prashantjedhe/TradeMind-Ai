"""
Redis-backed price cache.

Design notes:
- Reuses the same redis_client instance as the JWT blacklist (deps.py)
  rather than opening a second connection pool.
- Order execution and portfolio P&L calculations MUST read prices
  from this cache, never call the market data client (yfinance)
  directly - that keeps request/response times fast and avoids
  hammering Yahoo Finance on every single order.
- Prices are refreshed by a Celery beat task (see workers/market_data.py),
  independent of any single request.
- TTL is a safety net: if Celery beat stops running for any reason,
  cached prices expire rather than being served indefinitely stale.
"""

import logging
from decimal import Decimal, InvalidOperation

from app.api.deps import redis_client
from app.config import settings

logger = logging.getLogger(__name__)

PRICE_KEY_PREFIX = "price:"


def _price_key(ticker: str) -> str:
    return f"{PRICE_KEY_PREFIX}{ticker.strip().upper()}"


async def set_cached_price(ticker: str, price: Decimal) -> None:
    """Write a price to the cache with the configured TTL."""
    key = _price_key(ticker)
    await redis_client.setex(key, settings.PRICE_CACHE_TTL_SECONDS, str(price))


async def get_cached_price(ticker: str) -> Decimal | None:
    """
    Read a price from the cache.

    Returns None if the ticker isn't cached or has expired - callers
    must treat this as "no fresh price available" and must NOT
    execute orders against a None price.
    """
    key = _price_key(ticker)
    raw_value = await redis_client.get(key)

    if raw_value is None:
        logger.warning("Cache miss for %s", key)
        return None

    try:
        return Decimal(raw_value)
    except InvalidOperation:
        logger.error("Corrupt cached price for %s: %r", key, raw_value)
        return None


async def get_cached_prices(tickers: list[str]) -> dict[str, Decimal | None]:
    """Read multiple cached prices in one call."""
    results: dict[str, Decimal | None] = {}
    for ticker in tickers:
        results[ticker] = await get_cached_price(ticker)
    return results


async def get_price_or_derive(ticker: str) -> Decimal | None:
    """
    Read a price from cache; if absent and the ticker is an F&O
    contract, derive it on the fly from the underlying's cached spot
    (Black-Scholes for options, carry basis for futures). Lets any
    strike shown in the chain - not just the ATM band the worker
    caches - be priced for order execution and portfolio P&L.
    """
    cached = await get_cached_price(ticker)
    if cached is not None:
        return cached

    from app.services.fn_o_service import (
        parse_instrument,
        expiry_date,
        black_scholes,
        future_price,
    )
    from datetime import date

    inst = parse_instrument(ticker)
    if inst is None:
        return None

    spot = await get_cached_price(inst.underlying)
    if spot is None:
        return None

    exp = expiry_date(inst.expiry)
    if inst.option_type is not None:
        t_years = max((exp - date.today()).days, 0) / 365.0
        bs = black_scholes(spot, inst.strike, t_years, inst.option_type)
        return Decimal(str(bs["premium"])).quantize(Decimal("0.01"))
    return future_price(spot, exp)
