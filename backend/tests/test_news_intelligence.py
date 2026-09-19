import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1 import news as news_api
from app.services import advisor


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


@pytest.mark.asyncio
async def test_get_latest_news_returns_article_details(monkeypatch):
    row = (
        "Reliance posts strong quarterly growth",
        "https://example.com/reliance", 
        "en",
        datetime(2026, 9, 18, 9, 30, tzinfo=timezone.utc),
        "Reuters",
        "IT",
        ["RELIANCE"],
        0.82,
        "POS",
        0.72,
        {"keywords": ["reliance", "growth", "earnings"]},
    )

    class FakeDB:
        async def execute(self, stmt):
            return FakeResult([row])

    user = SimpleNamespace(id=uuid.uuid4(), username="tester")
    result = await news_api.get_latest_news("RELIANCE", 10, user, FakeDB())

    assert result["ticker"] == "RELIANCE"
    assert result["articles"][0]["title"] == row[0]
    assert result["articles"][0]["source"] == "Reuters"
    assert result["articles"][0]["sector"] == "IT"
    assert result["articles"][0]["keywords"] == ["reliance", "growth", "earnings"]
    assert result["articles"][0]["score"] == 0.82


def test_news_advisor_without_api_key_returns_local_strategy(monkeypatch):
    monkeypatch.setattr(advisor.settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(advisor.settings, "OPENROUTER_API_KEY", "")
    message = advisor.advise_on_news({
        "ticker": "RELIANCE",
        "headline": "Reliance posts strong quarterly growth",
        "sentiment_score": 0.82,
        "sentiment_label": "POS",
        "sector": "IT",
    })

    assert message["ok"] is True
    assert "RELIANCE" in message["body"].upper()
    assert "Strategy Name" in message["body"]


def test_news_advisor_uses_openrouter_fallback(monkeypatch):
    monkeypatch.setattr(advisor.settings, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(advisor.settings, "OPENROUTER_API_KEY", "demo-key")
    called = {}

    def fake_call(prompt):
        called["prompt"] = prompt
        return "OpenRouter strategy: Buy the breakout on RELIANCE"

    monkeypatch.setattr(advisor, "_call_openrouter", fake_call)
    message = advisor.advise_on_news({
        "ticker": "RELIANCE",
        "headline": "Reliance posts strong quarterly growth",
        "sentiment_score": 0.82,
        "sentiment_label": "POS",
        "sector": "IT",
    })

    assert message["ok"] is True
    assert "OpenRouter strategy" in message["body"]
    assert "RELIANCE" in called["prompt"].upper()


@pytest.mark.asyncio
async def test_strategy_advisor_uses_news_context(monkeypatch):
    payload = news_api.AdvisorRequest(
        ticker="RELIANCE",
        headline="Reliance posts strong quarterly growth",
        sector="IT",
        sentiment_score=0.82,
        sentiment_label="POS",
        article_url="https://example.com/reliance",
    )
    user = SimpleNamespace(id=uuid.uuid4(), username="tester")

    async def fake_execute(stmt):
        return FakeResult([
            (
                "Reliance posts strong quarterly growth",
                "Reuters",
                datetime(2026, 9, 18, 9, 30, tzinfo=timezone.utc),
                "IT",
                "https://example.com/reliance",
                0.82,
                "POS",
                {"keywords": ["reliance", "growth"]},
            )
        ])

    fake_db = SimpleNamespace()
    fake_db.execute = AsyncMock(side_effect=fake_execute)
    fake_db.add = lambda obj: None
    fake_db.commit = AsyncMock()
    fake_db.refresh = AsyncMock()

    monkeypatch.setattr(advisor, "advise_on_news", lambda ctx: {"ok": True, "model": "claude", "body": "Strategy idea: BUY on momentum"})
    resp = await news_api.strategy_advisor(payload, current_user=user, db=fake_db)

    assert resp["ok"] is True
    assert "Strategy idea" in resp["body"]
    assert resp["body"] == "Strategy idea: BUY on momentum"
