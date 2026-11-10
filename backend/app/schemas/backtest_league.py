from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, ConfigDict, Field
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
    error_message: Optional[str] = None
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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class MyLeagueEntryOut(BaseModel):
    """League entry with league name for 'My Leagues' view."""
    id: str
    league_id: str
    league_name: str
    league_status: str
    joined_at: str
    final_rank: Optional[int] = None
    final_sharpe: float
    final_return_pct: float
    final_drawdown: float
    final_trades: int
    final_win_rate: float
    final_pnl: float
    created_at: str


class BadgeOut(BaseModel):
    id: uuid.UUID
    league_id: uuid.UUID
    user_id: uuid.UUID
    badge_type: BadgeType
    description: str
    awarded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    username: str
    sharpe: float
    return_pct: float
    drawdown: float
    trades: int
    win_rate: float
    pnl: float
    badges: list[str]


class CreateLeagueRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = Field(default=None, max_length=500)
    initial_balance: float = Field(default=1000000, gt=0)
    duration_days: int = Field(default=30, ge=1, le=365)


class JoinLeagueResponse(BaseModel):
    id: str
    league_id: str
    status: str