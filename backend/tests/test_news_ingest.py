from types import SimpleNamespace

import pytest

from app.services import news_ingest


class FakeSession:
    def __init__(self):
        self.statements = []

    async def execute(self, statement):
        self.statements.append(statement)
        return SimpleNamespace(all=lambda: [])


@pytest.mark.asyncio
async def test_ingest_cycle_queries_old_scores_without_fetching_feeds(monkeypatch):
    db = FakeSession()
    monkeypatch.setattr(news_ingest, "build_queries", lambda ticker: [])

    result = await news_ingest.ingest_cycle(db, tickers=["TEST"])

    assert result == {
        "fetched": 0,
        "candidates": 0,
        "articles_inserted": 0,
        "sentiment_rows": 0,
        "legacy_rows_rescored": 0,
    }
    assert len(db.statements) == 1
