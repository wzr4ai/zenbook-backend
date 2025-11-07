import pytest
from sqlalchemy.engine import make_url

from src.core.database import resolve_async_database_url


def test_postgres_url_coerces_to_asyncpg():
    resolved = resolve_async_database_url("postgresql://user:pass@localhost:5432/devdb")
    url = make_url(resolved)
    assert url.drivername == "postgresql+asyncpg"


def test_mysql_url_coerces_to_asyncmy_and_preserves_query():
    resolved = resolve_async_database_url("mysql://user:pass@localhost:3306/devdb?charset=utf8mb4")
    url = make_url(resolved)
    assert url.drivername == "mysql+asyncmy"
    assert url.query["charset"] == "utf8mb4"


def test_sqlite_async_url_passes_through():
    resolved = resolve_async_database_url("sqlite+aiosqlite:///./dev.db")
    assert resolved == "sqlite+aiosqlite:///./dev.db"


def test_unsupported_dialect_raises():
    with pytest.raises(ValueError):
        resolve_async_database_url("mssql+pyodbc://user:pass@localhost:1433/devdb")
