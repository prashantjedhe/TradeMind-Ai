import uuid
import enum
from datetime import datetime, time
from sqlalchemy import String, Numeric, DateTime, Time, ForeignKey, Enum as SQLEnum, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.order import OrderSide, SettlementType  # reused: same BUY/SELL, DELIVERY/INTRADAY domain


class StrategyTimeframe(str, enum.Enum):
    M15 = "15m"
    D1 = "1d"


class StrategyStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


class StrategyActionOrderType(str, enum.Enum):
    """
    Deliberately narrower than order.OrderType. SL/TP are pending-order
    behaviors attached to an existing position (Phase 2's trigger
    engine) -- not valid entry actions for a strategy to auto-fire.
    """
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # e.g. RELIANCE.NS
    timeframe: Mapped[StrategyTimeframe] = mapped_column(SQLEnum(StrategyTimeframe), nullable=False)

    # Recursive AND/OR condition tree -- see app/schemas/strategy.py
    # ConditionNode. JSONB, not normalized tables: the tree nests
    # arbitrarily and is always read/written as a whole document on
    # every evaluation cycle -- a self-referencing adjacency-list
    # schema with recursive CTEs would be overengineering for that
    # access pattern.
    root_condition: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Action fired when root_condition evaluates True. Typed columns,
    # same pattern as Order -- small fixed field set, not a tree.
    action_side: Mapped[OrderSide] = mapped_column(SQLEnum(OrderSide), nullable=False)
    action_order_type: Mapped[StrategyActionOrderType] = mapped_column(
        SQLEnum(StrategyActionOrderType), nullable=False
    )
    action_quantity: Mapped[int] = mapped_column(nullable=False)
    action_settlement_type: Mapped[SettlementType] = mapped_column(
        SQLEnum(SettlementType), nullable=False, default=SettlementType.INTRADAY
    )
    action_limit_price: Mapped[float | None] = mapped_column(Numeric(12, 4), nullable=True)

    # Optional multi-leg options configuration. JSONB keeps the leg/risk
    # documents extensible while the classic action columns remain intact.
    strategy_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(10), nullable=True)
    product: Mapped[str | None] = mapped_column(String(20), nullable=True)
    order_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    square_off_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    trading_days: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    legs: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    risk_controls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    status: Mapped[StrategyStatus] = mapped_column(
        SQLEnum(StrategyStatus), nullable=False, default=StrategyStatus.DRAFT, index=True
    )
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── News Action Engine state ────────────────────────────────
    # Written by news_actions.py, never by the user directly.
    # paused_reason surfaces in the UI so auto-pauses are visible;
    # news_event_id links the pause to its evidence headline.
    # quantity_multiplier scales the next fired order's quantity
    # (actual = max(1, floor(base × multiplier))); multiplier_set_at
    # drives the auto-restore timer.
    paused_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    news_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("news_articles.id", ondelete="SET NULL"),
        nullable=True,
    )
    quantity_multiplier: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False, default=1.0)
    multiplier_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="strategies")
    backtests = relationship("BacktestResult", back_populates="strategy")

    @property
    def action(self) -> dict:
        """Expose the flat action_* columns as the nested `action` shape
        the StrategyOut schema expects (side/order_type/quantity/settlement_type/limit_price)."""
        return {
            "side": self.action_side,
            "order_type": self.action_order_type,
            "quantity": self.action_quantity,
            "settlement_type": self.action_settlement_type,
            "limit_price": self.action_limit_price,
        }

    __table_args__ = (
        # Celery evaluator's core query every cycle: "all ACTIVE
        # strategies for timeframe X" -- index matches that directly.
        Index("ix_strategies_status_timeframe", "status", "timeframe"),
    )

    def __repr__(self) -> str:
        return f"<Strategy {self.id} {self.name} {self.ticker} status={self.status}>"
