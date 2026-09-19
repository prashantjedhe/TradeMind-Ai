from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.strategy import StrategyStatus
from app.models.user import User
from app.schemas.strategy import StrategyCreate, StrategyOut, StrategyUpdate
from app.services.strategy_service import (
    create_strategy,
    delete_strategy,
    get_strategy,
    list_strategies,
    set_strategy_status,
    update_strategy,
)
from app.services.strategy_templates import list_templates

router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


def _not_found():
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Strategy not found",
    )


@router.get("/templates")
async def list_strategy_templates_endpoint(
    current_user: User = Depends(get_current_user),
):
    """Return the catalog of pre-built classic trading strategy templates."""
    return list_templates()


@router.post("/", response_model=StrategyOut, status_code=status.HTTP_201_CREATED)
async def create_strategy_endpoint(
    payload: StrategyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await create_strategy(db=db, user=current_user, data=payload)


@router.get("/", response_model=list[StrategyOut])
async def list_strategies_endpoint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await list_strategies(db=db, user=current_user)


@router.get("/{strategy_id}", response_model=StrategyOut)
async def get_strategy_endpoint(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = await get_strategy(db=db, user=current_user, strategy_id=strategy_id)
    if strategy is None:
        raise _not_found()
    return strategy


@router.patch("/{strategy_id}", response_model=StrategyOut)
async def update_strategy_endpoint(
    strategy_id: str,
    payload: StrategyUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = await update_strategy(db=db, user=current_user, strategy_id=strategy_id, data=payload)
    if strategy is None:
        raise _not_found()
    return strategy


@router.post("/{strategy_id}/activate", response_model=StrategyOut)
async def activate_strategy_endpoint(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = await set_strategy_status(
        db=db, user=current_user, strategy_id=strategy_id, status=StrategyStatus.ACTIVE
    )
    if strategy is None:
        raise _not_found()
    return strategy


@router.post("/{strategy_id}/pause", response_model=StrategyOut)
async def pause_strategy_endpoint(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    strategy = await set_strategy_status(
        db=db, user=current_user, strategy_id=strategy_id, status=StrategyStatus.PAUSED
    )
    if strategy is None:
        raise _not_found()
    return strategy


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy_endpoint(
    strategy_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deleted = await delete_strategy(db=db, user=current_user, strategy_id=strategy_id)
    if not deleted:
        raise _not_found()