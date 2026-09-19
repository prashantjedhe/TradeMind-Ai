"""
Fee calculator for simulated NSE trades.

Rates below reflect real, currently-published charges (NSE/SEBI-mandated
taxes + a standard discount-broker brokerage model, e.g. Groww), NOT
the simplified flat rates in the original project roadmap. Rates are
defined as module-level constants so they're easy to audit and update
if regulatory rates change.

All monetary results are Decimal, quantized to 2 decimal places (paise),
consistent with the rest of the accuracy-first design in this project.
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass

from app.models.order import OrderSide, SettlementType
from app.services.fn_o_service import parse_instrument

CENTS = Decimal("0.01")


def _round(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


# --- Brokerage (Groww-style discount broker model) ---
BROKERAGE_RATE = Decimal("0.001")       # 0.1% of trade value
BROKERAGE_MAX = Decimal("20.00")        # capped at ₹20 per order
BROKERAGE_MIN = Decimal("5.00")         # minimum ₹5 per order

# --- STT (Securities Transaction Tax) ---
STT_DELIVERY_RATE = Decimal("0.001")    # 0.1% on BOTH buy and sell
STT_INTRADAY_SELL_RATE = Decimal("0.00025")  # 0.025% on SELL only

# --- F&O STT (NSE/SEBI) ---
STT_FUTURES_SELL_RATE = Decimal("0.000125")   # 0.0125% on SELL only (turnover)
STT_OPTIONS_SELL_RATE = Decimal("0.000625")   # 0.0625% on SELL only (premium turnover)

# --- Stamp Duty (state tax, buy side only) ---
STAMP_DUTY_DELIVERY_RATE = Decimal("0.00015")  # 0.015% on BUY only
STAMP_DUTY_INTRADAY_RATE = Decimal("0.00003")  # 0.003% on BUY only
STAMP_DUTY_FNO_RATE = Decimal("0.00002")       # 0.002% on BUY only (F&O)

# --- Exchange Transaction Charge (NSE) ---
EXCHANGE_CHARGE_RATE = Decimal("0.0000297")  # 0.00297%

# --- SEBI Turnover Charge ---
SEBI_CHARGE_RATE = Decimal("0.000001")  # 0.0001%

# --- GST ---
GST_RATE = Decimal("0.18")  # 18%, applied on (brokerage + exchange charge + SEBI charge)

# --- DP Charge (delivery sell only, per scrip, flat) ---
DP_CHARGE_FLAT = Decimal("20.00")
DP_CHARGE_GST_RATE = Decimal("0.18")


@dataclass
class FeeBreakdown:
    brokerage_fee: Decimal
    stt_fee: Decimal
    stamp_duty_fee: Decimal
    exchange_charge_fee: Decimal
    sebi_charge_fee: Decimal
    gst_fee: Decimal
    dp_charge_fee: Decimal
    total_fees: Decimal


def calculate_fees(
    executed_price: Decimal,
    quantity: int,
    side: OrderSide,
    settlement_type: SettlementType,
    ticker: str | None = None,
) -> FeeBreakdown:
    """
    Calculate the full NSE/SEBI/broker fee breakdown for a single
    simulated trade leg (one order = one leg; a round-trip trade is
    two separate orders - a BUY and a later SELL - each fee-calculated
    independently, matching how real brokers issue contract notes).

    When `ticker` encodes an F&O contract (parsed by fn_o_service),
    the F&O-specific STT/stamp rates apply. Options STT is charged on
    the premium turnover; futures STT on the full turnover - for a
    paper-simulation these both use executed_price * quantity.
    """
    turnover = executed_price * quantity

    fno = parse_instrument(ticker) if ticker else None
    is_option = fno is not None and fno.option_type is not None
    is_futures = fno is not None and fno.option_type is None

    # Brokerage: min(BROKERAGE_MAX, rate * turnover), floored at BROKERAGE_MIN
    raw_brokerage = turnover * BROKERAGE_RATE
    brokerage_fee = min(raw_brokerage, BROKERAGE_MAX)
    brokerage_fee = max(brokerage_fee, BROKERAGE_MIN)
    brokerage_fee = _round(brokerage_fee)

    # STT
    if is_futures:
        stt_fee = turnover * STT_FUTURES_SELL_RATE if side == OrderSide.SELL else Decimal("0")
    elif is_option:
        stt_fee = turnover * STT_OPTIONS_SELL_RATE if side == OrderSide.SELL else Decimal("0")
    elif settlement_type in (SettlementType.DELIVERY, SettlementType.BTST):
        stt_fee = turnover * STT_DELIVERY_RATE
    else:  # INTRADAY equity - only charged on the SELL leg
        stt_fee = turnover * STT_INTRADAY_SELL_RATE if side == OrderSide.SELL else Decimal("0")
    stt_fee = _round(stt_fee)

    # Stamp Duty - only charged on the BUY leg
    if side == OrderSide.BUY:
        if fno is not None:
            stamp_rate = STAMP_DUTY_FNO_RATE
        else:
            stamp_rate = (
                STAMP_DUTY_DELIVERY_RATE
                if settlement_type in (SettlementType.DELIVERY, SettlementType.BTST)
                else STAMP_DUTY_INTRADAY_RATE
            )
        stamp_duty_fee = _round(turnover * stamp_rate)
    else:
        stamp_duty_fee = Decimal("0.00")

    # Exchange transaction charge - both legs, both settlement types
    exchange_charge_fee = _round(turnover * EXCHANGE_CHARGE_RATE)

    # SEBI turnover charge - both legs, both settlement types
    sebi_charge_fee = _round(turnover * SEBI_CHARGE_RATE)

    # GST - applied on (brokerage + exchange charge + SEBI charge) only,
    # NOT on STT or stamp duty (those are government taxes, not services)
    gst_fee = _round((brokerage_fee + exchange_charge_fee + sebi_charge_fee) * GST_RATE)

    # DP charge - delivery SELL only, flat per-scrip fee + GST (equity only)
    if (
        settlement_type in (SettlementType.DELIVERY, SettlementType.BTST)
        and side == OrderSide.SELL
        and fno is None
    ):
        dp_charge_fee = _round(DP_CHARGE_FLAT * (1 + DP_CHARGE_GST_RATE))
    else:
        dp_charge_fee = Decimal("0.00")

    total_fees = _round(
        brokerage_fee
        + stt_fee
        + stamp_duty_fee
        + exchange_charge_fee
        + sebi_charge_fee
        + gst_fee
        + dp_charge_fee
    )

    return FeeBreakdown(
        brokerage_fee=brokerage_fee,
        stt_fee=stt_fee,
        stamp_duty_fee=stamp_duty_fee,
        exchange_charge_fee=exchange_charge_fee,
        sebi_charge_fee=sebi_charge_fee,
        gst_fee=gst_fee,
        dp_charge_fee=dp_charge_fee,
        total_fees=total_fees,
    )
