import uuid
import enum
from datetime import datetime
from sqlalchemy import String, Numeric, DateTime, ForeignKey, Enum as SQLEnum, Index, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BacktestStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class BacktestKind(str, enum.Enum):
    STANDARD = "STANDARD"
    WALK_FORWARD = "WALK_FORWARD"


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False, default="1d")
    kind: Mapped[BacktestKind] = mapped_column(
        SQLEnum(BacktestKind), nullable=False, default=BacktestKind.STANDARD, index=True
    )
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    train_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    train_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    test_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[BacktestStatus] = mapped_column(
        SQLEnum(BacktestStatus), nullable=False, default=BacktestStatus.RUNNING, index=True
    )
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    cagr: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    sharpe: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    sortino: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    calmar: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    max_drawdown: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    volatility: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    profit_factor: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    total_trades: Mapped[int] = mapped_column(nullable=False, default=0)
    total_pnl: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    final_equity: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    initial_capital: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=1000000)
    total_fees: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    slippage_bps: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False, default=5)
    sl_pct: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    tp_pct: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)

    is_sharpe: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    oos_sharpe: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    efficiency_ratio: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    num_windows: Mapped[int] = mapped_column(nullable=False, default=0)
    window_results: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    equity_curve: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    trade_ledger: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    assumptions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user = relationship("User", back_populates="backtests")
    strategy = relationship("Strategy", back_populates="backtests")

    __table_args__ = (
        Index("ix_backtest_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Backtest {self.id} ticker={self.ticker} sharpe={self.sharpe:.2f}>"


class LeagueCompetition(str, enum.Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    UPCOMING = "UPCOMING"


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_balance: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=1000000)
    status: Mapped[LeagueCompetition] = mapped_column(
        SQLEnum(LeagueCompetition), nullable=False, default=LeagueCompetition.ACTIVE
    )
    ranking_metric: Mapped[str] = mapped_column(String(20), nullable=False, default="sharpe")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_league_active", "status"),
    )

    entries = relationship("LeagueEntry", back_populates="league", cascade="all, delete-orphan")
    badges = relationship("Badge", back_populates="league", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<League {self.id} {self.name} {self.status}>"


class LeagueEntry(Base):
    __tablename__ = "league_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    final_sharpe: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    final_return_pct: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False, default=0)
    final_drawdown: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    final_trades: Mapped[int] = mapped_column(nullable=False, default=0)
    final_win_rate: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    final_pnl: Mapped[float] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    final_rank: Mapped[int | None] = mapped_column(nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    league = relationship("League", back_populates="entries")
    user = relationship("User", back_populates="league_entries")

    __table_args__ = (
        Index("ix_league_entry_league_user", "league_id", "user_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<LeagueEntry {self.user_id} league={self.league_id} rank={self.final_rank}>"


class BadgeType(str, enum.Enum):
    CONSISTENT_PERFORMER = "Consistent Performer"
    DRAWDOWN_MASTER = "Drawdown Master"
    NEWS_NINJA = "News Ninja"
    TOP_TRADER = "Top Trader"
    MARATHON_BET = "Marathon Bet"
    FIRST_WIN = "First Win"


class Badge(Base):
    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    league_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("leagues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    badge_type: Mapped[BadgeType] = mapped_column(SQLEnum(BadgeType), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    awarded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    league = relationship("League", back_populates="badges")
    user = relationship("User", back_populates="badges")

    __table_args__ = (
        Index(
            "ix_badge_league_user_type",
            "league_id",
            "user_id",
            "badge_type",
            unique=True,
        ),
    )

    def __repr__(self) -> str:
        return f"<Badge {self.user_id} {self.badge_type}>"