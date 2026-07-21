"""Production asynchronous event bus.

Design goals (from the Technical Design Review, R0 #2):
- **Fire-and-forget publish** — the publisher never awaits subscriber work, so
  slow persistence can never backpressure ingestion.
- **Bounded per-subscriber queues + a dedicated worker each** — one slow or
  failing consumer is isolated; it fills only its own queue.
- **Backpressure protection** — on a full queue the event is dropped (newest
  kept) and routed to the **dead-letter queue** with a metric, rather than
  blocking.
- **Metrics** — published/delivered/dropped/errors + live queue depth.

Delivery is asynchronous; use :meth:`EventBus.join` (tests/graceful shutdown) to
wait until all queues drain.
"""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeVar

from prometheus_client import Counter, Gauge

from app.core.logging import get_logger
from app.shared.events.types import Event

logger = get_logger("event_bus")

E = TypeVar("E", bound=Event)
Handler = Callable[[Event], Awaitable[None]]

_PUBLISHED = Counter("bkn_events_published_total", "Events published", ["event"])
_DELIVERED = Counter("bkn_events_delivered_total", "Events delivered to a handler", ["subscriber"])
_DROPPED = Counter("bkn_events_dropped_total", "Events dropped (queue full)", ["subscriber"])
_ERRORS = Counter("bkn_event_handler_errors_total", "Handler exceptions", ["subscriber"])
_QUEUE_DEPTH = Gauge("bkn_event_queue_depth", "Per-subscriber queue depth", ["subscriber"])


@dataclass
class _Subscription:
    event_name: str
    handler: Handler
    name: str
    queue: asyncio.Queue[Event]
    worker: asyncio.Task[None] | None = None
    delivered: int = 0
    dropped: int = 0
    errors: int = 0


@dataclass
class DeadLetter:
    subscriber: str
    event: Event
    reason: str


@dataclass
class BusStats:
    published: int = 0
    subscribers: int = 0
    dead_letters: int = 0
    per_subscriber: dict[str, dict[str, int]] = field(default_factory=dict)


class EventBus:
    """A bounded, fire-and-forget async pub/sub bus with per-subscriber isolation."""

    def __init__(self, *, default_max_queue: int = 2000, dlq_size: int = 1000) -> None:
        self._subs: dict[str, list[_Subscription]] = {}
        self._all_subs: list[_Subscription] = []
        self._default_max_queue = default_max_queue
        self._dlq: deque[DeadLetter] = deque(maxlen=dlq_size)
        self._published = 0
        self._running = False

    def subscribe(
        self,
        event_type: type[E],
        handler: Callable[[E], Awaitable[None]],
        *,
        name: str | None = None,
        max_queue: int | None = None,
    ) -> None:
        """Register ``handler`` with its own bounded queue + worker."""
        sub = _Subscription(
            event_name=event_type.__name__,
            handler=handler,  # type: ignore[arg-type]
            name=name or str(getattr(handler, "__qualname__", repr(handler))),
            queue=asyncio.Queue(maxsize=max_queue or self._default_max_queue),
        )
        self._subs.setdefault(event_type.__name__, []).append(sub)
        self._all_subs.append(sub)
        if self._running:
            sub.worker = asyncio.create_task(self._worker(sub))

    async def start(self) -> None:
        """Spawn a worker task per subscriber."""
        self._running = True
        for sub in self._all_subs:
            if sub.worker is None:
                sub.worker = asyncio.create_task(self._worker(sub))

    async def stop(self) -> None:
        """Cancel all workers (does not drop already-queued events on join)."""
        self._running = False
        for sub in self._all_subs:
            if sub.worker is not None:
                sub.worker.cancel()
        self._all_subs and await asyncio.gather(
            *(s.worker for s in self._all_subs if s.worker), return_exceptions=True
        )

    def publish(self, event: Event) -> None:
        """Enqueue ``event`` to every matching subscriber. Never blocks/awaits."""
        self._published += 1
        _PUBLISHED.labels(type(event).__name__).inc()
        for sub in self._subs.get(type(event).__name__, ()):
            try:
                sub.queue.put_nowait(event)
                _QUEUE_DEPTH.labels(sub.name).set(sub.queue.qsize())
            except asyncio.QueueFull:
                sub.dropped += 1
                _DROPPED.labels(sub.name).inc()
                self._dlq.append(DeadLetter(sub.name, event, "queue_full"))

    async def join(self, timeout: float = 5.0) -> None:  # noqa: ASYNC109
        """Wait until all subscriber queues are drained (tests/graceful stop)."""

        async def _drain() -> None:
            for sub in self._all_subs:
                await sub.queue.join()

        try:
            await asyncio.wait_for(_drain(), timeout)
        except TimeoutError:
            logger.warning("event_bus_join_timeout")

    async def _worker(self, sub: _Subscription) -> None:
        while True:
            event = await sub.queue.get()
            try:
                await sub.handler(event)
                sub.delivered += 1
                _DELIVERED.labels(sub.name).inc()
            except asyncio.CancelledError:
                sub.queue.task_done()
                raise
            except Exception as exc:
                sub.errors += 1
                _ERRORS.labels(sub.name).inc()
                self._dlq.append(DeadLetter(sub.name, event, f"handler_error: {exc}"))
                logger.exception("event_handler_error", subscriber=sub.name)
            finally:
                sub.queue.task_done()
                _QUEUE_DEPTH.labels(sub.name).set(sub.queue.qsize())

    async def reset(self) -> None:
        """Stop workers and clear all subscriptions/state (test isolation)."""
        await self.stop()
        self._subs.clear()
        self._all_subs.clear()
        self._dlq.clear()
        self._published = 0

    @property
    def dead_letters(self) -> list[DeadLetter]:
        return list(self._dlq)

    @property
    def stats(self) -> BusStats:
        return BusStats(
            published=self._published,
            subscribers=len(self._all_subs),
            dead_letters=len(self._dlq),
            per_subscriber={
                s.name: {"delivered": s.delivered, "dropped": s.dropped, "errors": s.errors}
                for s in self._all_subs
            },
        )


# Process-wide default bus. Modules import this instance; the owning process
# (API or feed service) calls start()/stop() in its lifespan.
event_bus = EventBus()
