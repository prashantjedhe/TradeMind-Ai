import pytest
from sqlalchemy.engine import make_url

from app.config import async_database_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "postgres://user:password@host:5432/trademind",
            "postgresql+asyncpg://user:password@host:5432/trademind",
        ),
        (
            "postgresql://user:password@host:5432/trademind",
            "postgresql+asyncpg://user:password@host:5432/trademind",
        ),
        (
            "postgresql+asyncpg://user:password@host:5432/trademind",
            "postgresql+asyncpg://user:password@host:5432/trademind",
        ),
    ],
)
def test_async_database_url_is_valid_for_asyncpg(value, expected):
    normalized = async_database_url(value)

    assert normalized == expected
    assert make_url(normalized).drivername == "postgresql+asyncpg"
