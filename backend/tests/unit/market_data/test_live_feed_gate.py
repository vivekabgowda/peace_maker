"""The live broker feed is gated on market hours.

Outside market hours a live broker drops the socket and its SDK retries it,
so the feed holds the connection open only during the session and closes it out
of hours — avoiding a pointless reconnect churn. The simulated provider is never
gated (it streams continuously for dev).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.feed import service as feed_service
from app.feed.service import FeedService


class _FakeLiveProvider:
    name = "zerodha"

    def __init__(self) -> None:
        self._connected = False
        self.connects = 0
        self.disconnects = 0

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        self.connects += 1
        self._connected = True

    async def disconnect(self) -> None:
        self.disconnects += 1
        self._connected = False

    async def subscribe(self, symbols: list[str]) -> None:
        pass


async def test_gate_closes_out_of_hours_then_opens_in_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = _FakeLiveProvider()
    feed = FeedService(provider=provider, enforce_session=True)  # type: ignore[arg-type]
    now = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)  # a Saturday

    # Market closed → the socket is closed once and not reopened on later ticks.
    monkeypatch.setattr(feed_service, "is_market_open", lambda _now: False)
    await feed._gate_live_feed(now)
    await feed._gate_live_feed(now)
    assert provider.disconnects == 1
    assert provider.connects == 0
    assert provider.is_connected is False

    # Market opens → connect exactly once for the session.
    monkeypatch.setattr(feed_service, "is_market_open", lambda _now: True)
    await feed._gate_live_feed(now)
    await feed._gate_live_feed(now)
    assert provider.connects == 1
    assert provider.is_connected is True


async def test_gate_skips_simulated_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _FakeLiveProvider()
    provider.name = "simulated"  # type: ignore[misc]
    feed = FeedService(provider=provider, enforce_session=True)  # type: ignore[arg-type]
    monkeypatch.setattr(feed_service, "is_market_open", lambda _now: False)
    await feed._gate_live_feed(datetime(2026, 7, 25, 12, 0, tzinfo=UTC))
    assert provider.disconnects == 0 and provider.connects == 0
