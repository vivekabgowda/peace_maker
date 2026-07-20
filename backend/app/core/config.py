"""Application configuration.

Typed, 12-factor settings loaded from environment variables (prefix ``BKN_``).
A single cached :class:`Settings` instance is exposed via :func:`get_settings`.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]


class Settings(BaseSettings):
    """Central application settings.

    All values are overridable via environment variables prefixed with ``BKN_``,
    e.g. ``BKN_ENV=production`` or ``BKN_JWT_SECRET_KEY=...``.
    """

    model_config = SettingsConfigDict(
        env_prefix="BKN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- Application ---------------------------------------------------------
    env: Environment = "local"
    debug: bool = False
    project_name: str = "BKN AI Capital"
    api_v1_prefix: str = "/api/v1"
    version: str = "0.1.0"

    # -- Server --------------------------------------------------------------
    host: str = "0.0.0.0"  # noqa: S104 - binding inside a container is intentional
    port: int = 8000

    # -- CORS ----------------------------------------------------------------
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # -- Database ------------------------------------------------------------
    # Async SQLAlchemy DSN. Postgres (asyncpg) in every real environment; the
    # test suite uses aiosqlite. Kept as a validated ``str`` so both schemes
    # are accepted (PostgresDsn would reject the sqlite test URL).
    database_url: str = "postgresql+asyncpg://bkn:bkn@localhost:5432/bkn"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_echo: bool = False

    # -- Redis ---------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # -- Security / JWT ------------------------------------------------------
    jwt_secret_key: str = Field(
        default="change-me-in-production-this-is-not-a-secret",
        min_length=16,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # -- Logging -------------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = True

    # -- Market data (Sprint 2) ---------------------------------------------
    # Active market-data provider (resolved via the provider registry). The
    # rest of the app never depends on a concrete broker.
    market_provider: str = "simulated"
    # Start the live market feed runner on application startup.
    market_feed_enabled: bool = False
    # Simulated provider tick cadence (seconds).
    market_tick_interval: float = 1.0
    # Timeframes the candle builder maintains.
    market_timeframes: list[str] = Field(default_factory=lambda: ["1m", "5m", "15m", "1h", "1d"])
    # Underlyings whose option chains are polled.
    option_chain_underlyings: list[str] = Field(default_factory=lambda: ["NIFTY", "BANKNIFTY"])
    option_chain_poll_seconds: float = 5.0
    # Risk-free rate used for option greeks.
    risk_free_rate: float = 0.065

    @field_validator(
        "cors_origins",
        "market_timeframes",
        "option_chain_underlyings",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Allow comma-separated strings for list-typed settings."""
        if isinstance(value, str) and not value.startswith("["):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_db_scheme(cls, value: str) -> str:
        allowed = ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        if not value.startswith(allowed):
            raise ValueError(f"database_url must use one of {allowed}")
        return value

    @property
    def is_production(self) -> bool:
        return self.env == "production"

    @property
    def sync_database_url(self) -> str:
        """Synchronous DSN (used by Alembic's default engine helpers)."""
        return str(self.database_url).replace("+asyncpg", "+psycopg")


@lru_cache
def get_settings() -> Settings:
    """Return a process-wide cached :class:`Settings` instance."""
    return Settings()
