"""Task supervision for long-running loops (feed, pollers, bus workers).

Every long-running coroutine is wrapped so that a crash never silently stops the
system (Technical Design Review R0 #3):

- **Restart on crash** with **exponential backoff + jitter**.
- **Circuit breaker** — after too many failures in a window, stop hammering and
  mark the task unhealthy (so the watchdog/health endpoint can surface it).
- **Heartbeat + watchdog** — tasks emit heartbeats; the supervisor flags a task
  whose heartbeat is stale (hung, not crashed).
- **Health metrics** — per-task up/down, restart count, heartbeat age.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from prometheus_client import Counter, Gauge

from app.core.logging import get_logger

logger = get_logger("supervisor")

_STATE = Gauge("bkn_task_up", "Supervised task up(1)/down(0)", ["task"])
_RESTARTS = Counter("bkn_task_restarts_total", "Supervised task restarts", ["task"])
_HEARTBEAT_AGE = Gauge("bkn_task_heartbeat_age_seconds", "Age of last heartbeat", ["task"])

TaskFactory = Callable[[], Awaitable[None]]


class TaskState(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    BACKOFF = "backoff"
    CIRCUIT_OPEN = "circuit_open"
    STOPPED = "stopped"


@dataclass
class Backoff:
    base: float = 0.5
    factor: float = 2.0
    max_delay: float = 30.0
    jitter: float = 0.3

    def delay(self, attempt: int) -> float:
        raw = min(self.max_delay, self.base * (self.factor ** max(0, attempt - 1)))
        return raw + random.uniform(0, self.jitter * raw)


@dataclass
class CircuitBreaker:
    """Opens after ``failure_threshold`` failures within ``window`` seconds."""

    failure_threshold: int = 5
    window: float = 60.0
    _failures: list[float] = field(default_factory=list)
    open_until: float = 0.0

    def record_failure(self) -> None:
        now = time.monotonic()
        self._failures.append(now)
        self._failures = [t for t in self._failures if now - t <= self.window]
        if len(self._failures) >= self.failure_threshold:
            self.open_until = now + self.window
            self._failures.clear()

    def record_success(self) -> None:
        self._failures.clear()

    @property
    def is_open(self) -> bool:
        return time.monotonic() < self.open_until


class SupervisedTask:
    """Runs ``factory`` forever, restarting on failure under a circuit breaker."""

    def __init__(
        self,
        name: str,
        factory: TaskFactory,
        *,
        backoff: Backoff | None = None,
        breaker: CircuitBreaker | None = None,
        heartbeat_timeout: float = 30.0,
    ) -> None:
        self.name = name
        self._factory = factory
        self._backoff = backoff or Backoff()
        self._breaker = breaker or CircuitBreaker()
        self._heartbeat_timeout = heartbeat_timeout
        self.state = TaskState.STOPPED
        self.restarts = 0
        self.last_heartbeat = time.monotonic()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._supervise(), name=f"sup:{self.name}")

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.state = TaskState.STOPPED
        _STATE.labels(self.name).set(0)

    def heartbeat(self) -> None:
        self.last_heartbeat = time.monotonic()
        _HEARTBEAT_AGE.labels(self.name).set(0)

    @property
    def heartbeat_age(self) -> float:
        return time.monotonic() - self.last_heartbeat

    @property
    def healthy(self) -> bool:
        return (
            self.state == TaskState.RUNNING
            and not self._breaker.is_open
            and self.heartbeat_age <= self._heartbeat_timeout
        )

    async def _supervise(self) -> None:
        attempt = 0
        while self._running:
            if self._breaker.is_open:
                self.state = TaskState.CIRCUIT_OPEN
                _STATE.labels(self.name).set(0)
                logger.error("task_circuit_open", task=self.name)
                await asyncio.sleep(min(self._backoff.max_delay, 5.0))
                continue
            self.state = TaskState.RUNNING
            _STATE.labels(self.name).set(1)
            self.heartbeat()
            try:
                await self._factory()
                # Clean return: treat as a restartable cycle.
                attempt = 0
                self._breaker.record_success()
            except asyncio.CancelledError:
                raise
            except Exception:
                attempt += 1
                self.restarts += 1
                self._breaker.record_failure()
                _RESTARTS.labels(self.name).inc()
                _STATE.labels(self.name).set(0)
                delay = self._backoff.delay(attempt)
                self.state = TaskState.BACKOFF
                logger.exception(
                    "task_crashed", task=self.name, attempt=attempt, retry_in=round(delay, 2)
                )
                if not self._running:
                    break
                await asyncio.sleep(delay)


class Supervisor:
    """Owns a set of supervised tasks and reports aggregate health."""

    def __init__(self) -> None:
        self._tasks: dict[str, SupervisedTask] = {}

    def add(self, name: str, factory: TaskFactory, **kwargs: object) -> SupervisedTask:
        task = SupervisedTask(name, factory, **kwargs)  # type: ignore[arg-type]
        self._tasks[name] = task
        return task

    def start_all(self) -> None:
        for task in self._tasks.values():
            task.start()

    async def stop_all(self) -> None:
        await asyncio.gather(*(t.stop() for t in self._tasks.values()), return_exceptions=True)

    def watchdog(self) -> list[str]:
        """Return the names of unhealthy (crashed/circuit-open/stale) tasks."""
        stale = []
        for task in self._tasks.values():
            _HEARTBEAT_AGE.labels(task.name).set(round(task.heartbeat_age, 2))
            if not task.healthy:
                stale.append(task.name)
        return stale

    def health(self) -> dict[str, object]:
        return {
            "healthy": all(t.healthy for t in self._tasks.values()) if self._tasks else True,
            "tasks": {
                t.name: {
                    "state": t.state.value,
                    "healthy": t.healthy,
                    "restarts": t.restarts,
                    "heartbeat_age": round(t.heartbeat_age, 2),
                }
                for t in self._tasks.values()
            },
        }

    def get(self, name: str) -> SupervisedTask:
        return self._tasks[name]
