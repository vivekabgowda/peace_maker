"""Tests for the production async event bus (bounded, isolated, DLQ)."""

from __future__ import annotations

import asyncio
from decimal import Decimal

from app.shared.events import EventBus, QuoteUpdated


def _quote(sym: str) -> QuoteUpdated:
    return QuoteUpdated(instrument_id=1, symbol=sym, ltp=Decimal("1"))


async def test_publish_delivers_to_subscribers() -> None:
    bus = EventBus()
    received: list[str] = []

    async def handler(event: QuoteUpdated) -> None:
        received.append(event.symbol)

    bus.subscribe(QuoteUpdated, handler)
    await bus.start()
    bus.publish(_quote("NIFTY"))
    await bus.join()
    await bus.stop()
    assert received == ["NIFTY"]


async def test_publish_is_fire_and_forget_non_blocking() -> None:
    """A slow handler must not block the publisher."""
    bus = EventBus()
    gate = asyncio.Event()

    async def slow(_e: QuoteUpdated) -> None:
        await gate.wait()

    bus.subscribe(QuoteUpdated, slow)
    await bus.start()
    # publish() returns immediately even though the handler is blocked.
    bus.publish(_quote("X"))
    assert bus.stats.published == 1
    gate.set()
    await bus.join()
    await bus.stop()


async def test_slow_consumer_isolation_and_drop() -> None:
    """A full slow-consumer queue drops to the DLQ without affecting others."""
    bus = EventBus()
    gate = asyncio.Event()
    fast_hits: list[str] = []

    async def slow(_e: QuoteUpdated) -> None:
        await gate.wait()

    async def fast(e: QuoteUpdated) -> None:
        fast_hits.append(e.symbol)

    bus.subscribe(QuoteUpdated, slow, name="slow", max_queue=2)
    bus.subscribe(QuoteUpdated, fast, name="fast")
    await bus.start()
    for i in range(10):
        bus.publish(_quote(f"S{i}"))
    gate.set()
    await bus.join()
    await bus.stop()

    # Fast consumer received everything; slow consumer dropped the overflow.
    assert len(fast_hits) == 10
    assert bus.stats.per_subscriber["slow"]["dropped"] > 0
    assert any(dl.reason == "queue_full" for dl in bus.dead_letters)


async def test_handler_error_is_isolated_and_dead_lettered() -> None:
    bus = EventBus()
    good: list[str] = []

    async def bad(_e: QuoteUpdated) -> None:
        raise RuntimeError("boom")

    async def good_h(e: QuoteUpdated) -> None:
        good.append(e.symbol)

    bus.subscribe(QuoteUpdated, bad, name="bad")
    bus.subscribe(QuoteUpdated, good_h, name="good")
    await bus.start()
    bus.publish(_quote("TCS"))
    await bus.join()
    await bus.stop()
    assert good == ["TCS"]
    assert bus.stats.per_subscriber["bad"]["errors"] == 1
    assert any("handler_error" in dl.reason for dl in bus.dead_letters)
