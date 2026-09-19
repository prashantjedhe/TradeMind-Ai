import uuid
from decimal import Decimal

from pydantic import BaseModel

from app.models.portfolio import PositionStatus


class PositionSummary(BaseModel):
    id: uuid.UUID
    ticker: str
    quantity: int
    avg_entry_price: Decimal
    current_price: Decimal | None  # None if price cache miss
    unrealised_pnl: Decimal | None  # None if current_price unavailable
    realised_pnl: Decimal
    status: PositionStatus

    class Config:
        from_attributes = True


class PortfolioSummaryResponse(BaseModel):
    virtual_balance: Decimal
    total_realised_pnl: Decimal  # lifetime, across all positions (open + closed)
    total_unrealised_pnl: Decimal  # across currently open positions only
    total_position_value: Decimal  # current market value of all open positions
    net_worth: Decimal  # virtual_balance + total_position_value
    positions: list[PositionSummary]
