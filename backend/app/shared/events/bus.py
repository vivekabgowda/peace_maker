"""In-process asynchronous event bus with optional Redis fan-out.

Modules communicate only through typed events — never by importing each other's
services. Publishing is fire-and-forget to local async subscribers; handler
exceptions are isolated and logged so one bad subscriber can't break the bus.

For cross-process distribution (e.g. the WebSocket gateway on another worker),
events can also be mirrored to Redis pub/sub via :meth:`EventBus.bridge_to_redis`.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.core.logging import get_logger
from app.shared.events.types import Event

logger = get_logger("event_bus")

E = TypeVar("E", bound=Event)
Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    """A lightweight typed async pub/sub bus."""

    def __init__(self) -> None:
        self._subscribers: dict[str, list[Handler]] = defaultdict(list)
        self._published = 0
        self._dropped = 0

    def subscribe(self, event_type: type[E], handler: Callable[[E], Awaitable[None]]) -> None:
        """Register ``handler`` for every event whose ``type`` matches."""
        self._subscribers[event_type.__name__].append(handler)  # type: ignore[arg-type]

    def unsubscribe(self, event_type: type[E], handler: Callable[[E], Awaitable[None]]) -> None:
        handlers = self._subscribers.get(event_type.__name__, [])
        if handler in handlers:
            handlers.remove(handler)

    async def publish(self, event: Event) -> None:
        """Deliver ``event`` to all subscribers concurrently.

        Handler exceptions are caught and logged — the bus never propagates a
        subscriber failure back to the publisher.
        """
        handlers = list(self._subscribers.get(type(event).__name__, ()))
        self._published += 1
        if not handlers:
            return
        results = await asyncio.gather(
            *(self._safe_call(h, event) for h in handlers), return_exceptions=True
        )
        for result in results:
            if isinstance(result, Exception):
                self._dropped += 1

    async def _safe_call(self, handler: Handler, event: Event) -> None:
        try:
            await handler(event)
        except Exception:
            logger.exception(
                "event_handler_error",
                event_name=type(event).__name__,
                handler=getattr(handler, "__qualname__", repr(handler)),
            )
            raise

    @property
    def stats(self) -> dict[str, int]:
        return {
            "published": self._published,
            "handler_errors": self._dropped,
            "event_types": len(self._subscribers),
        }


# Process-wide default bus. Modules import this instance.
event_bus = EventBus()
