from sqlalchemy.orm import configure_mappers

from app.database import Base
import app.models


EXPECTED_TABLES = {
    "backtest_results",
    "badges",
    "league_entries",
    "leagues",
    "news_articles",
    "news_sentiment",
    "news_signal_outcomes",
    "news_signals",
    "ohlcv_bars",
    "orders",
    "positions",
    "strategies",
    "trade_journal",
    "users",
}


def test_all_orm_models_are_registered_and_relationships_resolve():
    configure_mappers()

    assert set(Base.metadata.tables) == EXPECTED_TABLES
    assert len(Base.registry.mappers) >= len(EXPECTED_TABLES)

    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table in Base.metadata.tables.values()

    for mapper in Base.registry.mappers:
        for relationship in mapper.relationships:
            if relationship.back_populates:
                assert relationship.back_populates in relationship.mapper.relationships
