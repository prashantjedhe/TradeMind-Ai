"""Persist expiring trade setups for explicit user confirmation."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.trade_proposal import TradeProposal

PROPOSAL_TTL_MINUTES = 15


async def create_trade_proposal(
    db: AsyncSession,
    *,
    proposal_key: str,
    user_id,
    strategy_id,
    ticker: str,
    side: str,
    quantity: int,
    settlement_type: str,
    limit_price: Decimal,
    rationale: str,
    evidence: dict,
) -> TradeProposal:
    now = datetime.now(timezone.utc)
    statement = (
        insert(TradeProposal)
        .values(
            proposal_key=proposal_key,
            user_id=user_id,
            strategy_id=strategy_id,
            ticker=ticker,
            side=side,
            quantity=quantity,
            settlement_type=settlement_type,
            limit_price=limit_price,
            status="PROPOSED",
            rationale=rationale[:500],
            evidence=evidence,
            expires_at=now + timedelta(minutes=PROPOSAL_TTL_MINUTES),
        )
        .on_conflict_do_nothing(index_elements=["proposal_key"])
        .returning(TradeProposal.id)
    )
    inserted_id = (await db.execute(statement)).scalar_one_or_none()
    await db.commit()
    proposal = (await db.execute(
        select(TradeProposal).where(
            TradeProposal.id == inserted_id
            if inserted_id is not None
            else TradeProposal.proposal_key == proposal_key
        )
    )).scalar_one()
    return proposal


async def expire_trade_proposals(db: AsyncSession, user_id) -> None:
    await db.execute(
        update(TradeProposal)
        .where(
            TradeProposal.user_id == user_id,
            TradeProposal.status == "PROPOSED",
            TradeProposal.expires_at <= datetime.now(timezone.utc),
        )
        .values(status="EXPIRED")
    )
    await db.commit()
