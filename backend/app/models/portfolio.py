import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PositionStatus(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    quantity: Mapped[int] = mapped_column(nullable=False, default=0)
    avg_entry_price: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False, default=0)

    realised_pnl: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    unrealised_pnl: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)

    status: Mapped[PositionStatus] = mapped_column(
        SQLEnum(PositionStatus), nullable=False, default=PositionStatus.OPEN, index=True
    )

    opened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user = relationship("User", back_populates="positions")

    def __repr__(self) -> str:
        return f"<Position {self.ticker} qty={self.quantity} status={self.status}>"
