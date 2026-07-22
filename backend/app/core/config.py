"""Application configuration.

Typed, 12-factor settings loaded from environment variables (prefix ``BKN_``).
A single cached :class:`Settings` instance is exposed via :func:`get_settings`.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# List-typed settings accept a comma-separated string (e.g. docker-compose sets
# ``BKN_CORS_ORIGINS=http://localhost:3000``) OR a JSON array. ``NoDecode`` stops
# pydantic-settings from JSON-decoding the env value before our ``_split_csv``
# validator runs — otherwise a plain CSV string raises a SettingsError.
CsvList = Annotated[list[str], NoDecode]

Environment = Literal["local", "test", "staging", "production"]

# The development-only JWT secret; forbidden in staging/production.
_DEFAULT_JWT_SECRET = "change-me-in-production-this-is-not-a-secret"  # noqa: S105


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
    cors_origins: CsvList = Field(default_factory=lambda: ["http://localhost:3000"])

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
    jwt_secret_key: str = Field(default=_DEFAULT_JWT_SECRET, min_length=16)
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
    market_timeframes: CsvList = Field(default_factory=lambda: ["1m", "5m", "15m", "1h", "1d"])
    # Underlyings whose option chains are polled.
    option_chain_underlyings: CsvList = Field(default_factory=lambda: ["NIFTY", "BANKNIFTY"])
    option_chain_poll_seconds: float = 5.0
    # Risk-free rate used for option greeks.
    risk_free_rate: float = 0.065
    # News ingestion (polled by the feed service).
    news_provider: str = "simulated"
    news_poll_seconds: float = 30.0
    # TTL for the live quote hot-cache (stale data must not linger if feed stops).
    quote_cache_ttl_seconds: int = 30
    # Redis-Streams event transport for cross-instance fan-out (R3). Enable when
    # running the feed + >1 API worker; off = single-process in-memory bus only.
    event_stream_enabled: bool = False

    # ---- Alpha Engine (Sprint 3) ----
    # Benchmark index for regime detection and relative strength.
    alpha_benchmark: str = "NIFTY"
    # Strategy allow-list; empty = every registered strategy is enabled.
    alpha_enabled_strategies: CsvList = Field(default_factory=list)

    # ---- Broker / Zerodha Kite Connect (Sprint 6) ----
    # market_provider selects the broker: "simulated" / "paper" (built-in paper
    # broker) or "zerodha" (live Kite market data — NO order placement).
    zerodha_api_key: str = ""
    zerodha_api_secret: str = ""
    zerodha_redirect_url: str = "http://localhost:8000/api/v1/broker/zerodha/callback"
    # Fernet key for encrypting broker tokens at rest (generate with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
    broker_enc_key: str = ""
    # Subscribe to F&O instruments in addition to equity/index.
    broker_subscribe_fno: bool = False
    # Extra symbols to subscribe beyond Nifty 500 (configurable watchlist).
    broker_watchlist: CsvList = Field(default_factory=list)

    # ---- Paper trading & analytics (Sprint 7) ----
    # Starting capital for a paper account (INR). Returns/drawdown are computed
    # against this.
    paper_starting_cash: float = 1_000_000.0
    # Blended per-side cost (bps of notional) applied to paper fills.
    paper_fee_bps: float = 3.0
    # Cost model applied to paper fills: "flat" (paper_fee_bps) or "realistic"
    # (segment-specific Indian statutory charges — brokerage/STT/exchange/GST/
    # SEBI/stamp). Default "flat" preserves existing behaviour; "realistic" is
    # the honest cost stack used for validation (Sprint 14).
    paper_cost_model: str = "flat"
    # Default segment used by the realistic cost model when a trade doesn't
    # specify one: equity_delivery / equity_intraday / futures / options.
    paper_default_segment: str = "equity_intraday"
    # Market-order slippage (bps) modelled against the taker on paper fills.
    paper_slippage_bps: float = 1.0
    # Run the tick-driven paper position manager inside the feed process.
    paper_trading_enabled: bool = True
    # Generate daily/weekly performance reports automatically in the feed.
    report_scheduler_enabled: bool = True
    # How often the report scheduler checks whether a report is due (seconds).
    report_scheduler_interval_seconds: float = 900.0

    @field_validator(
        "cors_origins",
        "market_timeframes",
        "option_chain_underlyings",
        "alpha_enabled_strategies",
        "broker_watchlist",
        mode="before",
    )
    @classmethod
    def _split_csv(cls, value: object) -> object:
        """Accept a comma-separated string OR a JSON array for list settings.

        These fields use ``NoDecode`` so pydantic-settings does not JSON-decode the
        raw env value before this runs — so we handle both forms here: a JSON array
        (``["a","b"]``) is parsed as JSON; anything else is split on commas.
        """
        if isinstance(value, str):
            text = value.strip()
            if text.startswith("["):
                return json.loads(text)
            return [item.strip() for item in text.split(",") if item.strip()]
        return value

    @field_validator("database_url")
    @classmethod
    def _validate_db_scheme(cls, value: str) -> str:
        allowed = ("postgresql+asyncpg://", "sqlite+aiosqlite://")
        if not value.startswith(allowed):
            raise ValueError(f"database_url must use one of {allowed}")
        return value

    @model_validator(mode="after")
    def _guard_prod_secrets(self) -> Settings:
        """Fail fast if a real environment ships the dev JWT default (R1/security)."""
        if self.env in ("staging", "production") and self.jwt_secret_key == _DEFAULT_JWT_SECRET:
            raise ValueError(
                "BKN_JWT_SECRET_KEY must be set to a strong secret in staging/production "
                "(the development default is not allowed). Generate one with: openssl rand -hex 32"
            )
        return self

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
