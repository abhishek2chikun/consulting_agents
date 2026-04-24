"""Async SQLAlchemy engine, session factory, and FastAPI dependency.

Defines the SQLAlchemy 2.x declarative `Base` used by all ORM models in
later milestones. Migrations (Alembic) reference `Base.metadata`; the
runtime app uses `AsyncSessionLocal` / `get_session()` for request-scoped
sessions.
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async session.

    Rolls back on exception, always closes the session afterwards.
    """
    session = AsyncSessionLocal()
    try:
        yield session
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


__all__ = ["AsyncSessionLocal", "Base", "engine", "get_session"]
