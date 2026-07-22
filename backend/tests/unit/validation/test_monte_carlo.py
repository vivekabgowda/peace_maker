"""Tests for the Monte Carlo simulator (Sprint 14)."""

from __future__ import annotations

import pytest
from app.modules.validation.monte_carlo import monte_carlo


def test_empty_returns_zeroed_result() -> None:
    r = monte_carlo([], simulations=100)
    assert r.n_trades == 0 and r.simulations == 0
    assert r.prob_loss == 0.0


def test_all_winners_never_lose() -> None:
    r = monte_carlo([1.0] * 30, simulations=500)
    assert r.prob_loss == 0.0
    assert r.final_return["p50"] == pytest.approx(30.0)
    assert r.max_drawdown["worst"] == 0.0  # monotically rising path


def test_all_losers_always_lose() -> None:
    r = monte_carlo([-1.0] * 30, simulations=500)
    assert r.prob_loss == 1.0
    assert r.max_drawdown["worst"] == pytest.approx(30.0)


def test_deterministic_given_seed() -> None:
    sample = [1.0, -0.5, 2.0, -1.0, 0.5, -0.3]
    a = monte_carlo(sample, simulations=1000, seed=1)
    b = monte_carlo(sample, simulations=1000, seed=1)
    assert a.as_dict() == b.as_dict()


def test_shuffle_preserves_total_but_varies_drawdown() -> None:
    sample = [1.0, 1.0, 1.0, -1.0, -1.0]  # sums to +1
    r = monte_carlo(sample, simulations=500, method="shuffle")
    # Every shuffled path has the same total (sum is order-invariant).
    assert r.final_return["p05"] == pytest.approx(1.0)
    assert r.final_return["p95"] == pytest.approx(1.0)
    assert r.method == "shuffle"
    # But ordering changes the worst drawdown.
    assert r.max_drawdown["worst"] >= r.max_drawdown["p50"]


def test_percentiles_are_ordered() -> None:
    import random

    rng = random.Random(3)
    sample = [rng.gauss(0.1, 1.0) for _ in range(100)]
    r = monte_carlo(sample, simulations=1000)
    assert r.final_return["p05"] <= r.final_return["p50"] <= r.final_return["p95"]
    assert 0.0 <= r.prob_loss <= 1.0
