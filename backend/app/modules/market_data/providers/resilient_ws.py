"""A reusable, resilient WebSocket client for provider feeds.

Broker providers (Zerodha, Upstox, …) stream over WebSocket. This class gives
them, for free: automatic reconnect with exponential backoff + jitter,
heartbeats, a subscription manager that survives reconnects and never
double-subscribes, backpressure protection via a bounded queue (with drop
accounting), and connection metrics.

It is transport-agnostic: a ``connect_factory`` returns any object satisfying
:class:`Transport`, so it is fully unit-testable with an in-memory fake — no
real network required.
"""

from __future__ import annotations

import asyncio
import contextlib
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.core.logging import get_logger

logger = get_logger("resilient_ws")


class Transport(Protocol):
    """Minimal duck-typed transport (a real or fake websocket)."""

    async def send(self, message: str) -> None: ...
    async def recv(self) -> str: ...
    async def close(self) -> None: ...


ConnectFactory = Callable[[], Awaitable[Transport]]
MessageHandler = Callable[[str], Awaitable[None]]


@dataclass
class BackoffPolicy:
    """Exponential backoff with jitter, capped."""

    base: float = 1.0
    factor: float = 2.0
    max_delay: float = 30.0
    jitter: float = 0.3

    def delay_for(self, attempt: int) -> float:
        raw = min(self.max_delay, self.base * (self.factor ** max(0, attempt - 1)))
        return raw + random.uniform(0, self.jitter * raw)


@dataclass
class WsMetrics:
    connects: int = 0
    reconnects: int = 0
    messages_received: int = 0
    messages_dropped: int = 0
    heartbeats_sent: int = 0
    subscribe_sends: int = 0
    connected: bool = False
    last_message_ts: float | None = None
    connected_since: float | None = None

    def snapshot(self) -> dict[str, float | int | bool | None]:
        return {**self.__dict__}


class ResilientWebSocketClient:
    """Manages one resilient provider WebSocket connection."""

    def __init__(
        self,
        connect_factory: ConnectFactory,
        *,
        on_message: MessageHandler,
        subscribe_encoder: Callable[[list[str]], str],
        unsubscribe_encoder: Callable[[list[str]], str],
        heartbeat_encoder: Callable[[], str] | None = None,
        heartbeat_interval: float = 15.0,
        max_queue: int = 10_000,
        backoff: BackoffPolicy | None = None,
    ) -> None:
        self._connect_factory = connect_factory
        self._on_message = on_message
        self._encode_sub = subscribe_encoder
        self._encode_unsub = unsubscribe_encoder
        self._encode_heartbeat = heartbeat_encoder
        self._heartbeat_interval = heartbeat_interval
        self._backoff = backoff or BackoffPolicy()

        self._subscriptions: set[str] = set()
        self._transport: Transport | None = None
        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_queue)
        self._running = False
        self._attempt = 0
        self.metrics = WsMetrics()

    # -- Subscription manager (dedup + survives reconnect) ------------------
    async def subscribe(self, symbols: list[str]) -> None:
        new = [s for s in symbols if s not in self._subscriptions]
        if not new:
            return
        self._subscriptions.update(new)
        if self._transport is not None:
            await self._send(self._encode_sub(new))

    async def unsubscribe(self, symbols: list[str]) -> None:
        existing = [s for s in symbols if s in self._subscriptions]
        if not existing:
            return
        self._subscriptions.difference_update(existing)
        if self._transport is not None:
            await self._send(self._encode_unsub(existing))

    @property
    def subscriptions(self) -> set[str]:
        return set(self._subscriptions)

    # -- Lifecycle ----------------------------------------------------------
    async def run(self) -> None:
        """Connect-and-serve loop with automatic reconnect. Runs until stopped."""
        self._running = True
        while self._running:
            try:
                await self._connect_and_serve()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._attempt += 1
                delay = self._backoff.delay_for(self._attempt)
                self.metrics.connected = False
                logger.warning(
                    "ws_disconnected",
                    error=str(exc),
                    attempt=self._attempt,
                    retry_in=round(delay, 2),
                )
                if not self._running:
                    break
                await asyncio.sleep(delay)

    async def stop(self) -> None:
        self._running = False
        if self._transport is not None:
            with contextlib.suppress(Exception):
                await self._transport.close()

    async def _connect_and_serve(self) -> None:
        self._transport = await self._connect_factory()
        self.metrics.connects += 1
        if self._attempt > 0:
            self.metrics.reconnects += 1
        self._attempt = 0
        self.metrics.connected = True
        self.metrics.connected_since = asyncio.get_event_loop().time()

        # Re-subscribe everything on (re)connect — never double-subscribing.
        if self._subscriptions:
            await self._send(self._encode_sub(sorted(self._subscriptions)))

        tasks = [
            asyncio.create_task(self._receive_loop()),
            asyncio.create_task(self._process_loop()),
        ]
        if self._encode_heartbeat is not None:
            tasks.append(asyncio.create_task(self._heartbeat_loop()))
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            with contextlib.suppress(Exception):
                if self._transport is not None:
                    await self._transport.close()
            self._transport = None

    async def _receive_loop(self) -> None:
        assert self._transport is not None
        while self._running:
            message = await self._transport.recv()
            self.metrics.messages_received += 1
            self.metrics.last_message_ts = asyncio.get_event_loop().time()
            try:
                self._queue.put_nowait(message)
            except asyncio.QueueFull:
                # Backpressure: drop oldest to stay current, count the loss.
                self.metrics.messages_dropped += 1
                with contextlib.suppress(asyncio.QueueEmpty):
                    self._queue.get_nowait()
                    self._queue.put_nowait(message)

    async def _process_loop(self) -> None:
        while self._running:
            message = await self._queue.get()
            try:
                await self._on_message(message)
            except Exception:
                logger.exception("ws_message_handler_error")
            finally:
                self._queue.task_done()

    async def _heartbeat_loop(self) -> None:
        assert self._encode_heartbeat is not None
        while self._running:
            await asyncio.sleep(self._heartbeat_interval)
            await self._send(self._encode_heartbeat())
            self.metrics.heartbeats_sent += 1

    async def _send(self, message: str) -> None:
        if self._transport is None:
            return
        await self._transport.send(message)
        self.metrics.subscribe_sends += 1
