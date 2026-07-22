"""Parameter-stability analysis (Sprint 14).

An edge that only appears at one knife-edge parameter value is almost certainly
an overfit. This measures how a metric varies across a parameter grid: a robust
strategy shows a broad plateau (low dispersion), a fragile one a sharp spike.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.validation.statistics import mean, stdev


@dataclass(frozen=True, slots=True)
class StabilityReport:
    n_points: int
    best_value: float
    mean_value: float
    stdev_value: float
    coefficient_of_variation: float  # stdev / |mean|; lower = more stable
    plateau_fraction: float  # share of points within `plateau_tol` of the best
    is_robust: bool

    def as_dict(self) -> dict[str, float | bool | int]:
        return {
            "n_points": self.n_points,
            "best_value": round(self.best_value, 6),
            "mean_value": round(self.mean_value, 6),
            "stdev_value": round(self.stdev_value, 6),
            "coefficient_of_variation": round(self.coefficient_of_variation, 6),
            "plateau_fraction": round(self.plateau_fraction, 4),
            "is_robust": self.is_robust,
        }


def analyze_stability(
    metric_values: Sequence[float],
    *,
    plateau_tol: float = 0.2,
    robust_cov: float = 0.5,
    robust_plateau: float = 0.5,
) -> StabilityReport:
    """Summarize dispersion of ``metric_values`` across a parameter grid.

    ``plateau_tol`` is the relative distance from the best value still counted as
    "on the plateau". A grid is flagged robust when its coefficient of variation
    is low AND a meaningful fraction of points sit near the best.
    """
    n = len(metric_values)
    if n == 0:
        return StabilityReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, False)

    mu = mean(metric_values)
    sd = stdev(metric_values)
    best = max(metric_values)
    cov = sd / abs(mu) if mu != 0 else float("inf")

    if best == 0:
        plateau = 1.0
    else:
        band = abs(best) * plateau_tol
        plateau = sum(1 for v in metric_values if abs(v - best) <= band) / n

    is_robust = (cov <= robust_cov) and (plateau >= robust_plateau)
    return StabilityReport(
        n_points=n,
        best_value=best,
        mean_value=mu,
        stdev_value=sd,
        coefficient_of_variation=cov if cov != float("inf") else 0.0,
        plateau_fraction=plateau,
        is_robust=is_robust,
    )
