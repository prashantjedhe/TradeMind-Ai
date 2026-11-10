from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.api.v1 import market as market_api
from app.api.v1.market import daily_change_pct


def test_daily_change_uses_previous_session_close_for_today():
    now = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)
    bars = [
        (datetime(2026, 10, 9, 3, 45, tzinfo=timezone.utc), 105.0),
        (datetime(2026, 10, 8, 3, 45, tzinfo=timezone.utc), 100.0),
    ]

    assert daily_change_pct(110.0, bars, now) == 10.0


def test_daily_change_uses_latest_close_when_no_bar_exists_today():
    now = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)
    bars = [(datetime(2026, 10, 8, 3, 45, tzinfo=timezone.utc), 100.0)]

    assert daily_change_pct(102.5, bars, now) == 2.5


def test_closed_market_uses_latest_completed_session_not_stale_quote():
    now = datetime(2026, 10, 9, 20, 0, tzinfo=timezone.utc)
    bars = [
        (datetime(2026, 10, 9, 3, 45, tzinfo=timezone.utc), 102.5),
        (datetime(2026, 10, 8, 3, 45, tzinfo=timezone.utc), 100.0),
    ]

    assert daily_change_pct(100.0, bars, now) == 2.5


def test_daily_change_is_unavailable_without_valid_reference_close():
    now = datetime(2026, 10, 9, 8, 0, tzinfo=timezone.utc)
    today_only = [(datetime(2026, 10, 9, 3, 45, tzinfo=timezone.utc), 100.0)]
    prior_close_zero = [(datetime(2026, 10, 8, 3, 45, tzinfo=timezone.utc), 0.0)]

    assert daily_change_pct(101.0, today_only, now) is None
    assert daily_change_pct(101.0, prior_close_zero, now) is None
    assert daily_change_pct(None, prior_close_zero, now) is None


@pytest.mark.asyncio
async def test_prices_endpoint_returns_change_from_previous_close(monkeypatch):
    now = datetime.now(timezone.utc)
    bars = [
        ("NIFTY", now, 100.0),
        ("NIFTY", datetime(2026, 10, 8, 3, 45, tzinfo=timezone.utc), 98.0),
    ]

    class FakeDB:
        async def execute(self, statement):
            return SimpleNamespace(all=lambda: bars)

    async def fake_get_cached_prices(tickers):
        assert tickers == ["NIFTY"]
        return {"NIFTY": 101.0}

    monkeypatch.setattr(market_api.settings, "WATCHLIST_TICKERS", ["NIFTY"])
    monkeypatch.setattr(market_api, "get_cached_prices", fake_get_cached_prices)
    user = SimpleNamespace(id="test-user")

    response = await market_api.get_prices(user, FakeDB())

    assert response["prices"] == {"NIFTY": "101.0"}
    assert response["changes"]["NIFTY"] == 2.04
    assert response["change_period"] == "LAST SESSION"
