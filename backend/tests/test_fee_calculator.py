from decimal import Decimal
import pytest

from app.models.order import OrderSide, SettlementType
from app.services.fee_calculator import (
    calculate_fees,
    BROKERAGE_MAX,
    BROKERAGE_MIN,
    DP_CHARGE_FLAT,
    DP_CHARGE_GST_RATE,
)


def test_equity_delivery_buy_fees():
    # 100 shares @ ₹2500 = ₹250,000 turnover
    price = Decimal("2500.00")
    qty = 100
    fees = calculate_fees(price, qty, OrderSide.BUY, SettlementType.DELIVERY, "RELIANCE")

    turnover = price * qty  # 250,000
    # Brokerage capped at max ₹20
    assert fees.brokerage_fee == BROKERAGE_MAX
    # STT: 0.1% on delivery buy = ₹250
    assert fees.stt_fee == Decimal("250.00")
    # Stamp duty: 0.015% on BUY = ₹37.50
    assert fees.stamp_duty_fee == Decimal("37.50")
    # DP charge is 0 on BUY
    assert fees.dp_charge_fee == Decimal("0.00")
    # Total fees should equal sum of components
    assert fees.total_fees == (
        fees.brokerage_fee
        + fees.stt_fee
        + fees.stamp_duty_fee
        + fees.exchange_charge_fee
        + fees.sebi_charge_fee
        + fees.gst_fee
        + fees.dp_charge_fee
    )


def test_equity_delivery_sell_fees_includes_dp_charge():
    price = Decimal("1500.00")
    qty = 50
    fees = calculate_fees(price, qty, OrderSide.SELL, SettlementType.DELIVERY, "INFY")

    # Stamp duty is 0 on SELL
    assert fees.stamp_duty_fee == Decimal("0.00")
    # DP charge is charged on delivery SELL: 20 * 1.18 = 23.60
    assert fees.dp_charge_fee == Decimal("23.60")
    assert fees.total_fees > Decimal("23.60")


def test_equity_intraday_no_stt_on_buy():
    price = Decimal("3000.00")
    qty = 10
    fees_buy = calculate_fees(price, qty, OrderSide.BUY, SettlementType.INTRADAY, "TCS")
    # STT on intraday BUY is 0
    assert fees_buy.stt_fee == Decimal("0.00")

    # STT on intraday SELL is 0.025%
    fees_sell = calculate_fees(price, qty, OrderSide.SELL, SettlementType.INTRADAY, "TCS")
    assert fees_sell.stt_fee == Decimal("7.50")  # 30,000 * 0.00025 = 7.50


def test_fno_options_and_futures_fee_rules():
    # Options contract: RELIANCE24AUG2800CE
    opt_price = Decimal("35.50")
    qty = 250
    fees_opt_buy = calculate_fees(opt_price, qty, OrderSide.BUY, SettlementType.DELIVERY, "RELIANCE24AUG2800CE")
    assert fees_opt_buy.dp_charge_fee == Decimal("0.00")  # No DP charges on F&O

    # Futures contract: RELIANCE24AUGFUT
    fut_price = Decimal("2510.00")
    fees_fut_sell = calculate_fees(fut_price, qty, OrderSide.SELL, SettlementType.DELIVERY, "RELIANCE24AUGFUT")
    assert fees_fut_sell.dp_charge_fee == Decimal("0.00")
    assert fees_fut_sell.stt_fee > Decimal("0.00")
