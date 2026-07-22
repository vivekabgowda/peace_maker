"""Time-ordered in-sample / out-of-sample partitioning (Sprint 14).

No look-ahead: the test segment is always strictly after the train segment.
Used by out-of-sample evaluation and as the building block for walk-forward.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Split:
    train_start: int
    train_end: int  # exclusive
    test_start: int
    test_end: int  # exclusive


def oos_split(n: int, *, oos_fraction: float = 0.3) -> Split:
    """Single in-sample/out-of-sample boundary over ``n`` ordered observations."""
    frac = min(0.9, max(0.05, oos_fraction))
    cut = int(round(n * (1.0 - frac)))
    cut = max(1, min(n - 1, cut)) if n >= 2 else n
    return Split(train_start=0, train_end=cut, test_start=cut, test_end=n)


def apply_split(seq: Sequence[T], split: Split) -> tuple[list[T], list[T]]:
    return (
        list(seq[split.train_start : split.train_end]),
        list(seq[split.test_start : split.test_end]),
    )


def walk_forward_windows(
    n: int, *, train_size: int, test_size: int, step: int | None = None
) -> list[Split]:
    """Rolling anchored/sliding windows: train then immediately-following test.

    ``step`` defaults to ``test_size`` (non-overlapping test windows). Returns an
    empty list if a single train+test window doesn't fit.
    """
    if train_size < 1 or test_size < 1 or n < train_size + test_size:
        return []
    stride = step if (step and step > 0) else test_size
    windows: list[Split] = []
    start = 0
    while start + train_size + test_size <= n:
        te_start = start + train_size
        windows.append(
            Split(
                train_start=start,
                train_end=te_start,
                test_start=te_start,
                test_end=te_start + test_size,
            )
        )
        start += stride
    return windows
