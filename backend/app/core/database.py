"""Async database engine, session factory, and the declarative ``Base``.

SQLAlchemy 2.x async engine with connection pooling configured from settings.
Sessions are provided per-request through the FastAPI dependency in
``app.core.dependencies``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

# Consistent, explicit constraint naming — required for reliable Alembic
# autogenerate/downgrade of indexes and constraints.
_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    metadata = MetaData(naming_convention=_NAMING_CONVENTION)


class TimestampMixin:
    """Adds ``created_at`` / ``updated_at`` columns managed by the database."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


def _create_engine() -> AsyncEngine:
    settings = get_settings()
    url = str(settings.database_url)
    # SQLite (used by the test suite) does not accept pool sizing kwargs.
    if url.startswith("sqlite"):
        return create_async_engine(url, echo=settings.db_echo, future=True)
    # Under test, pytest-asyncio runs each test on its own event loop. A pooled
    # asyncpg connection created on one loop cannot be reused (or pre-ping'd) on
    # the next — it raises "Event loop is closed". NullPool opens and closes a
    # fresh connection per checkout on the current loop, avoiding cross-loop reuse.
    if settings.env == "test":
        return create_async_engine(url, echo=settings.db_echo, future=True, poolclass=NullPool)
    return create_async_engine(
        url,
        echo=settings.db_echo,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,
    )


engine: AsyncEngine = _create_engine()

async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a transactional session; commit on success, rollback on error."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """Dispose the engine's connection pool (called on shutdown)."""
    await engine.dispose()
