from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone
from typing import Any

from app.api.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.backtest_copy_league import League, LeagueCompetition, LeagueEntry, Badge
from app.services.league_service import (
    create_league, join_league, finalize_league,
    get_league_leaderboard, get_my_leagues, get_user_badges,
)
from app.schemas.backtest_league import (
    LeagueOut, BadgeOut,
    LeaderboardEntry, CreateLeagueRequest, JoinLeagueResponse,
    MyLeagueEntryOut,
)

router = APIRouter(prefix="/api/v1/league", tags=["league"])


@router.post("/", response_model=LeagueOut, status_code=status.HTTP_201_CREATED)
async def create_league_endpoint(
    payload: CreateLeagueRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new competition league."""
    start = datetime.now(timezone.utc)
    end = start + timedelta(days=payload.duration_days)
    league = await create_league(
        db, payload.name, payload.description, start, end, payload.initial_balance
    )
    return league


@router.post("/{league_id}/join", response_model=JoinLeagueResponse)
async def join_league_endpoint(
    league_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Join a competition."""
    try:
        entry = await join_league(db, current_user, league_id)
        return {"id": str(entry.id), "league_id": league_id, "status": "joined"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{league_id}/leaderboard", response_model=list[LeaderboardEntry])
async def leaderboard_endpoint(
    league_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get league leaderboard with real metrics and usernames."""
    return await get_league_leaderboard(db, league_id)


@router.post("/{league_id}/finalize")
async def finalize_league_endpoint(
    league_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Finalize an expired active league and award badges."""
    result = await db.execute(select(League).where(League.id == league_id))
    league = result.scalar_one_or_none()
    if league is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="League not found")
    if league.status != LeagueCompetition.ACTIVE:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="League is not active")
    if league.end_date > datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="League has not ended")

    try:
        entries = await finalize_league(db, league_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return [
        {"rank": e.final_rank, "user_id": str(e.user_id), "sharpe": float(e.final_sharpe)}
        for e in entries
    ]


@router.get("/my", response_model=list[MyLeagueEntryOut])
async def list_my_leagues(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get leagues this user has joined."""
    entries = await get_my_leagues(db, current_user)
    return entries


@router.get("/", response_model=list[LeagueOut])
async def list_active_leagues(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active and upcoming leagues."""
    result = await db.execute(
        select(League)
        .where(League.status.in_([LeagueCompetition.ACTIVE, LeagueCompetition.UPCOMING]))
        .order_by(League.created_at.desc())
    )
    leagues = list(result.scalars().all())
    return leagues


@router.get("/all", response_model=list[LeagueOut])
async def list_all_leagues(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all leagues including completed."""
    result = await db.execute(
        select(League).order_by(League.created_at.desc())
    )
    leagues = list(result.scalars().all())
    return leagues


@router.get("/badges/me", response_model=list[BadgeOut])
async def list_my_badges(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all badges earned by the current user."""
    badges = await get_user_badges(db, current_user)
    return badges


@router.get("/{league_id}/badges", response_model=list[BadgeOut])
async def list_league_badges(
    league_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get badges earned by current user in this league."""
    badges = await get_user_badges(db, current_user)
    return [b for b in badges if str(b.league_id) == league_id]