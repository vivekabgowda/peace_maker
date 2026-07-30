"""Exponential-backoff reconnect supervision for the Kite ticker (Sprint 6).

The Kite ticker has its own reconnect, but the platform enforces its **own**
bounded exponential-backoff-with-jitter policy on top, so broker reconnect behaves
identically to every other resilient connection and is independently testable.
"""

from __future__ import annotations

import math
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
        exp = max(0, attempt - 1)
        # Cap the exponent *before* taking the power: once the raw delay reaches
        # ``max_delay`` it is clamped anyway, so a larger exponent changes nothing
        # except risking ``OverflowError`` — which happens when a broker rejects the
        # socket repeatedly (e.g. a 403 upgrade failure) and ``attempt`` climbs into
        # the thousands. Bounding the exponent keeps the result identical while never
        # overflowing a float.
        if self.factor > 1.0 and self.base > 0.0 and self.max_delay > 0.0:
            ceiling = math.ceil(math.log(self.max_delay / self.base, self.factor))
            exp = min(exp, max(0, ceiling))
        raw = self.base * (self.factor**exp)
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
