from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from decimal import Decimal
from app.models.backtest_copy_league import BacktestStatus, LeagueCompetition, BadgeType
from app.schemas.strategy import ActionSchema, ConditionNode


class BacktestResultOut(BaseModel):
    id: uuid.UUID
    ticker: str
    timeframe: str
    start_date: datetime
    end_date: datetime
    status: BacktestStatus
    cagr: float
    sharpe: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    total_pnl: float
    final_equity: float
    initial_capital: float
    is_sharpe: float
    oos_sharpe: float
    efficiency_ratio: float
    num_windows: int
    window_results: Optional[list] = None
    equity_curve: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BacktestRequest(BaseModel):
    """Strategy configuration used for a pre-deployment backtest."""
    strategy_id: Optional[uuid.UUID] = None
    ticker: str
    timeframe: str = "1d"
    years: int = Field(default=2, ge=1, le=10)
    root_condition: Optional[ConditionNode] = None
    action: Optional[ActionSchema] = None


class LeagueOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str] = None
    start_date: datetime
    end_date: datetime
    initial_balance: float
    status: LeagueCompetition
    ranking_metric: str
    created_at: datetime

    class Config:
        from_attributes = True


class LeagueEntryOut(BaseModel):
    id: uuid.UUID
    league_id: uuid.UUID
    user_id: uuid.UUID
    joined_at: datetime
    final_sharpe: float
    final_return_pct: float
    final_drawdown: float
    final_trades: int
    final_win_rate: float
    final_pnl: float
    final_rank: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class BadgeOut(BaseModel):
    id: uuid.UUID
    league_id: uuid.UUID
    user_id: uuid.UUID
    badge_type: BadgeType
    description: str
    awarded_at: datetime

    class Config:
        from_attributes = True


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    sharpe: float
    return_pct: float
    drawdown: float
    trades: int
    win_rate: float
    pnl: float
    badges: list[str]


class CreateLeagueRequest(BaseModel):
    name: str
    description: Optional[str] = None
    initial_balance: float = 1000000
    duration_days: int = 30


class JoinLeagueResponse(BaseModel):
    id: str
    league_id: str
    status: str