"""Unit tests for configuration parsing."""

from __future__ import annotations

from app.core.config import Settings


def test_cors_origins_accepts_csv_string() -> None:
    settings = Settings(cors_origins="http://a.com, http://b.com")  # type: ignore[arg-type]
    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_is_production_flag() -> None:
    assert Settings(env="production").is_production is True
    assert Settings(env="local").is_production is False


def test_sync_database_url_strips_async_driver() -> None:
    settings = Settings(
        database_url="postgresql+asyncpg://u:p@host:5432/db"  # type: ignore[arg-type]
    )
    assert "+asyncpg" not in settings.sync_database_url
