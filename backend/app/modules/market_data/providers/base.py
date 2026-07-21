"""The ``MarketProvider`` port — the single seam between the platform and any
market-data source.

Concrete providers (Zerodha Kite, Upstox, Angel One, Fyers, NSE Direct,
TradingView alerts, or the built-in simulator) implement this interface. No
other module may import a concrete provider or a broker SDK — they depend on
this abstraction only, resolved through the provider registry.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import datetime

from app.modules.market_data.domain.models import (
    Candle,
    InstrumentDTO,
    OptionChainSnapshot,
    Quote,
)


class ProviderError(Exception):
    """Raised for provider-level failures (auth, connection, rate limit)."""


class MarketProvider(ABC):
    """Abstract market-data provider.

    Lifecycle: ``connect`` → ``subscribe`` → consume ``stream`` → ``disconnect``.
    Implementations must be safe to reconnect and must never leak broker-specific
    types across this boundary.
    """

    #: Stable provider identifier (e.g. "simulated", "zerodha").
    name: str = "abstract"

    @abstractmethod
    async def connect(self) -> None:
        """Establish the session/connection (auth, websocket handshake)."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Tear down the connection cleanly."""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Whether the provider currently has a live connection."""

    @abstractmethod
    async def fetch_instruments(self) -> list[InstrumentDTO]:
        """Return the full instrument master the provider exposes."""

    @abstractmethod
    async def subscribe(self, symbols: list[str]) -> None:
        """Subscribe to live updates for ``symbols`` (idempotent)."""

    @abstractmethod
    async def unsubscribe(self, symbols: list[str]) -> None:
        """Unsubscribe from ``symbols`` (idempotent)."""

    @abstractmethod
    def stream(self) -> AsyncIterator[Quote]:
        """Yield normalized :class:`Quote` objects for subscribed symbols."""

    @abstractmethod
    async def fetch_option_chain(self, underlying: str, expiry: str) -> OptionChainSnapshot:
        """Return the current option chain for an underlying/expiry."""

    @abstractmethod
    async def fetch_historical_candles(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Candle]:
        """Return historical OHLCV candles (used for backfill/gap recovery)."""

    async def health_check(self) -> bool:
        """Lightweight liveness probe. Default: connection state."""
        return self.is_connected
