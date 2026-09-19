from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.backtest_copy_league import BacktestResult
from app.services.backtest_service import run_backtest, run_walk_forward
from app.schemas.backtest_league import BacktestRequest, BacktestResultOut

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResultOut, status_code=status.HTTP_201_CREATED)
async def run_backtest_endpoint(
    strategy_id: str | None = None,
    ticker: str = "RELIANCE",
    timeframe: str = "1d",
    years: int = 2,
    request: BacktestRequest | None = Body(default=None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Standard backtest: replay a strategy against OHLCV bars."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=years * 365)
    if request is not None:
        strategy_id = request.strategy_id
        ticker = request.ticker
        timeframe = request.timeframe
        years = request.years
    result = await run_backtest(
        db=db, user=current_user, strategy_id=strategy_id,
        ticker=ticker.upper(), timeframe=timeframe,
        start_date=start_date, end_date=end_date,
        strategy_config=request.model_dump(mode="json") if request and not request.strategy_id else None,
    )
    return result


@router.post("/walk-forward", response_model=BacktestResultOut, status_code=status.HTTP_201_CREATED)
async def walk_forward_endpoint(
    strategy_id: str | None = None,
    ticker: str = "RELIANCE",
    timeframe: str = "1d",
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Walk-forward backtest: rolling 3yr train / 1yr test windows."""
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=4 * 365)
    result = await run_walk_forward(
        db=db, user=current_user, strategy_id=strategy_id,
        ticker=ticker.upper(), timeframe=timeframe,
        start_date=start_date, end_date=end_date,
    )
    return result


@router.get("/", response_model=list[BacktestResultOut])
async def list_backtests(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all backtest results."""
    result = await db.execute(
        select(BacktestResult)
        .where(BacktestResult.user_id == current_user.id)
        .order_by(BacktestResult.created_at.desc())
    )
    return list(result.scalars().all())


@router.get("/{backtest_id}", response_model=BacktestResultOut)
async def get_backtest(
    backtest_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific backtest result."""
    result = await db.execute(
        select(BacktestResult).where(
            BacktestResult.id == backtest_id,
            BacktestResult.user_id == current_user.id,
        )
    )
    bt = result.scalar_one_or_none()
    if bt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backtest not found")
    return bt