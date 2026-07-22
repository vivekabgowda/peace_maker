"""Monte Carlo simulation of a strategy's trade sequence (Sprint 14).

Given a set of realized per-trade returns (in R or currency), resample them to
build many alternative equity paths. This exposes the *distribution* of outcomes
the historical single path hides — worst-case drawdown, return dispersion, and
the probability of a losing run — which is exactly the risk-of-ruin lens the CIO
report asks for. Pure and deterministic (seeded).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.validation.statistics import mean


def _percentile(sorted_xs: Sequence[float], q: float) -> float:
    if not sorted_xs:
        return 0.0
    idx = min(len(sorted_xs) - 1, max(0, int(q * (len(sorted_xs) - 1))))
    return sorted_xs[idx]


def _max_drawdown(path: Sequence[float]) -> float:
    """Peak-to-trough of a cumulative path (returned as a positive magnitude)."""
    peak = 0.0
    equity = 0.0
    worst = 0.0
    for step in path:
        equity += step
        peak = max(peak, equity)
        worst = max(worst, peak - equity)
    return worst


@dataclass(frozen=True, slots=True)
class MonteCarloResult:
    n_trades: int
    simulations: int
    method: str
    final_return: dict[str, float]  # distribution of total return
    max_drawdown: dict[str, float]  # distribution of worst drawdown
    prob_loss: float  # P(total return < 0)

    def as_dict(self) -> dict[str, object]:
        return {
            "n_trades": self.n_trades,
            "simulations": self.simulations,
            "method": self.method,
            "final_return": self.final_return,
            "max_drawdown": self.max_drawdown,
            "prob_loss": round(self.prob_loss, 4),
        }


def monte_carlo(
    trade_returns: Sequence[float],
    *,
    simulations: int = 2000,
    method: str = "resample",
    seed: int = 20240722,
) -> MonteCarloResult:
    """Simulate ``simulations`` alternative equity paths from ``trade_returns``.

    ``method``:
      - ``"resample"`` — bootstrap (sample trades with replacement); preserves the
        empirical return distribution, breaks path/order dependence.
      - ``"shuffle"`` — permute the same trades; tests whether results depend on
        the historical ordering (same totals, different drawdowns).
    """
    n = len(trade_returns)
    if n == 0:
        empty = {"p05": 0.0, "p50": 0.0, "p95": 0.0, "mean": 0.0}
        return MonteCarloResult(0, 0, method, dict(empty), dict(empty), 0.0)

    rng = random.Random(seed)
    finals: list[float] = []
    drawdowns: list[float] = []
    losses = 0
    base = list(trade_returns)
    for _ in range(simulations):
        if method == "shuffle":
            path = base[:]
            rng.shuffle(path)
        else:
            path = [base[rng.randrange(n)] for _ in range(n)]
        total = sum(path)
        finals.append(total)
        drawdowns.append(_max_drawdown(path))
        if total < 0:
            losses += 1

    finals.sort()
    drawdowns.sort()
    return MonteCarloResult(
        n_trades=n,
        simulations=simulations,
        method="shuffle" if method == "shuffle" else "resample",
        final_return={
            "p05": round(_percentile(finals, 0.05), 4),
            "p50": round(_percentile(finals, 0.50), 4),
            "p95": round(_percentile(finals, 0.95), 4),
            "mean": round(mean(finals), 4),
        },
        max_drawdown={
            "p50": round(_percentile(drawdowns, 0.50), 4),
            "p95": round(_percentile(drawdowns, 0.95), 4),
            "worst": round(drawdowns[-1], 4),
        },
        prob_loss=losses / simulations,
    )
