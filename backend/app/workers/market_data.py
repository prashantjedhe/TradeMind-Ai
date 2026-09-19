"""
Celery task: refresh cached NSE prices for the fixed watchlist
and every ticker currently held in an OPEN position.

Important: each task invocation runs via asyncio.run(), which
creates a NEW event loop every time. asyncpg connections are bound
to the event loop they were created in, so the shared `engine`'s
connection pool must be disposed at the end of every task run -
otherwise the next run (new event loop) fails trying to reuse
connections tied to the previous, now-closed loop.
"""

import asyncio
import logging
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.models.portfolio import Position, PositionStatus
from app.services.fn_o_service import (
    FNO_UNIVERSE,
    black_scholes,
    contract_spec,
    future_price,
    future_symbol,
    is_fno_symbol,
    monthly_expiries,
    option_strikes,
    option_symbol,
    underlying_of,
)
from app.services.price_cache_service import set_cached_price
from app.api.deps import redis_client
from app.utils.market_data import fetch_latest_prices
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _get_held_tickers() -> set[str]:
    """Fetch distinct tickers from all currently OPEN positions."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Position.ticker).where(Position.status == PositionStatus.OPEN).distinct()
        )
        return {row[0] for row in result.all()}


def _spot_key(underlying: str) -> str:
    """Map F&O underlying name to the spot price cache key (yfinance symbol)."""
    if underlying == "NIFTY":
        return "^NSEI"
    if underlying == "BANKNIFTY":
        return "^NSEBANK"
    return underlying  # equities use plain ticker


def _derive_fno_prices(spot_prices: dict[str, object]) -> dict[str, str]:
    """
    Derive F&O contract prices from the underlying's live spot and
    return {contract_symbol: "price"} for the F&O universe plus any
    F&O contract currently held in an open position.
    """
    ref = date.today()
    expiries = monthly_expiries(ref, count=3)
    derived: dict[str, str] = {}

    underlyings = set(FNO_UNIVERSE)
    for sym in spot_prices:
        if is_fno_symbol(sym):
            underlyings.add(underlying_of(sym))

    for underlying in underlyings:
        spot_key = _spot_key(underlying)
        spot = spot_prices.get(spot_key)
        if spot is None:
            continue
        try:
            spot_dec = Decimal(str(spot))
        except Exception:
            continue
        if spot_dec <= 0:
            continue

        spec = contract_spec(underlying, spot_dec)
        # Futures: every universe expiry
        for expiry in expiries:
            derived[future_symbol(underlying, expiry)] = str(future_price(spot_dec, expiry, ref))
        # Options: ATM +-1 step around spot (a tight, useful band)
        strikes = option_strikes(spot_dec, spec["step"], span=0.02)
        for expiry in expiries:
            t_years = max((expiry - ref).days, 0) / 365.0
            for strike in strikes:
                for opt_type in ("CE", "PE"):
                    bs = black_scholes(spot_dec, strike, t_years, opt_type)
                    derived[option_symbol(underlying, expiry, strike, opt_type)] = str(
                        Decimal(str(bs["premium"])).quantize(Decimal("0.01"))
                    )

    return derived


async def _refresh_prices() -> dict:
    try:
        watchlist = set(settings.WATCHLIST_TICKERS)
        held = await _get_held_tickers()
        all_tickers = sorted(watchlist | held)

        # F&O contracts have no yfinance symbol - they're DERIVED from
        # their underlying's spot. Pull them out of the yfinance fetch
        # and derive them afterwards.
        held_fno = {t for t in held if is_fno_symbol(t)}
        fetch_tickers = [t for t in all_tickers if t not in held_fno]

        prices = fetch_latest_prices(fetch_tickers)

        # Derive F&O contracts off the fresh spots and fold them in.
        fno_prices = _derive_fno_prices(prices)
        prices.update(fno_prices)

        refreshed = 0
        failed = []
        for ticker, price in prices.items():
            if price is not None:
                await set_cached_price(ticker, price)
                refreshed += 1
            else:
                failed.append(ticker)

        if failed:
            logger.warning("Failed to refresh prices for: %s", failed)

        return {"refreshed": refreshed, "failed": failed, "total": len(all_tickers), "fno": len(fno_prices)}
    finally:
        # Dispose the connection pool so the NEXT task invocation
        # (a new event loop via asyncio.run) doesn't inherit
        # connections bound to this now-closing loop. Same for the
        # shared Redis async client - its pool is loop-bound too.
        await engine.dispose()
        try:
            await redis_client.aclose()
        except Exception:
            pass


@celery_app.task(name="app.workers.market_data.refresh_watchlist_prices")
def refresh_watchlist_prices():
    """
    Sync entrypoint required by Celery. Wraps the async logic since
    our DB layer and price cache are async-native (matching the rest
    of the app's async SQLAlchemy architecture).
    """
    result = asyncio.run(_refresh_prices())
    logger.info("Price refresh complete: %s", result)
    return result
