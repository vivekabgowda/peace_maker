"""Tests for the task supervisor (restart, backoff, circuit breaker, watchdog)."""

from __future__ import annotations

import asyncio

from app.shared.supervision import Backoff, CircuitBreaker, Supervisor
from app.shared.supervision.supervisor import SupervisedTask, TaskState


def test_backoff_monotonic_capped() -> None:
    b = Backoff(base=1, factor=2, max_delay=8, jitter=0)
    assert [b.delay(a) for a in range(1, 6)] == [1, 2, 4, 8, 8]


def test_circuit_breaker_opens_after_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=3, window=100)
    assert not cb.is_open
    for _ in range(3):
        cb.record_failure()
    assert cb.is_open


async def test_restart_on_crash() -> None:
    calls = {"n": 0}

    async def flaky() -> None:
        calls["n"] += 1
        raise RuntimeError("crash")

    task = SupervisedTask("flaky", flaky, backoff=Backoff(base=0.001, max_delay=0.01, jitter=0))
    task.start()
    for _ in range(200):
        if calls["n"] >= 3:
            break
        await asyncio.sleep(0.005)
    await task.stop()
    assert calls["n"] >= 3  # it kept restarting
    assert task.restarts >= 2


async def test_circuit_open_marks_unhealthy() -> None:
    async def always_fail() -> None:
        raise RuntimeError("nope")

    task = SupervisedTask(
        "bad",
        always_fail,
        backoff=Backoff(base=0.001, max_delay=0.01, jitter=0),
        breaker=CircuitBreaker(failure_threshold=3, window=100),
    )
    task.start()
    for _ in range(300):
        if task.state == TaskState.CIRCUIT_OPEN:
            break
        await asyncio.sleep(0.005)
    assert task.state == TaskState.CIRCUIT_OPEN
    assert not task.healthy
    await task.stop()


async def test_supervisor_health_and_watchdog() -> None:
    async def loop_ok() -> None:
        while True:  # noqa: ASYNC110 - a long-running task body under test
            await asyncio.sleep(0.01)

    sup = Supervisor()
    t = sup.add("ok", loop_ok, heartbeat_timeout=0.05)
    sup.start_all()
    await asyncio.sleep(0.02)
    t.heartbeat()
    assert sup.health()["healthy"] is True
    assert sup.watchdog() == []
    # Let the heartbeat go stale → watchdog flags it.
    await asyncio.sleep(0.1)
    assert "ok" in sup.watchdog()
    await sup.stop_all()
