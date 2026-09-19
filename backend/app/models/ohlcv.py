import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Numeric, BigInteger, DateTime, Enum as SQLEnum, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class BarInterval(str, enum.Enum):
    ONE_DAY = "1d"
    FIFTEEN_MIN = "15m"


class OHLCVBar(Base):
    """
    Historical OHLCV candle storage.

    Note on data depth (a real constraint from yfinance/Yahoo Finance,
    not a design choice we made): daily (1d) bars are available for
    years of history, but intraday (15m) bars are only available for
    roughly the last 60 days. This is why walk-forward backtesting
    (Phase 4, 3-year train windows) will need to rely on daily bars,
    while 15m bars support only recent-history intraday strategies.
    """
    __tablename__ = "ohlcv_bars"
    __table_args__ = (
        UniqueConstraint("ticker", "interval", "timestamp", name="uq_ohlcv_ticker_interval_ts"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    interval: Mapped[BarInterval] = mapped_column(SQLEnum(BarInterval), nullable=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    open: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(12, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<OHLCVBar {self.ticker} {self.interval} {self.timestamp} close={self.close}>"
