import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OrderType(str, enum.Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    SL = "SL"
    TP = "TP"


class OrderSide(str, enum.Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class TriggeredBy(str, enum.Enum):
    USER = "USER"
    STRATEGY = "STRATEGY"
    NEWS_EVENT = "NEWS_EVENT"


class SettlementType(str, enum.Enum):
    INTRADAY = "INTRADAY"
    DELIVERY = "DELIVERY"
    BTST = "BTST"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    order_type: Mapped[OrderType] = mapped_column(SQLEnum(OrderType), nullable=False)
    side: Mapped[OrderSide] = mapped_column(SQLEnum(OrderSide), nullable=False)
    settlement_type: Mapped[SettlementType] = mapped_column(
        SQLEnum(SettlementType), nullable=False, default=SettlementType.DELIVERY
    )

    quantity: Mapped[int] = mapped_column(nullable=False)

    # The user-specified trigger price for LIMIT/SL/TP orders. NULL for
    # MARKET orders (which execute immediately, no trigger needed).
    trigger_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    requested_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    executed_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Reserved for a future "bracket order" feature (MARKET order with an
    # attached automatic SL/TP exit) - not used by the pending-trigger
    # engine, which uses trigger_price instead.
    stop_loss_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    take_profit_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    slippage_amount: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Full fee breakdown (all in INR), calculated per NSE/SEBI-mandated
    # rates and standard discount-broker (Groww-style) brokerage model.
    brokerage_fee: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    stt_fee: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    stamp_duty_fee: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    exchange_charge_fee: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    sebi_charge_fee: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    gst_fee: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    dp_charge_fee: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)
    total_fees: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    status: Mapped[OrderStatus] = mapped_column(
        SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING, index=True
    )
    triggered_by: Mapped[TriggeredBy] = mapped_column(
        SQLEnum(TriggeredBy), nullable=False, default=TriggeredBy.USER
    )
    updated_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="orders")

    def __repr__(self) -> str:
        return f"<Order {self.id} {self.side} {self.quantity} {self.ticker} status={self.status}>"
