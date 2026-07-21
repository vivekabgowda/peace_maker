"""Options analytics: Black-Scholes greeks, implied volatility, PCR, max pain.

Pure functions (stdlib ``math`` only — no scipy) so they are fast and
golden-testable. Time is in years; rates and IV are decimals (0.06 = 6%).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution via the error function."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass(frozen=True)
class Greeks:
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float


def _d1_d2(spot: float, strike: float, t: float, r: float, iv: float) -> tuple[float, float]:
    vol_sqrt_t = iv * math.sqrt(t)
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t) / vol_sqrt_t
    d2 = d1 - vol_sqrt_t
    return d1, d2


def black_scholes(
    spot: float, strike: float, t: float, r: float, iv: float, option_type: str
) -> Greeks:
    """Black-Scholes price and greeks for a European option.

    ``theta`` is per-calendar-day; ``vega`` is per 1 percentage-point of IV.
    """
    option_type = option_type.upper()
    if t <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        intrinsic = max(0.0, (spot - strike) if option_type == "CE" else (strike - spot))
        sign = 1.0 if option_type == "CE" else -1.0
        return Greeks(
            price=intrinsic, delta=sign if intrinsic > 0 else 0.0, gamma=0.0, theta=0.0, vega=0.0
        )

    d1, d2 = _d1_d2(spot, strike, t, r, iv)
    discount = math.exp(-r * t)
    gamma = norm_pdf(d1) / (spot * iv * math.sqrt(t))
    vega = spot * norm_pdf(d1) * math.sqrt(t) / 100.0

    if option_type == "CE":
        price = spot * norm_cdf(d1) - strike * discount * norm_cdf(d2)
        delta = norm_cdf(d1)
        theta = (
            -(spot * norm_pdf(d1) * iv) / (2 * math.sqrt(t)) - r * strike * discount * norm_cdf(d2)
        ) / 365.0
    else:
        price = strike * discount * norm_cdf(-d2) - spot * norm_cdf(-d1)
        delta = norm_cdf(d1) - 1.0
        theta = (
            -(spot * norm_pdf(d1) * iv) / (2 * math.sqrt(t)) + r * strike * discount * norm_cdf(-d2)
        ) / 365.0

    return Greeks(price=price, delta=delta, gamma=gamma, theta=theta, vega=vega)


def implied_volatility(
    market_price: float,
    spot: float,
    strike: float,
    t: float,
    r: float,
    option_type: str,
    *,
    tol: float = 1e-5,
    max_iter: int = 100,
) -> float | None:
    """Recover IV from a market price via bisection. Returns None if not solvable."""
    if market_price <= 0 or t <= 0:
        return None
    low, high = 1e-4, 5.0
    for _ in range(max_iter):
        mid = (low + high) / 2
        price = black_scholes(spot, strike, t, r, mid, option_type).price
        if abs(price - market_price) < tol:
            return mid
        if price > market_price:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def put_call_ratio(total_pe_oi: int, total_ce_oi: int) -> float | None:
    """PCR by open interest."""
    if total_ce_oi <= 0:
        return None
    return total_pe_oi / total_ce_oi


def max_pain(oi_by_strike: dict[float, tuple[int, int]]) -> float | None:
    """Max-pain strike: the strike minimizing total option-writer payout.

    ``oi_by_strike`` maps strike -> (call_oi, put_oi).
    """
    if not oi_by_strike:
        return None
    strikes = sorted(oi_by_strike)
    best_strike: float | None = None
    best_loss = math.inf
    for expiry_price in strikes:
        total = 0.0
        for strike, (call_oi, put_oi) in oi_by_strike.items():
            total += max(0.0, expiry_price - strike) * call_oi  # calls ITM
            total += max(0.0, strike - expiry_price) * put_oi  # puts ITM
        if total < best_loss:
            best_loss = total
            best_strike = expiry_price
    return best_strike
