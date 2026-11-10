"""
League / Competition service.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.order import Order, OrderStatus, OrderSide, TriggeredBy
from app.models.backtest_copy_league import League, LeagueCompetition, LeagueEntry, Badge, BadgeType

logger = logging.getLogger(__name__)


def _realize_order_pnl(
    orders: list[Order],
) -> tuple[float, int, int, dict[str, float], datetime | None]:
    """Match filled orders FIFO for both long and short positions."""
    long_lots: dict[str, deque[list[float]]] = {}
    short_lots: dict[str, deque[list[float]]] = {}
    total_pnl = 0.0
    wins = 0
    losses = 0
    daily_pnl: dict[str, float] = {}
    first_win_at = None

    for order in orders:
        quantity = int(order.quantity)
        if quantity <= 0:
            continue

        price = float(order.executed_price or 0)
        fee_per_share = float(order.total_fees or 0) / quantity
        ticker = order.ticker
        is_buy = order.side == OrderSide.BUY
        closing_book = short_lots if is_buy else long_lots
        opening_book = long_lots if is_buy else short_lots
        lots = closing_book.setdefault(ticker, deque())
        remaining = quantity
        close_timestamp = order.filled_at or order.created_at
        close_day = close_timestamp.strftime("%Y-%m-%d")

        while remaining > 0 and lots:
            entry_price, lot_quantity, lot_fees = lots[0]
            matched = min(remaining, int(lot_quantity))
            allocated_entry_fees = lot_fees * matched / lot_quantity
            exit_fees = fee_per_share * matched

            if is_buy:
                trade_pnl = (entry_price - price) * matched - allocated_entry_fees - exit_fees
            else:
                trade_pnl = (price - entry_price) * matched - allocated_entry_fees - exit_fees

            total_pnl += trade_pnl
            daily_pnl[close_day] = daily_pnl.get(close_day, 0.0) + trade_pnl
            wins += int(trade_pnl > 0)
            losses += int(trade_pnl < 0)
            if trade_pnl > 0 and first_win_at is None:
                first_win_at = close_timestamp
            remaining -= matched

            if matched == int(lot_quantity):
                lots.popleft()
            else:
                lot_quantity -= matched
                lot_fees -= allocated_entry_fees
                lots[0] = [entry_price, lot_quantity, lot_fees]

        if remaining:
            opening_book.setdefault(ticker, deque()).append(
                [price, remaining, fee_per_share * remaining]
            )

    return total_pnl, wins, losses, daily_pnl, first_win_at


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


async def compute_entry_metrics(
    db: AsyncSession,
    entry: LeagueEntry,
    league: League,
) -> LeagueEntry:
    """
    Compute real metrics for a league entry from the user's filled orders
    during the league period.
    """
    # Fetch all FILLED orders for this user during the league window
    result = await db.execute(
        select(Order).where(
            Order.user_id == entry.user_id,
            Order.status == OrderStatus.FILLED,
            func.coalesce(Order.filled_at, Order.created_at) >= league.start_date,
            func.coalesce(Order.filled_at, Order.created_at) <= league.end_date,
        ).order_by(func.coalesce(Order.filled_at, Order.created_at).asc())
    )
    orders = list(result.scalars().all())

    total_pnl, wins, losses, daily_returns, first_win_at = _realize_order_pnl(orders)

    total_trades = wins + losses
    win_rate = wins / total_trades if total_trades > 0 else 0.0

    # Compute Sharpe Ratio from daily P&L returns (annualized)
    initial_balance = float(league.initial_balance)
    daily_pnl_list = list(daily_returns.values())
    sharpe = 0.0
    max_drawdown = 0.0
    return_pct = total_pnl / initial_balance if initial_balance > 0 else 0.0

    if len(daily_pnl_list) > 1:
        daily_ret_pct = [p / initial_balance for p in daily_pnl_list]
        mean_ret = sum(daily_ret_pct) / len(daily_ret_pct)
        variance = sum((r - mean_ret) ** 2 for r in daily_ret_pct) / (len(daily_ret_pct) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 0.0
        sharpe = (mean_ret / std_dev * math.sqrt(252)) if std_dev > 0 else 0.0

        # Max drawdown from cumulative P&L
        cum_pnl = 0.0
        peak = 0.0
        for pnl in daily_pnl_list:
            cum_pnl += pnl
            peak = max(peak, cum_pnl)
            drawdown = (peak - cum_pnl) / (initial_balance + peak) if (initial_balance + peak) > 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

    entry.final_pnl = total_pnl
    entry.final_trades = total_trades
    entry.final_win_rate = win_rate
    entry.final_sharpe = sharpe
    entry.final_return_pct = return_pct
    entry.final_drawdown = max_drawdown
    entry._first_win_at = first_win_at
    return entry


async def compute_league_rankings(
    db: AsyncSession, league_id: str
) -> list[LeagueEntry]:
    """
    Compute real metrics + rank all entries by final Sharpe Ratio.
    Updates final_rank on each entry.
    """
    result = await db.execute(select(League).where(League.id == league_id))
    league = result.scalar_one_or_none()
    if league is None:
        return []

    result2 = await db.execute(
        select(LeagueEntry).where(LeagueEntry.league_id == league_id)
    )
    entries = list(result2.scalars().all())

    # Compute real metrics for each entry
    for entry in entries:
        await compute_entry_metrics(db, entry, league)

    # Sort by Sharpe (desc), then by return_pct (desc) as tiebreaker
    entries.sort(key=lambda e: (e.final_sharpe, e.final_return_pct), reverse=True)

    for i, entry in enumerate(entries, 1):
        entry.final_rank = i

    await db.commit()
    return entries


async def finalize_league(
    db: AsyncSession, league_id: str
) -> list[LeagueEntry]:
    """
    End-of-month league finalization:
    1. Compute final metrics for each entry from real orders
    2. Assign rankings
    3. Award badges
    4. Mark league COMPLETED
    """
    result = await db.execute(select(League).where(League.id == league_id))
    league = result.scalar_one_or_none()
    if league is None:
        raise ValueError("League not found")

    entries = await compute_league_rankings(db, league_id)

    # Award badges based on final standings
    news_orders = await db.execute(
        select(Order.user_id)
        .where(
            Order.status == OrderStatus.FILLED,
            Order.triggered_by == TriggeredBy.NEWS_EVENT,
            func.coalesce(Order.filled_at, Order.created_at) >= league.start_date,
            func.coalesce(Order.filled_at, Order.created_at) <= league.end_date,
            Order.user_id.in_([entry.user_id for entry in entries]),
        )
        .distinct()
    ) if entries else None
    news_trader_ids = {
        row[0] for row in news_orders.all()
    } if news_orders is not None else set()
    badge_assignments = _compute_badges(entries, league, news_trader_ids)
    for entry, badge_type, description in badge_assignments:
        # Avoid duplicate badges
        existing_badge = await db.execute(
            select(Badge).where(
                Badge.league_id == league.id,
                Badge.user_id == entry.user_id,
                Badge.badge_type == badge_type,
            )
        )
        if existing_badge.scalar_one_or_none() is None:
            badge = Badge(
                league_id=league.id,
                user_id=entry.user_id,
                badge_type=badge_type,
                description=description,
            )
            db.add(badge)

    league.status = LeagueCompetition.COMPLETED
    await db.commit()
    return entries


def _compute_badges(
    entries: list[LeagueEntry],
    league: League,
    news_trader_ids: set | None = None,
) -> list[tuple]:
    """Determine which badges to award based on standings."""
    assignments = []

    if not entries:
        return assignments

    with_trades = [e for e in entries if e.final_trades > 0]

    # Top 3 by Sharpe: Top Trader
    top3 = sorted(with_trades, key=lambda e: e.final_sharpe, reverse=True)[:3]
    for entry in top3:
        assignments.append((
            entry, BadgeType.TOP_TRADER,
            f"Top {entry.final_rank} performer in {league.name}"
        ))

    # Lowest drawdown: Drawdown Master (only if they have trades)
    if with_trades:
        lowest_dd = min(with_trades, key=lambda e: e.final_drawdown)
        assignments.append((
            lowest_dd, BadgeType.DRAWDOWN_MASTER,
            f"Smallest drawdown ({lowest_dd.final_drawdown:.1%}) in {league.name}"
        ))

    # Most consistent: highest Sharpe with most trades (>= 20)
    consistent_candidates = [e for e in entries if e.final_trades >= 20]
    if consistent_candidates:
        most_consistent = max(consistent_candidates, key=lambda e: e.final_sharpe)
        assignments.append((
            most_consistent, BadgeType.CONSISTENT_PERFORMER,
            f"Consistent performer ({most_consistent.final_trades} trades) in {league.name}"
        ))

    # News Ninja requires an actual news-triggered filled order.
    news_candidates = [
        entry for entry in entries
        if entry.user_id in (news_trader_ids or set())
    ]
    if news_candidates:
        news_trader = max(news_candidates, key=lambda entry: entry.final_sharpe)
        assignments.append((
            news_trader, BadgeType.NEWS_NINJA,
            f"News-driven trading performance in {league.name}"
        ))

    # First Win: participant with the earliest profitable closed trade.
    first_win_candidates = [
        entry for entry in with_trades if getattr(entry, "_first_win_at", None) is not None
    ]
    if first_win_candidates:
        first = min(first_win_candidates, key=lambda entry: entry._first_win_at)
        assignments.append((
            first, BadgeType.FIRST_WIN,
            f"First participant to record a profitable trade in {league.name}"
        ))

    return assignments


async def get_league_leaderboard(
    db: AsyncSession, league_id: str
) -> list[dict]:
    """Get formatted leaderboard data with usernames."""
    entries = await compute_league_rankings(db, league_id)

    # Fetch usernames for all entries
    user_ids = [entry.user_id for entry in entries]
    username_map: dict = {}
    if user_ids:
        users_result = await db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        for u in users_result.scalars().all():
            username_map[u.id] = u.username

    # Fetch badges per user in this league
    badges_result = await db.execute(
        select(Badge).where(Badge.league_id == league_id)
    )
    user_badges: dict = {}
    for badge in badges_result.scalars().all():
        user_badges.setdefault(badge.user_id, []).append(badge.badge_type.value)

    return [{
        "rank": entry.final_rank,
        "user_id": str(entry.user_id),
        "username": username_map.get(entry.user_id, str(entry.user_id)[:8]),
        "sharpe": float(entry.final_sharpe),
        "return_pct": float(entry.final_return_pct),
        "drawdown": float(entry.final_drawdown),
        "trades": entry.final_trades,
        "win_rate": float(entry.final_win_rate),
        "pnl": float(entry.final_pnl),
        "badges": user_badges.get(entry.user_id, []),
    } for entry in entries]


async def check_and_finalize_expired_leagues(db: AsyncSession) -> list[str]:
    """
    Find all ACTIVE leagues whose end_date has passed and finalize them.
    Called by the Celery daily reset task.
    Returns list of finalized league IDs.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(League).where(
            League.status == LeagueCompetition.ACTIVE,
            League.end_date <= now,
        )
    )
    expired = list(result.scalars().all())
    finalized_ids = []
    for league in expired:
        try:
            await finalize_league(db, str(league.id))
            finalized_ids.append(str(league.id))
            logger.info(f"League {league.id} ({league.name}) finalized automatically.")
        except Exception as e:
            logger.error(f"Failed to finalize league {league.id}: {e}")
    return finalized_ids


async def get_my_leagues(
    db: AsyncSession, user: User
) -> list[dict]:
    """Get leagues this user has joined with league names."""
    result = await db.execute(
        select(LeagueEntry, League)
        .join(League, LeagueEntry.league_id == League.id)
        .where(LeagueEntry.user_id == user.id)
        .order_by(LeagueEntry.joined_at.desc())
    )
    rows = result.all()
    return [{
        "id": str(entry.id),
        "league_id": str(entry.league_id),
        "league_name": league.name,
        "league_status": league.status.value,
        "joined_at": entry.joined_at.isoformat(),
        "final_rank": entry.final_rank,
        "final_sharpe": float(entry.final_sharpe),
        "final_return_pct": float(entry.final_return_pct),
        "final_drawdown": float(entry.final_drawdown),
        "final_trades": entry.final_trades,
        "final_win_rate": float(entry.final_win_rate),
        "final_pnl": float(entry.final_pnl),
        "created_at": entry.created_at.isoformat(),
    } for entry, league in rows]


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