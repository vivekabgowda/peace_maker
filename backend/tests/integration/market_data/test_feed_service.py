"""Integration + recovery tests for the supervised Feed Service."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest
from app.core.database import async_session_factory
from app.feed.service import FeedService
from app.modules.market_data.domain.models import Quote
from app.modules.market_data.providers.simulated import SimulatedMarketProvider
from app.modules.market_data.repository import MarketDataRepository
from app.shared.events import QuoteUpdated, event_bus

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
async def _reset_bus() -> AsyncIterator[None]:
    await event_bus.reset()
    yield
    await event_bus.reset()


async def test_feed_ingests_and_publishes_and_syncs_instruments() -> None:
    received: list[str] = []

    async def collect(event: QuoteUpdated) -> None:
        received.append(event.symbol)

    event_bus.subscribe(QuoteUpdated, collect, name="test_collector")
    await event_bus.start()

    feed = FeedService(
        provider=SimulatedMarketProvider(seed=1, tick_interval=0.0), enforce_session=False
    )
    await feed.start()
    try:
        for _ in range(200):
            if len(received) >= 5:
                break
            await asyncio.sleep(0.01)
    finally:
        await feed.stop()

    assert len(received) >= 5
    async with async_session_factory() as session:
        ids = await MarketDataRepository(session).symbol_id_map()
    assert "NIFTY" in ids  # instrument master synced


class _CrashingProvider(SimulatedMarketProvider):
    """Streams a few quotes, then raises once to simulate a dropped feed."""

    def __init__(self) -> None:
        super().__init__(seed=2, tick_interval=0.0)
        self._emitted = 0
        self.connects = 0

    async def connect(self) -> None:
        self.connects += 1
        await super().connect()

    async def stream(self) -> AsyncIterator[Quote]:
        async for quote in super().stream():
            self._emitted += 1
            if self._emitted == 4 and self.connects == 1:
                self._connected = False  # a real drop is no longer connected
                raise ConnectionError("simulated feed drop")
            yield quote


async def test_feed_recovers_from_stream_crash() -> None:
    provider = _CrashingProvider()
    feed = FeedService(provider=provider, enforce_session=False)
    await event_bus.start()
    await feed.start()
    reconnected_and_live = False
    try:
        # Wait for the crash + supervised restart (reconnect).
        for _ in range(500):
            if provider.connects >= 2:
                break
            await asyncio.sleep(0.01)
        # Capture liveness while running (stop() would disconnect the provider).
        reconnected_and_live = provider.connects >= 2 and provider.is_connected
    finally:
        await feed.stop()

    assert provider.connects >= 2  # supervisor restarted the stream → reconnected
    assert reconnected_and_live  # feed resumed on a live connection
