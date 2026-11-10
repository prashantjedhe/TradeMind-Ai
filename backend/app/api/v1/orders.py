from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.order import Order, OrderSide, OrderStatus, OrderType, SettlementType, TriggeredBy
from app.models.strategy import Strategy, StrategyStatus
from app.models.trade_proposal import TradeProposal
from app.models.user import User
from app.schemas.order import OrderCreateRequest, OrderResponse, TradeProposalResponse
from app.services.news_actions import exit_position_manually, exit_position_on_news
from app.services.order_service import (
    create_order as create_order_service,
    PriceUnavailableError,
    InsufficientBalanceError,
)
from app.services.rate_limiter import enforce_rate_limit
from app.services.strategy_service import evaluate_strategy, opposing_strategy_context
from app.services.price_cache_service import get_price_or_derive

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


class PositionExitRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)


@router.post("/exit-on-news", response_model=OrderResponse,
             status_code=status.HTTP_201_CREATED)
async def exit_on_news(
    payload: PositionExitRequest,
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


@router.post("/manual-exit", response_model=OrderResponse,
             status_code=status.HTTP_201_CREATED)
async def manual_exit(
    payload: PositionExitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User-triggered full MARKET exit, independent of news events."""
    await enforce_rate_limit(
        key=f"orders:{current_user.id}",
        max_requests=ORDER_RATE_LIMIT_MAX,
        window_seconds=ORDER_RATE_LIMIT_WINDOW_SECONDS,
    )
    try:
        return await exit_position_manually(db, current_user, payload.ticker)
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


@router.get("/proposals", response_model=list[TradeProposalResponse])
async def list_trade_proposals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    await db.execute(
        update(TradeProposal)
        .where(
            TradeProposal.user_id == current_user.id,
            TradeProposal.status == "PROPOSED",
            TradeProposal.expires_at <= now,
        )
        .values(status="EXPIRED")
    )
    await db.commit()
    result = await db.execute(
        select(TradeProposal).where(
            TradeProposal.user_id == current_user.id,
            TradeProposal.status == "PROPOSED",
            TradeProposal.expires_at > now,
        ).order_by(TradeProposal.created_at.desc())
    )
    return result.scalars().all()


@router.post("/proposals/{proposal_id}/confirm", response_model=OrderResponse)
async def confirm_trade_proposal(
    proposal_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        key=f"orders:{current_user.id}",
        max_requests=ORDER_RATE_LIMIT_MAX,
        window_seconds=ORDER_RATE_LIMIT_WINDOW_SECONDS,
    )
    proposal = (await db.execute(
        select(TradeProposal).where(
            TradeProposal.id == proposal_id,
            TradeProposal.user_id == current_user.id,
        ).with_for_update()
    )).scalar_one_or_none()
    if proposal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade proposal not found")

    idempotency_reason = f"TRADE_PROPOSAL:{proposal.id}"
    existing = (await db.execute(
        select(Order).where(
            Order.user_id == current_user.id,
            Order.updated_reason == idempotency_reason,
        ).limit(1)
    )).scalar_one_or_none()
    if existing is not None:
        proposal.order_id = existing.id
        proposal.status = "CONFIRMED"
        await db.commit()
        return existing

    if proposal.status != "PROPOSED" or proposal.expires_at <= datetime.now(timezone.utc):
        if proposal.status == "PROPOSED":
            proposal.status = "EXPIRED"
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This trade proposal has expired or is no longer available.",
        )

    if await get_price_or_derive(proposal.ticker) is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No fresh market price is available for {proposal.ticker}.",
        )

    if proposal.strategy_id is not None:
        strategy = (await db.execute(
            select(Strategy).where(
                Strategy.id == proposal.strategy_id,
                Strategy.user_id == current_user.id,
            ).with_for_update()
        )).scalar_one_or_none()
        if strategy is None or strategy.status != StrategyStatus.ACTIVE:
            proposal.status = "INVALIDATED"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The strategy is no longer active; this proposal was invalidated.",
            )
        conflict = await opposing_strategy_context(db, strategy)
        condition_holds = await evaluate_strategy(db, strategy)
        if conflict or not condition_holds:
            if conflict:
                strategy.status = StrategyStatus.PAUSED
                strategy.paused_reason = conflict[:255]
            proposal.status = "INVALIDATED"
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=conflict or "The strategy setup is no longer valid.",
            )

    payload = OrderCreateRequest(
        ticker=proposal.ticker,
        order_type=OrderType.LIMIT,
        side=OrderSide(proposal.side),
        settlement_type=SettlementType(proposal.settlement_type),
        quantity=proposal.quantity,
        limit_price=Decimal(proposal.limit_price),
    )
    try:
        order = await create_order_service(
            db=db,
            user=current_user,
            request=payload,
            triggered_by=TriggeredBy.STRATEGY if proposal.strategy_id else TriggeredBy.NEWS_EVENT,
            updated_reason=idempotency_reason,
        )
    except PriceUnavailableError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except InsufficientBalanceError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    proposal.status = "CONFIRMED"
    proposal.order_id = order.id
    await db.commit()
    return order
