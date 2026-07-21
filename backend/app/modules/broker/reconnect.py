"""Exponential-backoff reconnect supervision for the Kite ticker (Sprint 6).

The Kite ticker has its own reconnect, but the platform enforces its **own**
bounded exponential-backoff-with-jitter policy on top, so broker reconnect behaves
identically to every other resilient connection and is independently testable.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BackoffPolicy:
    """Bounded exponential backoff with full jitter."""

    base: float = 1.0
    factor: float = 2.0
    max_delay: float = 60.0
    jitter: float = 0.2

    def delay_for(self, attempt: int) -> float:
        """Delay (seconds) before reconnect ``attempt`` (1-indexed)."""
        raw = self.base * (self.factor ** max(0, attempt - 1))
        capped = min(raw, self.max_delay)
        if self.jitter <= 0:
            return capped
        spread = capped * self.jitter
        return max(0.0, capped + random.uniform(-spread, spread))


@dataclass
class ReconnectState:
    """Tracks reconnect attempts for health/metrics."""

    attempts: int = 0
    total_reconnects: int = 0
    connected: bool = False

    def on_disconnect(self) -> None:
        self.connected = False
        self.attempts += 1

    def on_connect(self) -> None:
        self.connected = True
        self.attempts = 0
        self.total_reconnects += 1
