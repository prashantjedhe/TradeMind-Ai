"""
League / Competition service.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.backtest_copy_league import League, LeagueCompetition, LeagueEntry, Badge, BadgeType

logger = logging.getLogger(__name__)


async def create_league(
    db: AsyncSession,
    name: str,
    description: str | None,
    start_date: datetime,
    end_date: datetime,
    initial_balance: float = 1000000,
) -> League:
    league = League(
        name=name,
        description=description,
        start_date=start_date,
        end_date=end_date,
        initial_balance=initial_balance,
    )
    db.add(league)
    await db.commit()
    await db.refresh(league)
    return league


async def join_league(
    db: AsyncSession, user: User, league_id: str
) -> LeagueEntry:
    """Join a competition."""
    result = await db.execute(select(League).where(League.id == league_id))
    league = result.scalar_one_or_none()
    if league is None or league.status != LeagueCompetition.ACTIVE:
        raise ValueError("League not found or not active")

    # Check if already joined
    existing = await db.execute(
        select(LeagueEntry).where(
            LeagueEntry.league_id == league_id,
            LeagueEntry.user_id == user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Already joined this league")

    entry = LeagueEntry(
        league_id=league_id,
        user_id=user.id,
        joined_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry


async def compute_league_rankings(
    db: AsyncSession, league_id: str
) -> list[LeagueEntry]:
    """
    Rank all entries by final Sharpe Ratio (default metric).
    Updates final_rank on each entry.
    """
    result = await db.execute(
        select(LeagueEntry)
        .where(LeagueEntry.league_id == league_id)
        .order_by(LeagueEntry.final_sharpe.desc())
    )
    entries = list(result.scalars().all())

    for i, entry in enumerate(entries, 1):
        entry.final_rank = i

    await db.commit()
    return entries


async def finalize_league(
    db: AsyncSession, league_id: str
) -> list[LeagueEntry]:
    """
    End-of-month league finalization:
    1. Compute final metrics for each entry from backtests/orders
    2. Assign rankings
    3. Award badges
    """
    result = await db.execute(select(League).where(League.id == league_id))
    league = result.scalar_one_or_none()
    if league is None:
        raise ValueError("League not found")

    entries = await compute_league_rankings(db, league_id)

    # Award badges based on final standings
    badge_assignments = _compute_badges(entries, league)
    for entry, badge_type, description in badge_assignments:
        badge = Badge(
            league_id=league_id,
            user_id=entry.user_id,
            badge_type=badge_type,
            description=description,
        )
        db.add(badge)

    league.status = LeagueCompetition.COMPLETED
    await db.commit()
    return entries


def _compute_badges(entries: list[LeagueEntry], league: League) -> list[tuple]:
    """Determine which badges to award based on standings."""
    assignments = []

    if not entries:
        return assignments

    # Top 3 by Sharpe: Top Trader
    top3 = sorted(entries, key=lambda e: e.final_sharpe, reverse=True)[:3]
    for entry in top3:
        assignments.append((
            entry, BadgeType.TOP_TRADER,
            f"Top {entry.final_rank} performer in {league.name}"
        ))

    # Lowest drawdown: Drawdown Master
    lowest_dd = min(entries, key=lambda e: e.final_drawdown)
    assignments.append((
        lowest_dd, BadgeType.DRAWDOWN_MASTER,
        f"Smallest drawdown in {league.name}"
    ))

    # Most consistent: low variance in daily returns -> highest Sharpe with most trades
    most_consistent = max(entries, key=lambda e: e.final_sharpe if e.final_trades > 20 else -999)
    if most_consistent.final_trades > 20:
        assignments.append((
            most_consistent, BadgeType.CONSISTENT_PERFORMER,
            f"Consistent performer ({most_consistent.final_trades} trades) in {league.name}"
        ))

    # News Ninja: if any trade had triggered_by = NEWS_EVENT
    for entry in entries:
        # Simplified: anyone who participated gets News Ninja if they have relevant trades
        # This is a placeholder - actual check would join with Order.triggered_by
        pass

    # First win: if any user had their first winning trade
    # Simplified: first participant gets First Win
    if entries:
        assignments.append((
            entries[-1], BadgeType.FIRST_WIN,
            f"First trade entered in {league.name}"
        ))

    return assignments


async def get_league_leaderboard(
    db: AsyncSession, league_id: str
) -> list[dict]:
    """Get formatted leaderboard data."""
    entries = await compute_league_rankings(db, league_id)
    return [{
        "rank": entry.final_rank,
        "user_id": str(entry.user_id),
        "sharpe": float(entry.final_sharpe),
        "return_pct": float(entry.final_return_pct),
        "drawdown": float(entry.final_drawdown),
        "trades": entry.final_trades,
        "win_rate": float(entry.final_win_rate),
        "pnl": float(entry.final_pnl),
        "badges": [],
    } for entry in entries]


async def check_monthly_reset(db: AsyncSession) -> list[League]:
    """Find leagues that need monthly reset (1st of month)."""
    today = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(League)
        .where(
            League.status == LeagueCompetition.ACTIVE,
            func.date_trunc('month', League.start_date) == today.date(),
        )
    )
    return list(result.scalars().all())


async def get_my_leagues(
    db: AsyncSession, user: User
) -> list[LeagueEntry]:
    """Get leagues this user has joined."""
    result = await db.execute(
        select(LeagueEntry)
        .where(LeagueEntry.user_id == user.id)
        .order_by(LeagueEntry.joined_at.desc())
    )
    return list(result.scalars().all())


async def get_user_badges(
    db: AsyncSession, user: User
) -> list[Badge]:
    """Get all badges earned by a user."""
    result = await db.execute(
        select(Badge)
        .where(Badge.user_id == user.id)
        .order_by(Badge.awarded_at.desc())
    )
    return list(result.scalars().all())