"""Incremental indicators — correctness vs. batch + performance target."""

from __future__ import annotations

import random
import time
from datetime import UTC, datetime, timedelta

import pytest
from app.shared.indicators import atr, ema, macd, rsi, supertrend
from app.shared.indicators.incremental import (
    IncrementalATR,
    IncrementalEMA,
    IncrementalMACD,
    IncrementalRSI,
    IncrementalSupertrend,
    RollingIndicatorState,
    SessionVWAP,
)


def _series(n: int = 300, seed: int = 3) -> tuple[list[float], list[float], list[float]]:
    rng = random.Random(seed)
    closes = [100.0]
    for _ in range(n - 1):
        closes.append(max(1.0, closes[-1] * (1 + rng.gauss(0, 0.003))))
    highs = [c * 1.004 for c in closes]
    lows = [c * 0.996 for c in closes]
    return highs, lows, closes


def test_incremental_ema_matches_batch() -> None:
    _, _, closes = _series()
    inc = IncrementalEMA(21)
    last = None
    for c in closes:
        last = inc.update(c)
    assert last == pytest.approx(ema(closes, 21)[-1])


def test_incremental_rsi_matches_batch() -> None:
    _, _, closes = _series()
    inc = IncrementalRSI(14)
    last = None
    for c in closes:
        last = inc.update(c)
    assert last == pytest.approx(rsi(closes, 14)[-1], abs=1e-6)


def test_incremental_atr_matches_batch() -> None:
    highs, lows, closes = _series()
    inc = IncrementalATR(14)
    last = None
    for h, low, c in zip(highs, lows, closes, strict=True):
        last = inc.update(h, low, c)
    assert last == pytest.approx(atr(highs, lows, closes, 14)[-1], abs=1e-6)


def test_incremental_macd_matches_batch() -> None:
    _, _, closes = _series()
    inc = IncrementalMACD()
    m = s = None
    for c in closes:
        m, s = inc.update(c)
    batch = macd(closes)
    assert m == pytest.approx(batch.macd[-1])
    assert s == pytest.approx(batch.signal[-1])


def test_incremental_supertrend_matches_batch() -> None:
    highs, lows, closes = _series()
    inc = IncrementalSupertrend()
    val = direction = None
    for h, low, c in zip(highs, lows, closes, strict=True):
        val, direction = inc.update(h, low, c)
    batch = supertrend(highs, lows, closes)
    assert direction == batch.direction[-1]
    assert val == pytest.approx(batch.line[-1], rel=1e-6)


def test_session_vwap_resets_each_session() -> None:
    vwap = SessionVWAP()
    ist_open = datetime(2026, 1, 27, 4, 0, tzinfo=UTC)  # ~09:30 IST
    v1 = vwap.update(100, 100, 100, 1000, ist_open)
    v2 = vwap.update(200, 200, 200, 1000, ist_open + timedelta(minutes=5))
    assert v1 == pytest.approx(100)
    assert v2 == pytest.approx(150)  # accumulated within the session
    # Next trading day → VWAP anchor resets.
    next_day = datetime(2026, 1, 28, 4, 0, tzinfo=UTC)
    v3 = vwap.update(300, 300, 300, 1000, next_day)
    assert v3 == pytest.approx(300)  # reset, not 200


def _under_coverage() -> bool:
    """True when pytest-cov is tracing — wall-clock timing is meaningless then."""
    try:
        import coverage

        return coverage.Coverage.current() is not None
    except Exception:
        return False


@pytest.mark.skipif(
    _under_coverage(), reason="wall-clock timing is meaningless under coverage line-tracing"
)
def test_rolling_update_under_5ms() -> None:
    highs, lows, closes = _series(300)
    state = RollingIndicatorState()
    ts = datetime(2026, 1, 27, 4, 0, tzinfo=UTC)
    # Warm up.
    for h, low, c in zip(highs, lows, closes, strict=True):
        state.update(h, low, c, 1000, ts)
    # Measure steady-state update latency. Take the best of several passes:
    # scheduling jitter on shared CI runners only ever inflates wall-clock, so
    # the minimum average is the truest steady-state cost and de-flakes the gate.
    n = 500
    best_ms = min(_timed_pass(state, highs, lows, closes, ts, n) for _ in range(5))
    assert best_ms < 5.0, f"indicator update {best_ms:.2f}ms exceeds 5ms target"


def _timed_pass(
    state: RollingIndicatorState,
    highs: list[float],
    lows: list[float],
    closes: list[float],
    ts: datetime,
    n: int,
) -> float:
    start = time.perf_counter()
    for i in range(n):
        state.update(highs[-1], lows[-1], closes[-1] + i * 0.01, 1000, ts)
    return (time.perf_counter() - start) / n * 1000
