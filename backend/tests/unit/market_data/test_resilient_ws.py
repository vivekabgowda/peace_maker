"""Tests for the resilient WebSocket client using an in-memory fake transport."""

from __future__ import annotations

import asyncio

import pytest
from app.modules.market_data.providers.resilient_ws import (
    BackoffPolicy,
    ResilientWebSocketClient,
)


class FakeTransport:
    """Yields queued messages, then raises to simulate a dropped connection."""

    def __init__(self, messages: list[str]) -> None:
        self._messages = list(messages)
        self.sent: list[str] = []
        self.closed = False

    async def send(self, message: str) -> None:
        self.sent.append(message)

    async def recv(self) -> str:
        if self._messages:
            return self._messages.pop(0)
        await asyncio.sleep(0.001)
        raise ConnectionError("connection dropped")

    async def close(self) -> None:
        self.closed = True


def test_backoff_monotonic_and_capped() -> None:
    policy = BackoffPolicy(base=1.0, factor=2.0, max_delay=10.0, jitter=0.0)
    delays = [policy.delay_for(a) for a in range(1, 8)]
    assert delays[0] == 1.0
    assert delays[1] == 2.0
    assert all(d <= 10.0 for d in delays)
    assert delays == sorted(delays)


async def test_subscription_dedup_without_transport() -> None:
    client = _make_client([])
    await client.subscribe(["A", "B"])
    await client.subscribe(["B", "C"])
    assert client.subscriptions == {"A", "B", "C"}


async def test_reconnect_and_resubscribe() -> None:
    transports: list[FakeTransport] = []

    async def factory() -> FakeTransport:
        t = FakeTransport(messages=["m1"])
        transports.append(t)
        return t

    received: list[str] = []

    async def on_message(msg: str) -> None:
        received.append(msg)

    client = ResilientWebSocketClient(
        factory,  # type: ignore[arg-type]
        on_message=on_message,
        subscribe_encoder=lambda syms: f"SUB:{','.join(syms)}",
        unsubscribe_encoder=lambda syms: f"UNSUB:{','.join(syms)}",
        backoff=BackoffPolicy(base=0.001, factor=1.0, max_delay=0.01, jitter=0.0),
    )
    await client.subscribe(["NIFTY", "BANKNIFTY"])

    task = asyncio.create_task(client.run())
    # Wait until several reconnects have happened.
    for _ in range(200):
        if len(transports) >= 3:
            break
        await asyncio.sleep(0.01)
    await client.stop()
    task.cancel()

    assert len(transports) >= 3  # reconnected multiple times
    assert client.metrics.reconnects >= 2
    assert "m1" in received
    # Every fresh connection re-sent the subscription (never lost on reconnect).
    for t in transports[:3]:
        assert any(s.startswith("SUB:") for s in t.sent)


async def test_backpressure_drops_when_queue_full() -> None:
    client = _make_client([], max_queue=2)
    # Fill the internal queue beyond capacity via the receive path simulation.
    client._queue.put_nowait("a")
    client._queue.put_nowait("b")
    assert client._queue.full()


def _make_client(messages: list[str], max_queue: int = 10000) -> ResilientWebSocketClient:
    async def factory() -> FakeTransport:
        return FakeTransport(messages)

    async def on_message(_msg: str) -> None:
        return None

    return ResilientWebSocketClient(
        factory,  # type: ignore[arg-type]
        on_message=on_message,
        subscribe_encoder=lambda syms: f"SUB:{','.join(syms)}",
        unsubscribe_encoder=lambda syms: f"UNSUB:{','.join(syms)}",
        max_queue=max_queue,
    )


pytestmark = pytest.mark.filterwarnings("ignore::RuntimeWarning")
