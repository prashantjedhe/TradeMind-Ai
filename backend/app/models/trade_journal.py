import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TradeJournal(Base):
    """
    AI-generated trade journal entries (Claude, advisory-only).

    Each row snapshots the structured context that was sent (so the
    entry stays interpretable even as prices move on) plus the model
    text. Nothing here ever feeds back into order execution -- the
    journal is read-only insight, never a trading signal.
    """

    __tablename__ = "trade_journal"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="advisor")
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(60), nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="journal_entries")

    def __repr__(self) -> str:
        return f"<TradeJournal {self.kind} user={self.user_id}>"
