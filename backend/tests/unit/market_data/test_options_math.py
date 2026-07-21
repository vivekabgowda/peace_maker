"""Tests for options analytics (Black-Scholes, IV, PCR, max pain)."""

from __future__ import annotations

import pytest
from app.modules.market_data.options_math import (
    black_scholes,
    implied_volatility,
    max_pain,
    put_call_ratio,
)


def test_atm_call_put_parity() -> None:
    spot, strike, t, r, iv = 100.0, 100.0, 0.5, 0.06, 0.2
    call = black_scholes(spot, strike, t, r, iv, "CE").price
    put = black_scholes(spot, strike, t, r, iv, "PE").price
    # Put-call parity: C - P = S - K*e^{-rT}
    import math

    assert (call - put) == pytest.approx(spot - strike * math.exp(-r * t), abs=1e-6)


def test_call_delta_bounds() -> None:
    g = black_scholes(100.0, 100.0, 0.5, 0.06, 0.2, "CE")
    assert 0.0 < g.delta < 1.0
    assert g.gamma > 0
    assert g.vega > 0


def test_put_delta_negative() -> None:
    g = black_scholes(100.0, 100.0, 0.5, 0.06, 0.2, "PE")
    assert -1.0 < g.delta < 0.0


def test_implied_vol_roundtrip() -> None:
    spot, strike, t, r, true_iv = 100.0, 105.0, 0.25, 0.06, 0.22
    price = black_scholes(spot, strike, t, r, true_iv, "CE").price
    recovered = implied_volatility(price, spot, strike, t, r, "CE")
    assert recovered is not None
    assert recovered == pytest.approx(true_iv, abs=1e-3)


def test_expired_option_is_intrinsic() -> None:
    g = black_scholes(110.0, 100.0, 0.0, 0.06, 0.2, "CE")
    assert g.price == pytest.approx(10.0)


def test_put_call_ratio() -> None:
    assert put_call_ratio(1500, 1000) == pytest.approx(1.5)
    assert put_call_ratio(100, 0) is None


def test_max_pain_picks_min_writer_payout() -> None:
    # Heavy OI at 100 on both sides → max pain gravitates to 100.
    oi = {90.0: (100, 5000), 100.0: (200, 200), 110.0: (5000, 100)}
    assert max_pain(oi) == 100.0


def test_max_pain_empty() -> None:
    assert max_pain({}) is None
