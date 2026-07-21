"""Fake Kite ports for broker tests — no SDK, no network."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.modules.broker.ports import KiteTickerPort

_INSTRUMENTS: list[dict[str, Any]] = [
    {
        "tradingsymbol": "NIFTY 50",
        "instrument_token": 256265,
        "segment": "INDICES",
        "exchange": "NSE",
        "name": "NIFTY 50",
        "instrument_type": "EQ",
    },
    {
        "tradingsymbol": "TCS",
        "instrument_token": 2953217,
        "segment": "NSE",
        "exchange": "NSE",
        "name": "TCS",
        "instrument_type": "EQ",
        "lot_size": 1,
        "tick_size": 0.05,
    },
]


class FakeKiteHttp:
    """Implements KiteHttpPort deterministically."""

    def __init__(self) -> None:
        self.access_token: str | None = None
        self.profile_calls = 0

    def login_url(self) -> str:
        return "https://kite.zerodha.com/connect/login?api_key=FAKE&v=3"

    def generate_session(self, request_token: str, api_secret: str) -> dict[str, Any]:
        if request_token == "bad":
            return {}
        return {
            "access_token": "ACCESS-" + request_token,
            "public_token": "PUB",
            "user_id": "AB1234",
        }

    def set_access_token(self, access_token: str) -> None:
        self.access_token = access_token

    def profile(self) -> dict[str, Any]:
        self.profile_calls += 1
        return {"user_id": "AB1234"}

    def instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
        return list(_INSTRUMENTS)

    def historical_data(
        self,
        instrument_token: int,
        from_date: datetime,
        to_date: datetime,
        interval: str,
        continuous: bool = False,
    ) -> list[dict[str, Any]]:
        return [
            {
                "date": datetime(2025, 1, 2, tzinfo=UTC),
                "open": 100,
                "high": 102,
                "low": 99,
                "close": 101,
                "volume": 1000,
            }
        ]

    def quote(self, instruments: list[str]) -> dict[str, Any]:
        return {}


class FakeKiteTicker:
    """Implements KiteTickerPort; connect() invokes on_connect synchronously."""

    def __init__(self) -> None:
        self.on_ticks: Callable[[list[dict[str, Any]]], None] | None = None
        self.on_connect: Callable[..., None] | None = None
        self.on_close: Callable[..., None] | None = None
        self.on_error: Callable[..., None] | None = None
        self._connected = False
        self.subscribed: list[int] = []

    def connect(self, threaded: bool = True) -> None:
        self._connected = True
        if self.on_connect:
            self.on_connect(self)

    def close(self) -> None:
        self._connected = False

    def subscribe(self, tokens: list[int]) -> None:
        self.subscribed = tokens

    def unsubscribe(self, tokens: list[int]) -> None:
        self.subscribed = [t for t in self.subscribed if t not in tokens]

    def set_mode(self, mode: str, tokens: list[int]) -> None:
        pass

    @property
    def is_connected(self) -> bool:
        return self._connected

    def emit_ticks(self, ticks: list[dict[str, Any]]) -> None:
        if self.on_ticks:
            self.on_ticks(ticks)

    def emit_close(self) -> None:
        self._connected = False
        if self.on_close:
            self.on_close(self, 1006, "drop")


def ticker_builder_for(ticker: FakeKiteTicker) -> Callable[[str, str], KiteTickerPort]:
    def _build(api_key: str, access_token: str) -> KiteTickerPort:
        return ticker

    return _build
