"""Small, pure technical helpers shared across strategies.

Deliberately dependency-free (plain floats) so strategies stay unit-testable in
isolation and identical in live scan and backtest.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


def sma(values: Sequence[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    return sum(values[-period:]) / period


def highest(values: Sequence[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    return max(values[-period:])


def lowest(values: Sequence[float], period: int) -> float | None:
    if len(values) < period or period <= 0:
        return None
    return min(values[-period:])


def pct_change(a: float, b: float) -> float:
    """Percent change from ``a`` to ``b`` (0 when ``a`` is 0)."""
    return (b - a) / a * 100.0 if a else 0.0


def true_range(high: float, low: float, prev_close: float) -> float:
    return max(high - low, abs(high - prev_close), abs(low - prev_close))


@dataclass(frozen=True, slots=True)
class CPR:
    """Central Pivot Range + classic pivots from the prior session's HLC."""

    pivot: float
    bc: float
    tc: float
    r1: float
    r2: float
    s1: float
    s2: float

    @property
    def width(self) -> float:
        return abs(self.tc - self.bc)


def central_pivot_range(high: float, low: float, close: float) -> CPR:
    """Compute CPR/pivots from a completed session (used by CPR-breakout)."""
    pivot = (high + low + close) / 3.0
    bc = (high + low) / 2.0
    tc = pivot - bc + pivot  # reflection of BC through the pivot
    lo, hi = (bc, tc) if bc <= tc else (tc, bc)
    return CPR(
        pivot=pivot,
        bc=lo,
        tc=hi,
        r1=2 * pivot - low,
        r2=pivot + (high - low),
        s1=2 * pivot - high,
        s2=pivot - (high - low),
    )


def is_contracting(ranges: Sequence[float], lookback: int = 5) -> bool:
    """True if recent bar ranges are shrinking (volatility contraction)."""
    if len(ranges) < lookback + 1:
        return False
    window = ranges[-lookback:]
    prior = ranges[-(lookback + 1)]
    return max(window) <= prior and window[-1] <= window[0]


def slope(values: Sequence[float]) -> float:
    """Least-squares slope of ``values`` against index (trend of a line)."""
    n = len(values)
    if n < 2:
        return 0.0
    xs = range(n)
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, values, strict=True))
    den = sum((x - mean_x) ** 2 for x in xs)
    return num / den if den else 0.0
