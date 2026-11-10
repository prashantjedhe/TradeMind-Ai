from datetime import date, datetime
from datetime import time as day_time, timezone
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.ohlcv import BarInterval, OHLCVBar
from app.models.user import User
from app.services.fn_o_service import (
    FNO_UNIVERSE,
    contract_spec,
    futures_quotes,
    monthly_expiries,
    option_chain,
    parse_instrument,
    underlying_of,
)
from app.services.price_cache_service import get_cached_prices
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/v1/market", tags=["market"])
NSE_TIMEZONE = ZoneInfo("Asia/Kolkata")


def daily_change_pct(
    current_price: float | None,
    bars: list[tuple[datetime, float]],
    now: datetime | None = None,
) -> float | None:
    """Return today's live move, or the last completed session's move."""
    if not bars:
        return None

    reference_now = now or datetime.now(NSE_TIMEZONE)
    if reference_now.tzinfo is None:
        reference_now = reference_now.replace(tzinfo=timezone.utc)
    local_now = reference_now.astimezone(NSE_TIMEZONE)
    latest_timestamp, latest_close = bars[0]
    latest_day = latest_timestamp.astimezone(NSE_TIMEZONE).date()
    market_open = (
        local_now.weekday() < 5
        and day_time(9, 15) <= local_now.time() < day_time(15, 30)
    )

    if market_open:
        if current_price is None or current_price <= 0:
            return None
        if latest_day == local_now.date():
            if len(bars) < 2:
                return None
            reference_close = bars[1][1]
        else:
            reference_close = latest_close
        comparison_price = current_price
    else:
        if len(bars) < 2:
            return None
        reference_close = bars[1][1]
        comparison_price = latest_close

    if reference_close <= 0:
        return None
    return round((comparison_price / reference_close - 1) * 100, 2)


@router.get("/watchlist")
async def get_watchlist(current_user: User = Depends(get_current_user)):
    return {"tickers": settings.WATCHLIST_TICKERS}


@router.get("/prices")
async def get_prices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Latest cached NSE prices and today's or last-session change."""
    tickers = settings.WATCHLIST_TICKERS
    prices = await get_cached_prices(tickers)
    local_now = datetime.now(NSE_TIMEZONE)
    ranked_bars = (
        select(
            OHLCVBar.ticker.label("ticker"),
            OHLCVBar.timestamp.label("timestamp"),
            OHLCVBar.close.label("close"),
            func.row_number().over(
                partition_by=OHLCVBar.ticker,
                order_by=OHLCVBar.timestamp.desc(),
            ).label("rank"),
        )
        .where(
            OHLCVBar.ticker.in_(tickers),
            OHLCVBar.interval == BarInterval.ONE_DAY,
        )
        .subquery()
    )
    result = await db.execute(
        select(ranked_bars.c.ticker, ranked_bars.c.timestamp, ranked_bars.c.close)
        .where(ranked_bars.c.rank <= 2)
        .order_by(ranked_bars.c.ticker, ranked_bars.c.timestamp.desc())
    )
    daily_bars: dict[str, list[tuple[datetime, float]]] = {}
    for ticker, timestamp, close in result.all():
        daily_bars.setdefault(ticker, []).append((timestamp, float(close)))
    changes = {
        ticker: daily_change_pct(
            float(price) if price is not None else None,
            daily_bars.get(ticker, []),
        )
        for ticker, price in prices.items()
    }
    return {
        "tickers": tickers,
        "prices": {
            t: (str(p) if p is not None else None) for t, p in prices.items()
        },
        "changes": changes,
        "change_period": (
            "TODAY"
            if local_now.weekday() < 5
            and day_time(9, 15) <= local_now.time() < day_time(15, 30)
            else "LAST SESSION"
        ),
    }


@router.get("/fno/universe")
async def get_fno_universe(current_user: User = Depends(get_current_user)):
    """Underlyings for which we derive futures & options contracts."""
    return {"underlyings": FNO_UNIVERSE}


@router.get("/fno/expiries")
async def get_fno_expiries(current_user: User = Depends(get_current_user)):
    """Next monthly derivative expiries (NSE last-Thursday rule)."""
    return {"expiries": [e.isoformat() for e in monthly_expiries(date.today(), 3)]}


@router.get("/fno/chain")
async def get_fno_chain(
    underlying: str = Query(..., description="Underlying equity ticker, e.g. RELIANCE"),
    expiry: str | None = Query(None, description="DDMMM expiry, e.g. 24AUG. Defaults to nearest"),
    current_user: User = Depends(get_current_user),
):
    """Full option chain (CE/PE × strikes) for one underlying + expiry,
    priced live via Black-Scholes off the cached underlying spot."""
    from datetime import datetime, timedelta

    underlying = underlying.strip().upper()
    spot_result = await get_cached_prices([underlying])
    spot = spot_result.get(underlying)
    if spot is None:
        return {
            "underlying": underlying,
            "spot": None,
            "error": f"No live spot price cached for {underlying}. Try a ticker in /fno/universe.",
            "contracts": [],
            "futures": [],
            "expiries": [e.isoformat() for e in monthly_expiries(date.today(), 3)],
        }

    expiries = monthly_expiries(date.today(), 3)

    # Optional expiry filter: DDMMM -> the matching date in the current year.
    expiries_meta = [e for e in expiries]
    if expiry:
        try:
            target = datetime.strptime(expiry.strip().upper(), "%d%b").date().replace(year=date.today().year)
            if any(e == target for e in expiries):
                expiries_meta = [target]
        except ValueError:
            pass

    chain = option_chain(underlying, spot, expiries_meta[0])
    futs = futures_quotes(underlying, spot, count=3)
    return {
        "underlying": underlying,
        "spot": float(spot),
        "expiry": chain["expiry"],
        "expiries": [e.strftime("%d%b").upper() for e in expiries],
        "chain": chain,
        "futures": futs,
    }


@router.get("/fno/quote")
async def get_fno_quote(
    symbol: str = Query(..., description="F&O contract symbol, e.g. RELIANCE24AUG2800CE"),
    current_user: User = Depends(get_current_user),
):
    """Live quote + greeks for a single F&O contract."""
    parsed = parse_instrument(symbol)
    if parsed is None:
        return {"symbol": symbol.upper(), "error": "Not a valid F&O contract symbol"}

    prices = await get_cached_prices([symbol.upper(), parsed.underlying])
    contract_price = prices.get(symbol.upper())
    spot = prices.get(parsed.underlying)

    return {
        "symbol": symbol.upper(),
        "underlying": parsed.underlying,
        "option_type": parsed.option_type,
        "strike": parsed.strike,
        "expiry": parsed.expiry,
        "spot": float(spot) if spot is not None else None,
        "last_price": float(contract_price) if contract_price is not None else None,
    }
