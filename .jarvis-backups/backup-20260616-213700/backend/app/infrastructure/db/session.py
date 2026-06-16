"""Async SQLAlchemy engine + session factory (lazily initialised)."""
from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def _maker() -> async_sessionmaker[AsyncSession]:
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def get_session() -> AsyncIterator[AsyncSession]:
    async with _maker()() as session:
        yield session


async def init_models() -> None:
    """Create tables on boot (dev convenience; production uses Alembic)."""
    from app.infrastructure.db.base import Base
    from app.infrastructure.db import models  # noqa: F401 - ensure models imported
    async with get_engine().begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
