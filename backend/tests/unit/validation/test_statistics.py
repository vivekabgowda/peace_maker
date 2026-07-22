"""Unit tests for the pure statistical primitives (Sprint 14)."""

from __future__ import annotations

import math

import pytest
from app.modules.validation.statistics import (
    kurtosis,
    mean,
    norm_cdf,
    norm_ppf,
    sharpe,
    skewness,
    stdev,
)


def test_mean_stdev() -> None:
    xs = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
    assert mean(xs) == pytest.approx(5.0)
    assert stdev(xs, sample=False) == pytest.approx(2.0)
    assert stdev(xs, sample=True) == pytest.approx(2.13809, abs=1e-4)


def test_norm_cdf_known_points() -> None:
    assert norm_cdf(0.0) == pytest.approx(0.5)
    assert norm_cdf(1.96) == pytest.approx(0.975, abs=1e-3)
    assert norm_cdf(-1.96) == pytest.approx(0.025, abs=1e-3)


def test_norm_ppf_is_inverse_of_cdf() -> None:
    for p in (0.025, 0.1, 0.5, 0.9, 0.975):
        assert norm_cdf(norm_ppf(p)) == pytest.approx(p, abs=1e-6)
    assert norm_ppf(0.975) == pytest.approx(1.959964, abs=1e-4)
    assert math.isinf(norm_ppf(0.0)) and norm_ppf(0.0) < 0


def test_skew_kurtosis_normal_like() -> None:
    symmetric = [-2.0, -1.0, 0.0, 1.0, 2.0]
    assert skewness(symmetric) == pytest.approx(0.0, abs=1e-9)
    # Right-skewed sample has positive skew.
    assert skewness([0.0, 0.0, 0.0, 0.0, 10.0]) > 0
    assert kurtosis(symmetric) > 0


def test_sharpe_zero_variance() -> None:
    assert sharpe([1.0, 1.0, 1.0]) == 0.0
    assert sharpe([1.0, -1.0, 1.0, -1.0]) == pytest.approx(0.0, abs=1e-9)
    assert sharpe([]) == 0.0
