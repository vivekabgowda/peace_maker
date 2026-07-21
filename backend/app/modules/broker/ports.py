"""SDK-agnostic ports for Zerodha Kite Connect (Sprint 6).

The rest of the broker module depends only on these Protocols, never on the
``kiteconnect`` SDK directly. The real SDK is wrapped by adapters in
``app.modules.broker.kite`` and imported **lazily** (so the platform installs and
tests without it); fakes implement the same Protocols in the test suite.

This is the second seam (below ``MarketProvider``) that keeps a concrete broker —
and its network/order surface — out of the core.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

# A Kite tick and instrument row are loosely-typed dicts as the SDK returns them;
# the mappers normalize them into the platform's domain models.
KiteTick = dict[str, Any]
KiteInstrument = dict[str, Any]
KiteCandle = list[Any]  # [date, open, high, low, close, volume]
TickCallback = Callable[[list[KiteTick]], None]


@runtime_checkable
class KiteHttpPort(Protocol):
    """The REST subset of Kite Connect the platform uses (no order methods)."""

    def login_url(self) -> str:
        """The hosted Kite login URL the user is redirected to."""

    def generate_session(self, request_token: str, api_secret: str) -> dict[str, Any]:
        """Exchange a request_token for a session (contains ``access_token``)."""

    def set_access_token(self, access_token: str) -> None:
        """Attach an access token to subsequent authenticated calls."""

    def profile(self) -> dict[str, Any]:
        """Fetch the account profile — used as a lightweight auth/health probe."""

    def instruments(self, exchange: str | None = None) -> list[KiteInstrument]:
        """Full instrument master (optionally for one exchange)."""

    def historical_data(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str,
        continuous: bool = False,
    ) -> list[dict[str, Any]]:
        """OHLCV candles for one instrument token over a date range."""

    def quote(self, instruments: list[str]) -> dict[str, Any]:
        """Full market quote (incl. depth / OHLC) for ``exchange:tradingsymbol``."""


@runtime_checkable
class KiteTickerPort(Protocol):
    """The streaming subset of the Kite ticker (WebSocket)."""

    def connect(self, threaded: bool = True) -> None: ...
    def close(self) -> None: ...
    def subscribe(self, tokens: list[int]) -> None: ...
    def unsubscribe(self, tokens: list[int]) -> None: ...
    def set_mode(self, mode: str, tokens: list[int]) -> None: ...

    @property
    def is_connected(self) -> bool: ...

    #: Assignable callbacks (the SDK exposes these as attributes).
    on_ticks: TickCallback | None
    on_connect: Callable[..., None] | None
    on_close: Callable[..., None] | None
    on_error: Callable[..., None] | None
