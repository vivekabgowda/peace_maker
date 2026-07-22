"""Pure statistical primitives for strategy validation (Sprint 14).

No third-party numerics (numpy is intentionally not a dependency): everything is
implemented from the standard library so it is transparent and unit-testable
against hand-worked or reference values. These back the deflated Sharpe,
bootstrap confidence intervals, and multiple-testing corrections.
"""

from __future__ import annotations

import math
from collections.abc import Sequence


def mean(xs: Sequence[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def stdev(xs: Sequence[float], *, sample: bool = True) -> float:
    n = len(xs)
    if n < 2:
        return 0.0
    mu = mean(xs)
    denom = (n - 1) if sample else n
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / denom)


def skewness(xs: Sequence[float]) -> float:
    """Population skewness (0 for <3 points or zero variance)."""
    n = len(xs)
    if n < 3:
        return 0.0
    mu = mean(xs)
    sd = stdev(xs, sample=False)
    if sd == 0:
        return 0.0
    return sum(((x - mu) / sd) ** 3 for x in xs) / n


def kurtosis(xs: Sequence[float]) -> float:
    """Non-excess (Pearson) kurtosis; 3.0 for a normal distribution."""
    n = len(xs)
    if n < 4:
        return 3.0
    mu = mean(xs)
    sd = stdev(xs, sample=False)
    if sd == 0:
        return 3.0
    return sum(((x - mu) / sd) ** 4 for x in xs) / n


def norm_cdf(x: float) -> float:
    """Standard normal CDF via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (probit) — Acklam's rational approximation.

    Accurate to ~1e-9 over (0, 1). Clamps the open interval endpoints.
    """
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf

    a = (
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    )
    b = (
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    )
    c = (
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    )
    d = (
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    )
    p_low = 0.02425
    p_high = 1.0 - p_low
    if p < p_low:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p <= p_high:
        q = p - 0.5
        r = q * q
        return (
            (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5])
            * q
            / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
        )
    q = math.sqrt(-2.0 * math.log(1.0 - p))
    return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
        (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
    )


def sharpe(returns: Sequence[float]) -> float:
    """Per-observation Sharpe ratio (mean/stdev). 0 if <2 points or no variance."""
    sd = stdev(returns)
    return mean(returns) / sd if sd > 0 else 0.0
