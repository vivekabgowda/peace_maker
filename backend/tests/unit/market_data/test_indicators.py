"""Golden-value and property tests for the technical-indicator library."""

from __future__ import annotations

import pytest
from app.shared.indicators import (
    atr,
    bollinger,
    ema,
    macd,
    obv,
    rsi,
    sma,
    supertrend,
    vwap,
)


def test_sma_golden() -> None:
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_sma_shorter_than_period() -> None:
    assert sma([1, 2], 5) == [None, None]


def test_ema_golden() -> None:
    # seed = SMA(first 3) = 2; k = 0.5 → 3, 4
    assert ema([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]


def test_rsi_all_gains_approaches_100() -> None:
    values = [float(i) for i in range(1, 30)]
    result = rsi(values, 14)
    assert result[-1] == pytest.approx(100.0)


def test_rsi_bounded() -> None:
    values = [10, 12, 11, 13, 15, 14, 16, 18, 17, 19, 20, 22, 21, 23, 25, 24]
    for v in rsi(values, 14):
        if v is not None:
            assert 0.0 <= v <= 100.0


def test_atr_positive() -> None:
    highs = [float(10 + i) for i in range(20)]
    lows = [float(8 + i) for i in range(20)]
    closes = [float(9 + i) for i in range(20)]
    result = atr(highs, lows, closes, 14)
    assert result[-1] is not None
    assert result[-1] > 0


def test_macd_histogram_consistency() -> None:
    closes = [float(100 + (i % 7) - 3) for i in range(60)]
    res = macd(closes)
    for m, s, h in zip(res.macd, res.signal, res.histogram, strict=True):
        if m is not None and s is not None:
            assert h == pytest.approx(m - s)


def test_bollinger_ordering() -> None:
    closes = [float(100 + (i % 5)) for i in range(40)]
    res = bollinger(closes, 20, 2.0)
    for u, mid, low in zip(res.upper, res.middle, res.lower, strict=True):
        if u is not None and mid is not None and low is not None:
            assert low <= mid <= u


def test_supertrend_direction_values() -> None:
    highs = [float(100 + i) for i in range(40)]
    lows = [float(98 + i) for i in range(40)]
    closes = [float(99 + i) for i in range(40)]
    res = supertrend(highs, lows, closes, 10, 3.0)
    dirs = {d for d in res.direction if d is not None}
    assert dirs <= {1, -1}
    # A steadily rising series should end in an uptrend.
    assert res.direction[-1] == 1


def test_vwap_constant_price() -> None:
    highs = [100.0] * 5
    lows = [100.0] * 5
    closes = [100.0] * 5
    result = vwap(highs, lows, closes, [10, 20, 30, 40, 50])
    assert result[-1] == pytest.approx(100.0)


def test_obv_direction() -> None:
    closes = [10, 11, 10, 12]
    volumes = [100, 50, 30, 20]
    result = obv(closes, volumes)
    assert result == [0.0, 50.0, 20.0, 40.0]
