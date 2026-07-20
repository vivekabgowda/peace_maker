"""Pytest fixtures.

The test suite runs against an isolated on-disk SQLite database (async) so
integration tests need no external services. Environment variables are set
*before* the application modules are imported so the cached settings pick up the
test configuration.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

# --- Configure the environment before importing anything that reads settings --
_TMP_DB = Path(tempfile.gettempdir()) / "bkn_test.db"
os.environ.setdefault("BKN_ENV", "test")
os.environ.setdefault("BKN_DATABASE_URL", f"sqlite+aiosqlite:///{_TMP_DB}")
os.environ.setdefault("BKN_JWT_SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("BKN_LOG_JSON", "false")
os.environ.setdefault("BKN_ACCESS_TOKEN_EXPIRE_MINUTES", "15")

import httpx  # noqa: E402
from app.core.database import Base, async_session_factory, engine  # noqa: E402
from app.main import create_app  # noqa: E402

_IS_SQLITE = os.environ["BKN_DATABASE_URL"].startswith("sqlite")
# The Postgres CI job sets BKN_TEST_FAKE_REDIS=0 to use the real redis service.
_USE_FAKE_REDIS = os.environ.get("BKN_TEST_FAKE_REDIS", "1") != "0"


@pytest.fixture(scope="session", autouse=True)
async def _prepare_database() -> AsyncIterator[None]:
    """Create the schema for the test session; drop it afterwards.

    Works on both SQLite (default) and Postgres/TimescaleDB (the CI job that
    points BKN_DATABASE_URL at a real server), so Postgres-specific paths
    (ON CONFLICT, GREATEST/LEAST, native types) are exercised in CI.
    """
    if _IS_SQLITE and _TMP_DB.exists():
        _TMP_DB.unlink()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    if _IS_SQLITE and _TMP_DB.exists():
        _TMP_DB.unlink()


@pytest.fixture(autouse=True)
async def _fake_redis() -> AsyncIterator[None]:
    """Back get_redis() with an in-memory fakeredis so Redis paths (cache,
    WS tickets, rate limiting) are exercised and isolated per test. When
    BKN_TEST_FAKE_REDIS=0, use the real Redis (flushed between tests)."""
    from app.core import redis as redis_module

    if not _USE_FAKE_REDIS:
        redis_module.get_redis()
        try:
            yield
        finally:
            with contextlib.suppress(Exception):
                await redis_module.get_redis().flushall()
        return

    import fakeredis.aioredis

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    previous = redis_module._client
    redis_module._client = fake
    try:
        yield
    finally:
        await fake.flushall()
        await fake.aclose()
        redis_module._client = previous


@pytest.fixture(autouse=True)
async def _clean_tables() -> AsyncIterator[None]:
    """Truncate all tables between tests for isolation."""
    yield
    async with async_session_factory() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(table.delete())
        await session.commit()


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """An HTTPX client wired to the ASGI app in-process (no network)."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
