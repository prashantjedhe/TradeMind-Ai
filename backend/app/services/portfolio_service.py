"""
Portfolio summary service.

Reads current prices from the Redis cache (never calls the market
data client directly - keeps this endpoint fast, matching the same
cache-first design used by order execution).
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Position, PositionStatus
from app.models.user import User
from app.schemas.portfolio import PositionSummary, PortfolioSummaryResponse
from app.services.price_cache_service import get_price_or_derive

CENTS = Decimal("0.01")


async def get_portfolio_summary(db: AsyncSession, user: User) -> PortfolioSummaryResponse:
    # All positions (open + closed) for lifetime realised P&L.
    all_positions_result = await db.execute(
        select(Position).where(Position.user_id == user.id)
    )
    all_positions = all_positions_result.scalars().all()

    total_realised_pnl = sum((p.realised_pnl for p in all_positions), Decimal("0.00"))

    open_positions = [p for p in all_positions if p.status == PositionStatus.OPEN]

    position_summaries: list[PositionSummary] = []
    total_unrealised_pnl = Decimal("0.00")
    total_position_value = Decimal("0.00")

    for position in open_positions:
        current_price = await get_price_or_derive(position.ticker)

        if current_price is not None:
            # Works for both long (positive qty) and short (negative qty):
            # unrealised = (current - avg_entry) * qty
            unrealised = ((current_price - position.avg_entry_price) * position.quantity).quantize(CENTS)
            position_value = (current_price * position.quantity).quantize(CENTS)
            total_unrealised_pnl += unrealised
            total_position_value += position_value
        else:
            unrealised = None
            position_value = None

        position_summaries.append(
            PositionSummary(
                id=position.id,
                ticker=position.ticker,
                quantity=position.quantity,
                avg_entry_price=position.avg_entry_price,
                current_price=current_price,
                unrealised_pnl=unrealised,
                realised_pnl=position.realised_pnl,
                status=position.status,
            )
        )

    net_worth = (user.virtual_balance + total_position_value).quantize(CENTS)

    return PortfolioSummaryResponse(
        virtual_balance=user.virtual_balance,
        total_realised_pnl=total_realised_pnl,
        total_unrealised_pnl=total_unrealised_pnl,
        total_position_value=total_position_value,
        net_worth=net_worth,
        positions=position_summaries,
    )
