import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import pytest

from app.models.backtest_copy_league import League, LeagueCompetition, LeagueEntry, BadgeType
from app.models.order import OrderSide
from app.services.league_service import _compute_badges, _realize_order_pnl


def test_compute_badges_allocates_top_trader_and_drawdown_master():
    league = SimpleNamespace(
        id=uuid.uuid4(),
        name="September Alpha Challenge",
        status=LeagueCompetition.ACTIVE,
    )

    entry1 = SimpleNamespace(
        user_id=uuid.uuid4(),
        final_rank=1,
        final_sharpe=2.45,
        final_return_pct=0.35,
        final_drawdown=0.08,
        final_trades=25,
        final_pnl=350000.0,
        joined_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    entry2 = SimpleNamespace(
        user_id=uuid.uuid4(),
        final_rank=2,
        final_sharpe=1.85,
        final_return_pct=0.20,
        final_drawdown=0.03,  # Lowest drawdown!
        final_trades=15,
        final_pnl=200000.0,
        joined_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )

    entries = [entry1, entry2]
    assignments = _compute_badges(entries, league)

    badge_types = [b[1] for b in assignments]
    assert BadgeType.TOP_TRADER in badge_types
    assert BadgeType.DRAWDOWN_MASTER in badge_types
    assert BadgeType.CONSISTENT_PERFORMER in badge_types  # entry1 has >= 20 trades


def test_realize_order_pnl_matches_long_and_short_round_trips():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    orders = [
        SimpleNamespace(
            ticker="ABC", side=OrderSide.BUY, quantity=2, executed_price=100,
            total_fees=2, filled_at=start, created_at=start,
        ),
        SimpleNamespace(
            ticker="ABC", side=OrderSide.SELL, quantity=2, executed_price=110,
            total_fees=2, filled_at=start + timedelta(days=1),
            created_at=start + timedelta(days=1),
        ),
        SimpleNamespace(
            ticker="XYZ", side=OrderSide.SELL, quantity=3, executed_price=100,
            total_fees=3, filled_at=start, created_at=start,
        ),
        SimpleNamespace(
            ticker="XYZ", side=OrderSide.BUY, quantity=3, executed_price=90,
            total_fees=3, filled_at=start + timedelta(days=1),
            created_at=start + timedelta(days=1),
        ),
    ]

    pnl, wins, losses, daily_pnl, first_win_at = _realize_order_pnl(orders)

    assert pnl == 40
    assert wins == 2
    assert losses == 0
    assert daily_pnl == {"2026-09-02": 40}
    assert first_win_at == start + timedelta(days=1)


def test_realize_order_pnl_does_not_count_unclosed_positions_as_profit():
    timestamp = datetime(2026, 9, 1, tzinfo=timezone.utc)
    orders = [
        SimpleNamespace(
            ticker="ABC", side=OrderSide.SELL, quantity=2, executed_price=100,
            total_fees=1, filled_at=timestamp, created_at=timestamp,
        )
    ]

    pnl, wins, losses, daily_pnl, first_win_at = _realize_order_pnl(orders)

    assert pnl == 0
    assert wins == 0
    assert losses == 0
    assert daily_pnl == {}
    assert first_win_at is None


def test_news_ninja_badge_requires_a_news_triggered_trade():
    league = SimpleNamespace(name="September Alpha Challenge")
    entry = SimpleNamespace(
        user_id=uuid.uuid4(),
        final_rank=1,
        final_sharpe=3.0,
        final_return_pct=0.4,
        final_drawdown=0.02,
        final_trades=25,
        final_pnl=400000.0,
        joined_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
    )

    no_news_badges = _compute_badges([entry], league)
    news_badges = _compute_badges([entry], league, {entry.user_id})

    assert BadgeType.NEWS_NINJA not in [badge[1] for badge in no_news_badges]
    assert BadgeType.NEWS_NINJA in [badge[1] for badge in news_badges]
