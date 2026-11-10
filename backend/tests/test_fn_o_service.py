from datetime import date
from decimal import Decimal
import pytest

from app.services.fn_o_service import (
    black_scholes,
    parse_instrument,
    option_symbol,
    future_symbol,
    underlying_of,
)


def test_black_scholes_call_and_put():
    spot = 2500.0
    strike = 2500.0  # ATM
    t_years = 30.0 / 365.0
    r = 0.07
    sigma = 0.20

    call_price = black_scholes(Decimal(str(spot)), int(strike), t_years, "CE", sigma, r)["premium"]
    put_price = black_scholes(Decimal(str(spot)), int(strike), t_years, "PE", sigma, r)["premium"]

    assert call_price > 0.0
    assert put_price > 0.0

    # Put-Call Parity check: C - P = S - K * exp(-r*T)
    import math
    discounted_strike = strike * math.exp(-r * t_years)
    parity_diff = abs((call_price - put_price) - (spot - discounted_strike))
    assert parity_diff < 1e-4


def test_compute_greeks():
    spot = 2500.0
    strike = 2500.0
    t_years = 30.0 / 365.0
    r = 0.07
    sigma = 0.20

    greeks_call = black_scholes(Decimal(str(spot)), int(strike), t_years, "CE", sigma, r)
    # ATM call delta is approximately 0.5 ~ 0.55
    assert 0.40 < greeks_call["delta"] < 0.65
    assert greeks_call["gamma"] > 0.0
    assert greeks_call["theta_per_day"] < 0.0
    assert greeks_call["vega_per_1pct"] > 0.0

    greeks_put = black_scholes(Decimal(str(spot)), int(strike), t_years, "PE", sigma, r)
    # Put delta should be negative
    assert -0.65 < greeks_put["delta"] < -0.35
    assert greeks_put["gamma"] > 0.0


def test_instrument_symbol_parser_and_encoder():
    expiry = date(2026, 8, 27)

    # Encode Option Symbol
    symbol_ce = option_symbol("RELIANCE", expiry, 2800, "CE")
    assert "RELIANCE" in symbol_ce
    assert "2800CE" in symbol_ce

    # Parse Option Symbol
    parsed = parse_instrument(symbol_ce)
    assert parsed is not None
    assert parsed.underlying == "RELIANCE"
    assert parsed.strike == 2800
    assert parsed.option_type == "CE"

    # Encode Futures Symbol
    symbol_fut = future_symbol("ICICIBANK", expiry)
    assert "ICICIBANK" in symbol_fut
    assert "FUT" in symbol_fut

    # Parse Futures Symbol
    parsed_fut = parse_instrument(symbol_fut)
    assert parsed_fut is not None
    assert parsed_fut.underlying == "ICICIBANK"
    assert parsed_fut.option_type is None

    # Underlying resolution
    assert underlying_of(symbol_ce) == "RELIANCE"
    assert underlying_of(symbol_fut) == "ICICIBANK"
    assert underlying_of("TCS.NS") == "TCS"
