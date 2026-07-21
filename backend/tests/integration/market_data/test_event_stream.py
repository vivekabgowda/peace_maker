"""Redis-Streams cross-instance event transport (R3)."""

from __future__ import annotations

from decimal import Decimal

import pytest
from app.shared.events import IndicatorCalculated, QuoteUpdated
from app.shared.events.stream import EventStreamBridge

pytestmark = pytest.mark.integration


async def test_event_round_trips_through_stream() -> None:
    """An event forwarded to the stream is consumed back intact on another instance."""
    producer = EventStreamBridge()
    await producer.forward(QuoteUpdated(instrument_id=7, symbol="NIFTY", ltp=Decimal("24500.5")))
    await producer.forward(
        IndicatorCalculated(
            instrument_id=7,
            symbol="NIFTY",
            timeframe="5m",
            bar_ts=QuoteUpdated(instrument_id=7, symbol="X", ltp=Decimal("1")).ts,
            indicators={"rsi_14": 61.2},
        )
    )

    received: list[object] = []
    consumer = EventStreamBridge()
    consumer._last_id = "0"  # read from the start of the stream
    n = await consumer.consume_once(received.append, block_ms=50)

    assert n == 2
    q = received[0]
    assert isinstance(q, QuoteUpdated)
    assert q.symbol == "NIFTY"
    assert q.ltp == Decimal("24500.5")  # Decimal preserved across serialization
    ind = received[1]
    assert isinstance(ind, IndicatorCalculated)
    assert ind.indicators["rsi_14"] == 61.2


async def test_consumer_tracks_position() -> None:
    """A second consume only returns new events (broadcast cursor advances)."""
    producer = EventStreamBridge()
    consumer = EventStreamBridge()
    consumer._last_id = "0"

    await producer.forward(QuoteUpdated(instrument_id=1, symbol="A", ltp=Decimal("1")))
    assert await consumer.consume_once(lambda _e: None, block_ms=50) == 1
    # Nothing new yet.
    assert await consumer.consume_once(lambda _e: None, block_ms=50) == 0
    # A new event is picked up from the tracked position.
    await producer.forward(QuoteUpdated(instrument_id=1, symbol="B", ltp=Decimal("2")))
    assert await consumer.consume_once(lambda _e: None, block_ms=50) == 1
