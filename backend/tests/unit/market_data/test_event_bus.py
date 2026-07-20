"""Tests for the async event bus."""

from __future__ import annotations

from decimal import Decimal

from app.shared.events import EventBus, QuoteUpdated


async def test_publish_delivers_to_subscribers() -> None:
    bus = EventBus()
    received: list[str] = []

    async def handler(event: QuoteUpdated) -> None:
        received.append(event.symbol)

    bus.subscribe(QuoteUpdated, handler)
    await bus.publish(QuoteUpdated(instrument_id=1, symbol="NIFTY", ltp=Decimal("100")))
    assert received == ["NIFTY"]


async def test_handler_failure_is_isolated() -> None:
    bus = EventBus()
    good: list[str] = []

    async def bad(_event: QuoteUpdated) -> None:
        raise RuntimeError("boom")

    async def good_handler(event: QuoteUpdated) -> None:
        good.append(event.symbol)

    bus.subscribe(QuoteUpdated, bad)
    bus.subscribe(QuoteUpdated, good_handler)
    # Publish must not raise even though one handler fails.
    await bus.publish(QuoteUpdated(instrument_id=1, symbol="TCS", ltp=Decimal("1")))
    assert good == ["TCS"]
    assert bus.stats["handler_errors"] == 1


async def test_unsubscribe() -> None:
    bus = EventBus()
    hits: list[str] = []

    async def handler(event: QuoteUpdated) -> None:
        hits.append(event.symbol)

    bus.subscribe(QuoteUpdated, handler)
    bus.unsubscribe(QuoteUpdated, handler)
    await bus.publish(QuoteUpdated(instrument_id=1, symbol="X", ltp=Decimal("1")))
    assert hits == []
