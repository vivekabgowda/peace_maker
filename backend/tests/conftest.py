"""Pytest fixtures.

The test suite runs against an isolated on-disk SQLite database (async) so
integration tests need no external services. Environment variables are set
*before* the application modules are imported so the cached settings pick up the
test configuration.
"""

from __future__ import annotations

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


@pytest.fixture(scope="session", autouse=True)
async def _prepare_database() -> AsyncIterator[None]:
    """Create the schema once for the whole test session, drop it afterwards."""
    if _TMP_DB.exists():
        _TMP_DB.unlink()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()
    if _TMP_DB.exists():
        _TMP_DB.unlink()


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
