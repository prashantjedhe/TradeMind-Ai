from datetime import date
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.config import settings
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

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/watchlist")
async def get_watchlist(current_user: User = Depends(get_current_user)):
    return {"tickers": settings.WATCHLIST_TICKERS}


@router.get("/prices")
async def get_prices(current_user: User = Depends(get_current_user)):
    """Latest cached prices for the full watchlist (NSE)."""
    tickers = settings.WATCHLIST_TICKERS
    prices = await get_cached_prices(tickers)
    return {
        "tickers": tickers,
        "prices": {
            t: (str(p) if p is not None else None) for t, p in prices.items()
        },
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
