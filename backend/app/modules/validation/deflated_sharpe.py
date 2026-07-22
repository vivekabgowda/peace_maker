"""Probabilistic and Deflated Sharpe Ratio (Bailey & Lopez de Prado, 2014).

The Sharpe of a *selected* strategy is upward-biased: pick the best of N tries
and it looks good by luck. These estimators correct for that — directly
addressing the CIO due-diligence report's overfitting concern.

- **PSR** — probability the true Sharpe exceeds a benchmark, given sample length
  and the return distribution's skew/kurtosis (a fat-tailed, negatively-skewed
  series needs a higher observed Sharpe to be convincing).
- **DSR** — PSR with the benchmark set to the *expected maximum* Sharpe you'd see
  from N independent trials under the null; i.e. it "deflates" the observed
  Sharpe by how hard you searched.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.modules.validation.statistics import (
    kurtosis,
    norm_cdf,
    norm_ppf,
    sharpe,
    skewness,
    stdev,
)

_EULER = 0.5772156649015329


def _psr_denominator(sr: float, skew: float, kurt: float) -> float:
    # Standard error scaling of the Sharpe estimator under non-normality
    # (Mertens / Lo): 1 - skew*SR + (kurt-1)/4 * SR^2. Guarded to stay positive.
    val = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    return math.sqrt(val) if val > 1e-12 else 1e-6


def probabilistic_sharpe_ratio(
    *,
    observed_sr: float,
    n_obs: int,
    skew: float,
    kurt: float,
    benchmark_sr: float = 0.0,
) -> float:
    """P(true SR > benchmark_sr). Returns a probability in [0, 1]."""
    if n_obs < 2:
        return 0.0
    num = (observed_sr - benchmark_sr) * math.sqrt(n_obs - 1)
    return norm_cdf(num / _psr_denominator(observed_sr, skew, kurt))


def expected_max_sharpe(*, n_trials: int, sr_variance: float) -> float:
    """Expected maximum Sharpe from ``n_trials`` independent trials under the null.

    ``sr_variance`` is the cross-trial variance of the Sharpe estimates. Uses the
    Gumbel-based approximation from Bailey & Lopez de Prado.
    """
    if n_trials <= 1 or sr_variance <= 0:
        return 0.0
    sd = math.sqrt(sr_variance)
    a = norm_ppf(1.0 - 1.0 / n_trials)
    b = norm_ppf(1.0 - 1.0 / (n_trials * math.e))
    return sd * ((1.0 - _EULER) * a + _EULER * b)


def deflated_sharpe_ratio(
    *,
    observed_sr: float,
    n_obs: int,
    skew: float,
    kurt: float,
    n_trials: int,
    sr_variance: float,
) -> float:
    """P(true SR > expected max SR of the trials) — the deflated Sharpe."""
    benchmark = expected_max_sharpe(n_trials=n_trials, sr_variance=sr_variance)
    return probabilistic_sharpe_ratio(
        observed_sr=observed_sr,
        n_obs=n_obs,
        skew=skew,
        kurt=kurt,
        benchmark_sr=benchmark,
    )


def evaluate_returns(
    returns: Sequence[float],
    *,
    n_trials: int = 1,
    sr_variance: float | None = None,
    benchmark_sr: float = 0.0,
) -> dict[str, float]:
    """Convenience: full deflated/probabilistic Sharpe summary for a return series.

    ``sr_variance`` defaults to the variance of the series' own Sharpe estimate
    (a conservative single-strategy fallback when the cross-trial variance is
    unknown).
    """
    sr = sharpe(returns)
    sk = skewness(returns)
    ku = kurtosis(returns)
    n = len(returns)
    psr = probabilistic_sharpe_ratio(
        observed_sr=sr, n_obs=n, skew=sk, kurt=ku, benchmark_sr=benchmark_sr
    )
    if sr_variance is None:
        # Variance of the Sharpe estimator itself (per-observation units).
        var = (_psr_denominator(sr, sk, ku) ** 2) / (n - 1) if n > 1 else 0.0
    else:
        var = sr_variance
    dsr = deflated_sharpe_ratio(
        observed_sr=sr, n_obs=n, skew=sk, kurt=ku, n_trials=n_trials, sr_variance=var
    )
    return {
        "sharpe": round(sr, 4),
        "skew": round(sk, 4),
        "kurtosis": round(ku, 4),
        "n_obs": float(n),
        "stdev": round(stdev(returns), 6),
        "psr": round(psr, 4),
        "dsr": round(dsr, 4),
        "n_trials": float(n_trials),
    }
