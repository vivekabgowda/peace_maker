"""Tests for the candle builder: bucketing, aggregation, gaps, validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from app.modules.market_data.candle_builder import (
    CandleValidationError,
    TimeframeAggregator,
    WorkingCandle,
    floor_to_timeframe,
    validate_candle,
)


def _dt(minute: int, second: int = 0) -> datetime:
    return datetime(2026, 7, 20, 9, minute, second, tzinfo=UTC)


def test_floor_to_timeframe_5m() -> None:
    assert floor_to_timeframe(_dt(12, 34), "5m") == _dt(10, 0)
    assert floor_to_timeframe(_dt(15, 0), "5m") == _dt(15, 0)


def test_floor_to_timeframe_daily() -> None:
    ts = datetime(2026, 7, 20, 14, 30, tzinfo=UTC)
    assert floor_to_timeframe(ts, "1d") == datetime(2026, 7, 20, 0, 0, tzinfo=UTC)


def test_aggregation_within_bucket() -> None:
    closed: list[WorkingCandle] = []
    agg = TimeframeAggregator("X", "5m", lambda _s, _tf, c: closed.append(c))
    agg.add(100.0, 10, _dt(10, 0))
    agg.add(102.0, 5, _dt(11, 0))
    agg.add(99.0, 5, _dt(12, 0))
    assert closed == []  # still forming
    agg.flush()
    assert len(closed) == 1
    bar = closed[0]
    assert (bar.open, bar.high, bar.low, bar.close, bar.volume) == (100.0, 102.0, 99.0, 99.0, 20)


def test_new_bucket_closes_previous() -> None:
    closed: list[tuple[str, str, WorkingCandle]] = []
    agg = TimeframeAggregator("X", "5m", lambda s, tf, c: closed.append((s, tf, c)))
    agg.add(100.0, 10, _dt(10))  # bar 10:10
    agg.add(105.0, 10, _dt(16))  # bar 10:15 → closes the 10:10 bar
    assert len(closed) == 1
    assert closed[0][2].close == 100.0


def test_gap_recovery_fills_flat_bars() -> None:
    closed: list[WorkingCandle] = []
    agg = TimeframeAggregator("X", "1m", lambda _s, _tf, c: closed.append(c))
    agg.add(100.0, 10, _dt(0))  # bar 09:00
    agg.add(101.0, 10, _dt(3))  # jump to 09:03 → 09:00 closes, 09:01 & 09:02 filled flat
    assert len(closed) == 3
    assert closed[0].close == 100.0
    # Two synthesized flat bars at the last close, zero volume.
    assert closed[1].volume == 0 and closed[1].close == 100.0
    assert closed[2].volume == 0 and closed[2].close == 100.0


def test_validate_candle_rejects_bad_ohlc() -> None:
    with pytest.raises(CandleValidationError):
        validate_candle(o=10, h=9, low=8, c=9, volume=1)  # high < open
    with pytest.raises(CandleValidationError):
        validate_candle(o=10, h=12, low=11, c=11, volume=1)  # open < low
    with pytest.raises(CandleValidationError):
        validate_candle(o=10, h=12, low=8, c=11, volume=-1)  # negative volume


def test_validate_candle_accepts_valid() -> None:
    validate_candle(o=10, h=12, low=9, c=11, volume=100)  # no raise
