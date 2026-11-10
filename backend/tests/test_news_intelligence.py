import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from app.api.v1 import news as news_api
from app.services import advisor


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def scalars(self):
        return SimpleNamespace(all=lambda: self._rows)


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


@pytest.mark.asyncio
async def test_get_latest_news_all_returns_market_articles_without_ticker_filter():
    row = (
        "Indian bank reports stronger quarterly results",
        "https://example.com/bank",
        "en",
        datetime(2026, 10, 8, 9, 30, tzinfo=timezone.utc),
        "Reuters",
        "BANKING",
        ["HDFCBANK"],
        0.6,
        "POS",
        0.6,
        {"keywords": ["banking"], "tags": ["earnings"]},
    )

    class FakeDB:
        statement = None

        async def execute(self, statement):
            self.statement = statement
            return FakeResult([row])

    db = FakeDB()
    user = SimpleNamespace(id=uuid.uuid4(), username="tester")
    result = await news_api.get_latest_news("ALL", 10, user, db)
    statement = str(db.statement.compile(dialect=postgresql.dialect()))

    assert result["ticker"] == "ALL"
    assert result["articles"][0]["ticker"] == "HDFCBANK"
    assert result["articles"][0]["sector"] == "BANKING"
    assert result["articles"][0]["impact_band"] in {"LOW", "MEDIUM", "HIGH"}
    assert "news_sentiment.ticker =" not in statement


@pytest.mark.asyncio
async def test_get_signal_all_windows_aggregates_market_snapshots():
    now = datetime.now(timezone.utc)
    signal_rows = [
        ("AAA", 0.4, 2, 0.2, now),
        ("BBB", -0.2, 1, -0.1, now),
    ]
    headline_row = (
        "Indian banks rally after policy update",
        "https://example.com/policy",
        "en",
        now,
        0.5,
        "POS",
    )

    class FakeDB:
        async def execute(self, statement):
            compiled = str(statement.compile(dialect=postgresql.dialect()))
            if "news_signals" in compiled:
                return FakeResult(signal_rows)
            if compiled.lstrip().startswith("SELECT news_sentiment.label"):
                return FakeResult(["POS", "NEG"])
            return FakeResult([headline_row])

    user = SimpleNamespace(id=uuid.uuid4(), username="tester")
    result = await news_api.get_signal_all_windows("ALL", user, FakeDB())

    assert result["ticker"] == "ALL"
    assert len(result["windows"]) == len(news_api.settings.NEWS_WINDOWS_MINUTES)
    assert result["windows"][0]["signal"]["score"] == pytest.approx(0.2)
    assert result["windows"][0]["signal"]["impact"] == pytest.approx(0.1)
    assert result["windows"][0]["signal"]["article_count"] == 3
    assert result["headlines"][0]["title"] == headline_row[0]
    assert result["last_24h_counts"] == {"POS": 1, "NEG": 1, "NEU": 0}


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
