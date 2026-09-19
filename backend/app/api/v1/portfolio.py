from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.portfolio import PortfolioSummaryResponse
from app.services.portfolio_service import get_portfolio_summary

router = APIRouter(prefix="/api/v1/portfolio", tags=["portfolio"])


@router.get("/summary", response_model=PortfolioSummaryResponse)
async def portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_portfolio_summary(db=db, user=current_user)
