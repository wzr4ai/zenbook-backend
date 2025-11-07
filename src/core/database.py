"""Database engine and session helpers."""

from collections.abc import AsyncIterator

from sqlalchemy.engine import make_url
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings

SUPPORTED_ASYNC_DIALECTS = {"postgresql+asyncpg", "mysql+asyncmy", "sqlite+aiosqlite"}
DRIVER_COERCIONS = {
    "postgres": "postgresql+asyncpg",
    "postgresql": "postgresql+asyncpg",
    "mysql": "mysql+asyncmy",
    "sqlite": "sqlite+aiosqlite",
}


def resolve_async_database_url(raw_url: str) -> str:
    """Ensure the configured DATABASE_URL uses an async-capable driver."""
    url = make_url(raw_url)
    drivername = url.drivername.lower()
    if drivername in SUPPORTED_ASYNC_DIALECTS:
        return raw_url

    base_driver = drivername.split("+", 1)[0]
    target_driver = DRIVER_COERCIONS.get(base_driver)
    if not target_driver:
        raise ValueError(
            f"Unsupported database dialect '{url.drivername}'. "
            "ZenBook currently supports PostgreSQL (asyncpg), "
            "MySQL (asyncmy), or SQLite with aiosqlite for testing."
        )

    coerced_url: URL = url.set(drivername=target_driver)
    return coerced_url.render_as_string(hide_password=False)


class Base(DeclarativeBase):
    """Base declarative class with common metadata."""


DATABASE_URL = resolve_async_database_url(settings.database_url)

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.debug,
    future=True,
)
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an async session."""
    async with AsyncSessionLocal() as session:
        yield session
