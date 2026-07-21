"""Redis-Streams event transport for cross-instance fan-out (R3).

The in-process :class:`EventBus` is per-process. To scale the realtime path
horizontally (a dedicated feed process + N API workers, each with its own
WebSocket clients), domain events are mirrored onto a Redis Stream:

    feed process ──forward──▶ Redis Stream ──consume──▶ every API worker ──▶ WS

Consumption is **broadcast** (each API worker reads the whole stream from its own
last-seen id), so every worker delivers every event to its own clients — unlike a
consumer group, which would distribute events. Enabled by
``BKN_EVENT_STREAM_ENABLED``; when off, everything runs on the in-process bus.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.core.logging import get_logger
from app.core.redis import get_redis
from app.shared.events.types import (
    CandleClosed,
    Event,
    IndicatorCalculated,
    MarketStatusChanged,
    NewsReceived,
    OptionChainUpdated,
    QuoteUpdated,
)

logger = get_logger("event_stream")

STREAM_KEY = "bkn:events"
_MAXLEN = 100_000

# Only these cross instances (the WS-facing events). Internal events like
# CandleClosed stay local to the feed process that computes indicators.
_REGISTRY: dict[str, type[Event]] = {
    c.__name__: c
    for c in (
        QuoteUpdated,
        IndicatorCalculated,
        OptionChainUpdated,
        NewsReceived,
        MarketStatusChanged,
        CandleClosed,
    )
}

Dispatch = Callable[[Event], None]


class EventStreamBridge:
    """Forwards local events to Redis and consumes them back into a local bus."""

    def __init__(self) -> None:
        self._last_id = "$"  # start reading only new entries

    async def forward(self, event: Event) -> None:
        """Publish an event to the Redis Stream (registered on the feed's bus)."""
        try:
            await get_redis().xadd(
                STREAM_KEY,
                {"type": type(event).__name__, "data": event.model_dump_json()},
                maxlen=_MAXLEN,
                approximate=True,
            )
        except Exception:
            logger.warning("event_stream_forward_failed", event_type=type(event).__name__)

    async def consume_once(self, dispatch: Dispatch, *, block_ms: int = 1000) -> int:
        """Read a batch of new events and dispatch them. Returns #dispatched."""
        entries = await get_redis().xread({STREAM_KEY: self._last_id}, block=block_ms, count=500)
        count = 0
        for _stream, messages in entries or []:
            for message_id, fields in messages:
                self._last_id = message_id
                event = _deserialize(fields)
                if event is not None:
                    dispatch(event)
                    count += 1
        return count

    async def run_consumer(self, dispatch: Dispatch, *, is_running: Callable[[], bool]) -> None:
        """Loop consuming the stream until ``is_running()`` returns False."""
        while is_running():
            await self.consume_once(dispatch)


def _deserialize(fields: dict[str, str]) -> Event | None:
    cls = _REGISTRY.get(fields.get("type", ""))
    if cls is None:
        return None
    try:
        return cls.model_validate_json(fields["data"])
    except Exception:
        logger.warning("event_stream_deserialize_failed", type=fields.get("type"))
        return None


def register_forwarder(bus: object, bridge: EventStreamBridge) -> None:
    """Subscribe the bridge forwarder for cross-instance event types (feed side)."""
    forwardable: tuple[type[Event], ...] = (
        QuoteUpdated,
        IndicatorCalculated,
        OptionChainUpdated,
        NewsReceived,
        MarketStatusChanged,
    )
    for event_type in forwardable:
        name = f"stream_forward:{event_type.__name__}"
        bus.subscribe(event_type, _make_forward(bridge), name=name)  # type: ignore[attr-defined]


def _make_forward(bridge: EventStreamBridge) -> Callable[[Event], Awaitable[None]]:
    async def _forward(event: Event) -> None:
        await bridge.forward(event)

    return _forward
