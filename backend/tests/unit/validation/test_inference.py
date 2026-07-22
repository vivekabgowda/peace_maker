"""Tests for deflated Sharpe, bootstrap CIs, multiple-testing, partitions."""

from __future__ import annotations

import random

import pytest
from app.modules.validation.bootstrap import bootstrap_ci
from app.modules.validation.deflated_sharpe import (
    deflated_sharpe_ratio,
    evaluate_returns,
    expected_max_sharpe,
    probabilistic_sharpe_ratio,
)
from app.modules.validation.multiple_testing import benjamini_hochberg, bonferroni
from app.modules.validation.partition import oos_split, walk_forward_windows
from app.modules.validation.statistics import mean, sharpe

# --- deflated / probabilistic Sharpe ---------------------------------------


def test_psr_increases_with_sample_length() -> None:
    short = probabilistic_sharpe_ratio(observed_sr=0.2, n_obs=20, skew=0.0, kurt=3.0)
    long = probabilistic_sharpe_ratio(observed_sr=0.2, n_obs=500, skew=0.0, kurt=3.0)
    assert 0.0 <= short <= 1.0 and long > short


def test_psr_zero_sharpe_is_half() -> None:
    assert probabilistic_sharpe_ratio(
        observed_sr=0.0, n_obs=100, skew=0.0, kurt=3.0
    ) == pytest.approx(0.5, abs=1e-6)


def test_negative_skew_and_fat_tails_lower_psr() -> None:
    base = probabilistic_sharpe_ratio(observed_sr=0.3, n_obs=100, skew=0.0, kurt=3.0)
    worse = probabilistic_sharpe_ratio(observed_sr=0.3, n_obs=100, skew=-1.0, kurt=8.0)
    assert worse < base


def test_expected_max_sharpe_grows_with_trials() -> None:
    one = expected_max_sharpe(n_trials=1, sr_variance=0.04)
    many = expected_max_sharpe(n_trials=100, sr_variance=0.04)
    assert one == 0.0 and many > 0.0


def test_dsr_is_deflated_below_psr_when_many_trials() -> None:
    psr = probabilistic_sharpe_ratio(observed_sr=0.4, n_obs=200, skew=0.0, kurt=3.0)
    dsr = deflated_sharpe_ratio(
        observed_sr=0.4, n_obs=200, skew=0.0, kurt=3.0, n_trials=50, sr_variance=0.02
    )
    assert dsr < psr


def test_evaluate_returns_summary_shape() -> None:
    rng = random.Random(1)
    rs = [rng.gauss(0.05, 1.0) for _ in range(300)]
    out = evaluate_returns(rs, n_trials=10)
    assert set(out) >= {"sharpe", "psr", "dsr", "skew", "kurtosis", "n_obs"}
    assert 0.0 <= out["psr"] <= 1.0 and 0.0 <= out["dsr"] <= 1.0


# --- bootstrap --------------------------------------------------------------


def test_bootstrap_ci_brackets_point_and_is_deterministic() -> None:
    rng = random.Random(7)
    sample = [rng.gauss(1.0, 2.0) for _ in range(200)]
    ci1 = bootstrap_ci(sample, mean, resamples=1000, seed=42)
    ci2 = bootstrap_ci(sample, mean, resamples=1000, seed=42)
    assert ci1.low <= ci1.point <= ci1.high
    assert (ci1.low, ci1.high) == (ci2.low, ci2.high)  # deterministic


def test_bootstrap_ci_significance_flag() -> None:
    strong = bootstrap_ci([1.0] * 50, mean, resamples=200)
    assert strong.significant  # all positive
    mixed = bootstrap_ci([-1.0, 1.0] * 50, sharpe, resamples=200)
    assert not mixed.significant  # spans zero


# --- multiple testing -------------------------------------------------------


def test_bonferroni_threshold() -> None:
    items = [("a", 0.001), ("b", 0.02), ("c", 0.30)]
    res = {r.label: r for r in bonferroni(items, alpha=0.05)}
    assert res["a"].reject  # 0.001 <= 0.05/3
    assert not res["b"].reject  # 0.02 > 0.0167
    assert not res["c"].reject


def test_benjamini_hochberg_rejects_more_than_bonferroni() -> None:
    items = [("a", 0.001), ("b", 0.013), ("c", 0.02), ("d", 0.30)]
    bh = {r.label: r.reject for r in benjamini_hochberg(items, alpha=0.05)}
    bonf = {r.label: r.reject for r in bonferroni(items, alpha=0.05)}
    assert sum(bh.values()) >= sum(bonf.values())
    assert bh["a"]


def test_multiple_testing_empty() -> None:
    assert bonferroni([]) == []
    assert benjamini_hochberg([]) == []


# --- partition --------------------------------------------------------------


def test_oos_split_boundary() -> None:
    s = oos_split(100, oos_fraction=0.3)
    assert s.train_end == 70 and s.test_start == 70 and s.test_end == 100


def test_walk_forward_windows_non_overlapping_tests() -> None:
    w = walk_forward_windows(100, train_size=40, test_size=20)
    assert len(w) == 3
    assert w[0].train_end == 40 and w[0].test_end == 60
    assert w[1].test_start == 60
    assert walk_forward_windows(30, train_size=40, test_size=20) == []
