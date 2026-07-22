"""Bootstrap confidence intervals for strategy performance metrics (Sprint 14).

Resamples a trade/return series with replacement to produce a non-parametric
confidence interval for a statistic (expectancy, Sharpe, profit factor, …). A
metric whose CI spans zero is reported as *not yet significant* — the honest
answer the CIO report asks for. Deterministic given a seed.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfidenceInterval:
    point: float
    low: float
    high: float
    level: float  # e.g. 0.95

    @property
    def significant(self) -> bool:
        """True when the whole interval sits on one side of zero."""
        return (self.low > 0.0 and self.high > 0.0) or (self.low < 0.0 and self.high < 0.0)

    def as_dict(self) -> dict[str, float | bool]:
        return {
            "point": round(self.point, 6),
            "low": round(self.low, 6),
            "high": round(self.high, 6),
            "level": self.level,
            "significant": self.significant,
        }


def bootstrap_ci(
    sample: Sequence[float],
    statistic: Callable[[Sequence[float]], float],
    *,
    resamples: int = 2000,
    level: float = 0.95,
    seed: int = 12345,
) -> ConfidenceInterval:
    """Percentile bootstrap CI for ``statistic`` over ``sample``."""
    point = statistic(sample)
    n = len(sample)
    if n < 2:
        return ConfidenceInterval(point=point, low=point, high=point, level=level)

    rng = random.Random(seed)
    stats: list[float] = []
    for _ in range(resamples):
        draw = [sample[rng.randrange(n)] for _ in range(n)]
        stats.append(statistic(draw))
    stats.sort()

    alpha = (1.0 - level) / 2.0
    lo_idx = max(0, int(alpha * resamples))
    hi_idx = min(resamples - 1, int((1.0 - alpha) * resamples))
    return ConfidenceInterval(point=point, low=stats[lo_idx], high=stats[hi_idx], level=level)
