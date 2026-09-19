from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.order import Order
from app.models.user import User
from app.schemas.order import OrderCreateRequest, OrderResponse
from app.services.news_actions import exit_position_on_news
from app.services.order_service import (
    create_order as create_order_service,
    PriceUnavailableError,
    InsufficientBalanceError,
)
from app.services.rate_limiter import enforce_rate_limit

router = APIRouter(prefix="/api/v1/orders", tags=["orders"])

# Rate limit: at most 10 order submissions per user per 60 seconds.
ORDER_RATE_LIMIT_MAX = 10
ORDER_RATE_LIMIT_WINDOW_SECONDS = 60


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order_endpoint(
    payload: OrderCreateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        key=f"orders:{current_user.id}",
        max_requests=ORDER_RATE_LIMIT_MAX,
        window_seconds=ORDER_RATE_LIMIT_WINDOW_SECONDS,
    )

    try:
        order = await create_order_service(db=db, user=current_user, request=payload)
        return order
    except PriceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except InsufficientBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


class ExitOnNewsRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)


@router.post("/exit-on-news", response_model=OrderResponse,
             status_code=status.HTTP_201_CREATED)
async def exit_on_news(
    payload: ExitOnNewsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    USER-triggered only: one-tap full exit of the open position in
    `ticker` at MARKET (slippage + fees via the standard fill path),
    tagged triggered_by=NEWS_EVENT. The engine itself never calls this.
    """
    await enforce_rate_limit(
        key=f"orders:{current_user.id}",
        max_requests=ORDER_RATE_LIMIT_MAX,
        window_seconds=ORDER_RATE_LIMIT_WINDOW_SECONDS,
    )
    try:
        return await exit_position_on_news(db, current_user, payload.ticker)
    except PriceUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except InsufficientBalanceError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.get("/", response_model=list[OrderResponse])
async def list_orders(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Order)
        .where(Order.user_id == current_user.id)
        .order_by(Order.created_at.desc())
    )
    return result.scalars().all()
