"""
F&O (Futures & Options) pricing + instrument service.

TradeMind's market data is equity OHLCV (yfinance, .NS tickers), so
derivatives cannot be pulled live. Instead we DERIVE realistic F&O
instruments from the underlying equity spot price:

- Futures  : spot * (1 + carry_basis) with basis decaying toward expiry.
- Options  : Black-Scholes premium + greeks from spot, strike, time to
             expiry, risk-free rate and a synthetic implied-volatility
             surface (base IV + moneyness smile + time decay).

Instruments are encoded ENTIRELY in a ticker string that fits the
existing Order.ticker / Position.ticker / Strategy.ticker columns
(String(20)) and the order schema's max_length=20 validator:

    {UNDERLYING}{DDMMM}{STRIKE}{CE|PE}   e.g. RELIANCE24AUG2800CE
    {UNDERLYING}{DDMMM}FUT               e.g. ICICIBANK24AUGFUT

The order/position/P&L engine is completely agnostic to this: it just
reads the cached price for whatever ticker string it sees. F&O prices
are written to the same Redis price cache by the market-data worker,
derived from the underlying's live spot each cycle.

Strategy evaluation ALSO works unchanged: when a strategy's ticker is
an F&O contract, the evaluator resolves it back to the underlying
equity ticker to load OHLCV bars (the contract has no candles of its
own), then fires the order on the F&O ticker itself.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal

from app.config import settings

RISK_FREE_RATE = 0.07          # ~7% India policy-neutral proxy
VOL_BASE = 0.16                # ATM implied vol base
VOL_SMILE = 0.18               # smile curvature by |moneyness|
VOL_TIME_DECAY = 0.04          # extra vol the further out in time
CARRY_RATE = 0.08              # annualised futures carry (funding + dividends)

# Per-ticker contract specs. Unlisted tickers fall back to a heuristic
# lot size of max(25, round(5000/spot)) rounded to the nearest 25.
CONTRACT_SPECS: dict[str, dict] = {
    "RELIANCE": {"lot": 250, "multiplier": 250, "step": 5},
    "HDFCBANK": {"lot": 550, "multiplier": 550, "step": 5},
    "ICICIBANK": {"lot": 2750, "multiplier": 2750, "step": 5},
    "SBIN": {"lot": 3000, "multiplier": 3000, "step": 5},
    "KOTAKBANK": {"lot": 1600, "multiplier": 1600, "step": 5},
    "TCS": {"lot": 175, "multiplier": 175, "step": 20},
    "INFY": {"lot": 800, "multiplier": 800, "step": 5},
    "WIPRO": {"lot": 3000, "multiplier": 3000, "step": 5},
    "HCLTECH": {"lot": 2500, "multiplier": 2500, "step": 5},
    "RELIANCE": {"lot": 250, "multiplier": 250, "step": 5},
    "MARUTI": {"lot": 100, "multiplier": 100, "step": 20},
    "HINDUNILVR": {"lot": 500, "multiplier": 500, "step": 10},
    "ITC": {"lot": 3200, "multiplier": 3200, "step": 5},
    "TATASTEEL": {"lot": 3000, "multiplier": 3000, "step": 5},
    "JSWSTEEL": {"lot": 1250, "multiplier": 1250, "step": 5},
    "SUNPHARMA": {"lot": 1000, "multiplier": 1000, "step": 5},
    "DLF": {"lot": 1500, "multiplier": 1500, "step": 5},
    "ONGC": {"lot": 2000, "multiplier": 2000, "step": 5},
    "NIFTY": {"lot": 25, "multiplier": 25, "step": 50},
    "BANKNIFTY": {"lot": 15, "multiplier": 15, "step": 100},
}

# Which underlyings the price worker derives F&O contracts for every
# cycle (kept small to limit Redis writes; any contract held in an OPEN
# position is priced too, regardless of this list).
FNO_UNIVERSE: list[str] = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "TCS", "INFY",
    "NIFTY", "BANKNIFTY",
]


# ────────────────────────────────────────────────────────────────
# Contract-spec helpers
# ────────────────────────────────────────────────────────────────

def contract_spec(underlying: str, spot: Decimal) -> dict:
    spec = CONTRACT_SPECS.get(underlying)
    if spec is not None:
        return spec
    lot = max(25, round(5000 / float(spot)))
    lot = max(25, int(round(lot / 25.0)) * 25)
    step = 5 if float(spot) < 2000 else 10 if float(spot) < 5000 else 50
    return {"lot": lot, "multiplier": lot, "step": step}


# ────────────────────────────────────────────────────────────────
# Expiry calendar
# ────────────────────────────────────────────────────────────────

def _last_thursday(year: int, month: int) -> date:
    """Last Thursday of a month - the standard NSE derivatives expiry."""
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last_day = next_month - timedelta(days=1)
    days_back = (last_day.weekday() - 3) % 7  # Thursday == weekday 3
    return last_day - timedelta(days=days_back)


def monthly_expiries(reference: date | None = None, count: int = 3) -> list[date]:
    """Next `count` monthly expiry dates (NSE last-Thursday rule)."""
    ref = reference or date.today()
    result: list[date] = []
    year, month = ref.year, ref.month
    while len(result) < count:
        expiry = _last_thursday(year, month)
        if expiry > ref:
            result.append(expiry)
        month += 1
        if month > 12:
            month = 1
            year += 1
    return result


# ────────────────────────────────────────────────────────────────
# Symbol parsing / building
# ────────────────────────────────────────────────────────────────

_OPTION_SYMBOL_RE = re.compile(r"^([A-Z0-9]+?)(\d{2})([A-Z]{3})(\d+)(CE|PE)$")
_FUTURE_SYMBOL_RE = re.compile(r"^([A-Z0-9]+?)(\d{2})([A-Z]{3})FUT$")


@dataclass
class FnOInstrument:
    underlying: str
    expiry: str          # DDMMM, e.g. "24AUG"
    strike: int | None
    option_type: str | None  # "CE" | "PE" | None for futures
    symbol: str


def option_symbol(underlying: str, expiry: date, strike: int, option_type: str) -> str:
    return f"{underlying.upper()}{expiry.strftime('%d%b').upper()}{strike}{option_type.upper()}"


def future_symbol(underlying: str, expiry: date) -> str:
    return f"{underlying.upper()}{expiry.strftime('%d%b').upper()}FUT"


def parse_instrument(symbol: str) -> FnOInstrument | None:
    """Parse an F&O ticker string back into its components, or None if
    the symbol is not an F&O contract."""
    sym = symbol.strip().upper()
    m = _OPTION_SYMBOL_RE.match(sym)
    if m:
        return FnOInstrument(
            underlying=m.group(1),
            expiry=f"{m.group(2)}{m.group(3)}",
            strike=int(m.group(4)),
            option_type=m.group(5),
            symbol=sym,
        )
    m = _FUTURE_SYMBOL_RE.match(sym)
    if m:
        return FnOInstrument(
            underlying=m.group(1),
            expiry=f"{m.group(2)}{m.group(3)}",
            strike=None,
            option_type=None,
            symbol=sym,
        )
    return None


def is_fno_symbol(symbol: str) -> bool:
    return parse_instrument(symbol) is not None


def underlying_of(symbol: str) -> str:
    """Resolve the equity underlying of any ticker (F&O or plain equity)."""
    inst = parse_instrument(symbol)
    return inst.underlying if inst else symbol.strip().upper()


def expiry_date(expiry: str, reference: date | None = None) -> date:
    """Parse a DDMMM expiry string into a date."""
    try:
        return datetime.strptime(expiry, "%d%b").date().replace(year=(reference or date.today()).year)
    except ValueError:
        return (reference or date.today())


# ────────────────────────────────────────────────────────────────
# Black-Scholes (European options on spot, dividend-adjusted r)
# ────────────────────────────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes(
    spot: Decimal, strike: int, t_years: float, option_type: str,
    implied_vol: float | None = None, rate: float = RISK_FREE_RATE,
) -> dict:
    """Return {premium, delta, gamma, theta_per_day, vega_per_1pct, iv}."""
    s = float(spot)
    k = float(strike)
    iv = implied_vol if implied_vol is not None else implied_vol_surface(s, k, t_years, option_type)

    if t_years <= 0 or s <= 0 or iv <= 0:
        intrinsic = max(s - k, 0.0) if option_type == "CE" else max(k - s, 0.0)
        return {
            "premium": intrinsic,
            "delta": 1.0 if (option_type == "CE" and s > k) else (0.0 if option_type == "CE" else -1.0) if s < k else 0.0,
            "gamma": 0.0,
            "theta_per_day": 0.0,
            "vega_per_1pct": 0.0,
            "iv": iv,
        }

    d1 = (math.log(s / k) + (rate + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    d2 = d1 - iv * math.sqrt(t_years)

    if option_type == "CE":
        premium = s * _norm_cdf(d1) - k * math.exp(-rate * t_years) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        theta = (
            -(s * _norm_pdf(d1) * iv) / (2 * math.sqrt(t_years))
            - rate * k * math.exp(-rate * t_years) * _norm_cdf(d2)
        )
    else:
        premium = k * math.exp(-rate * t_years) * _norm_cdf(-d2) - s * _norm_cdf(-d1)
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -(s * _norm_pdf(d1) * iv) / (2 * math.sqrt(t_years))
            + rate * k * math.exp(-rate * t_years) * _norm_cdf(-d2)
        )

    gamma = _norm_pdf(d1) / (s * iv * math.sqrt(t_years))
    vega = s * _norm_pdf(d1) * math.sqrt(t_years)

    return {
        # Keep precision here; the chain formatter applies the NSE ₹0.05
        # tick so far OTM options do not disappear as ₹0.00.
        "premium": round(premium, 6),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta_per_day": round(theta / 365.0, 4),
        "vega_per_1pct": round(vega / 100.0, 4),
        "iv": round(iv, 4),
    }


def implied_vol_surface(
    spot: float,
    strike: float,
    t_years: float,
    option_type: str | None = None,
) -> float:
    """Synthetic NSE-like smile with a downside-put volatility skew.

    The chain remains theoretical, but calls and puts must not share one
    constant premium floor. OTM puts carry a modest volatility premium,
    matching the usual index/equity downside skew.
    """
    log_moneyness = math.log(strike / spot) if spot > 0 else 0.0
    moneyness = abs(log_moneyness)
    smile = VOL_SMILE * moneyness
    downside_skew = 0.04 * max(-log_moneyness, 0.0) / 0.10
    put_skew = downside_skew if option_type == "PE" else 0.0
    return VOL_BASE + smile + put_skew + VOL_TIME_DECAY * t_years


def future_price(spot: Decimal, expiry: date, reference: date | None = None) -> Decimal:
    """Spot * (1 + carry) with the carry decaying linearly to zero at expiry."""
    ref = reference or date.today()
    days_to_expiry = max((expiry - ref).days, 0)
    annual_fraction = days_to_expiry / 365.0
    basis = CARRY_RATE * annual_fraction
    return (spot * (1 + Decimal(str(basis)))).quantize(Decimal("0.01"))


# ────────────────────────────────────────────────────────────────
# Chain generation
# ────────────────────────────────────────────────────────────────

def option_strikes(spot: Decimal, step: int, span: float = 0.12) -> list[int]:
    """Strikes spanning +/-span around the spot, on the given step grid."""
    spot_f = float(spot)
    lower = int(math.floor(spot_f * (1 - span) / step) * step)
    upper = int(math.ceil(spot_f * (1 + span) / step) * step)
    return list(range(lower, upper + 1, step))


def option_chain(
    underlying: str,
    spot: Decimal,
    expiry: date,
    reference: date | None = None,
) -> dict:
    """Full CE/PE chain for one underlying + expiry with greeks."""
    ref = reference or date.today()
    spec = contract_spec(underlying, spot)
    strikes = option_strikes(spot, spec["step"])
    t_years = max((expiry - ref).days, 0) / 365.0

    contracts = []
    atm_strike = min(strikes, key=lambda k: abs(k - float(spot)))

    for strike in strikes:
        for opt_type in ("CE", "PE"):
            bs = black_scholes(spot, strike, t_years, opt_type)
            contracts.append(
                {
                    "symbol": option_symbol(underlying, expiry, strike, opt_type),
                    "underlying": underlying,
                    "expiry": expiry.strftime("%d%b").upper(),
                    "expiry_date": expiry.isoformat(),
                    "strike": strike,
                    "option_type": opt_type,
                    "is_atm": strike == atm_strike,
                    "premium": bs["premium"],
                    "delta": bs["delta"],
                    "gamma": bs["gamma"],
                    "theta_per_day": bs["theta_per_day"],
                    "vega_per_1pct": bs["vega_per_1pct"],
                    "iv": bs["iv"],
                    "multiplier": spec["multiplier"],
                    "lot_size": spec["lot"],
                }
            )

    return {
        "underlying": underlying,
        "spot": float(spot),
        "expiry": expiry.strftime("%d%b").upper(),
        "expiry_date": expiry.isoformat(),
        "days_to_expiry": max((expiry - ref).days, 0),
        "step": spec["step"],
        "lot_size": spec["lot"],
        "multiplier": spec["multiplier"],
        "contracts": contracts,
    }


def futures_quotes(underlying: str, spot: Decimal, count: int = 3, reference: date | None = None) -> list[dict]:
    ref = reference or date.today()
    expiries = monthly_expiries(ref, count)
    spec = contract_spec(underlying, spot)
    quotes = []
    for expiry in expiries:
        quotes.append(
            {
                "symbol": future_symbol(underlying, expiry),
                "underlying": underlying,
                "expiry": expiry.strftime("%d%b").upper(),
                "expiry_date": expiry.isoformat(),
                "days_to_expiry": max((expiry - ref).days, 0),
                "price": float(future_price(spot, expiry, ref)),
                "basis": float(future_price(spot, expiry, ref) - spot),
                "lot_size": spec["lot"],
                "multiplier": spec["multiplier"],
            }
        )
    return quotes