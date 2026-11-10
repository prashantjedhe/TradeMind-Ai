import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.order import OrderType, OrderSide, OrderStatus, TriggeredBy, SettlementType


class OrderCreateRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    order_type: OrderType
    side: OrderSide
    settlement_type: SettlementType = SettlementType.DELIVERY
    quantity: int = Field(gt=0, le=100_000, description="Must be a positive integer")

    # Required for LIMIT/SL/TP orders; must be omitted for MARKET orders.
    limit_price: Decimal | None = Field(default=None, gt=0)

    stop_loss_price: Decimal | None = Field(default=None, gt=0)
    take_profit_price: Decimal | None = Field(default=None, gt=0)

    @field_validator("ticker")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.strip().upper()

    @model_validator(mode="after")
    def validate_price_by_order_type(self) -> "OrderCreateRequest":
        needs_limit_price = self.order_type in (OrderType.LIMIT, OrderType.SL, OrderType.TP)

        if needs_limit_price and self.limit_price is None:
            raise ValueError(f"limit_price is required for {self.order_type.value} orders")

        if self.order_type == OrderType.MARKET and self.limit_price is not None:
            raise ValueError("limit_price must not be set for MARKET orders")

        return self


class OrderResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    ticker: str
    order_type: OrderType
    side: OrderSide
    settlement_type: SettlementType
    quantity: int

    trigger_price: Decimal | None
    requested_price: Decimal | None
    executed_price: Decimal | None
    stop_loss_price: Decimal | None
    take_profit_price: Decimal | None

    slippage_amount: Decimal | None
    brokerage_fee: Decimal | None
    stt_fee: Decimal | None
    stamp_duty_fee: Decimal | None
    exchange_charge_fee: Decimal | None
    sebi_charge_fee: Decimal | None
    gst_fee: Decimal | None
    dp_charge_fee: Decimal | None
    total_fees: Decimal | None

    status: OrderStatus
    triggered_by: TriggeredBy
    updated_reason: str | None

    created_at: datetime
    filled_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class TradeProposalResponse(BaseModel):
    id: uuid.UUID
    strategy_id: uuid.UUID | None
    ticker: str
    side: str
    quantity: int
    settlement_type: str
    limit_price: Decimal
    status: str
    rationale: str
    evidence: dict
    created_at: datetime
    expires_at: datetime

    model_config = ConfigDict(from_attributes=True)
