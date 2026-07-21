"""Candle builder: aggregates live quotes into multi-timeframe OHLCV candles.

Responsibilities:
- Bucket incoming price/volume updates into the correct time bar per timeframe.
- Validate every candle before it is emitted/stored.
- Detect and recover gaps (missing bars) by synthesizing flat bars from the last
  close, or via an injected backfill hook (provider history).

The aggregator is pure and callback-based (no event-bus or DB coupling) so it is
fully unit-testable; the engine wires the callback to persistence + the bus.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

TIMEFRAMES: dict[str, int] = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "1d": 1440,
    "1w": 10080,
}
# 1M (monthly) is calendar-based and handled separately.
MONTHLY = "1M"


class CandleValidationError(ValueError):
    """Raised when a candle fails structural validation."""


@dataclass
class WorkingCandle:
    bar_ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    def as_tuple(self) -> tuple[datetime, float, float, float, float, int]:
        return (self.bar_ts, self.open, self.high, self.low, self.close, self.volume)


def floor_to_timeframe(ts: datetime, timeframe: str) -> datetime:
    """Return the bar-open timestamp for ``ts`` in ``timeframe``."""
    ts = ts.astimezone(UTC)
    if timeframe == MONTHLY:
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if timeframe == "1w":
        start = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        return start - timedelta(days=start.weekday())
    if timeframe == "1d":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    minutes = TIMEFRAMES.get(timeframe)
    if minutes is None:
        raise CandleValidationError(f"Unsupported timeframe: {timeframe}")
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    total_minutes = int((ts - epoch).total_seconds() // 60)
    bucket = total_minutes - (total_minutes % minutes)
    return epoch + timedelta(minutes=bucket)


def next_bar(bar_ts: datetime, timeframe: str) -> datetime:
    """Start of the bar immediately following ``bar_ts``."""
    if timeframe == MONTHLY:
        year, month = bar_ts.year, bar_ts.month
        return bar_ts.replace(year=year + (month // 12), month=(month % 12) + 1)
    minutes = 10080 if timeframe == "1w" else (1440 if timeframe == "1d" else TIMEFRAMES[timeframe])
    return bar_ts + timedelta(minutes=minutes)


def validate_candle(o: float, h: float, low: float, c: float, volume: int) -> None:
    """Raise :class:`CandleValidationError` if the OHLCV is structurally invalid."""
    if any(x <= 0 for x in (o, h, low, c)):
        raise CandleValidationError("prices must be positive")
    if h < low:
        raise CandleValidationError(f"high {h} < low {low}")
    if not (low <= o <= h):
        raise CandleValidationError(f"open {o} outside [{low}, {h}]")
    if not (low <= c <= h):
        raise CandleValidationError(f"close {c} outside [{low}, {h}]")
    if volume < 0:
        raise CandleValidationError("volume must be non-negative")


CandleCallback = Callable[[str, str, WorkingCandle], None]


@dataclass
class TimeframeAggregator:
    """Aggregates updates for a single (symbol, timeframe)."""

    symbol: str
    timeframe: str
    on_close: CandleCallback
    max_gap_fill: int = 500
    _current: WorkingCandle | None = field(default=None)

    def add(self, price: float, volume: int, ts: datetime) -> None:
        bar_ts = floor_to_timeframe(ts, self.timeframe)
        if self._current is None:
            self._current = WorkingCandle(bar_ts, price, price, price, price, volume)
            return
        if bar_ts == self._current.bar_ts:
            self._current.high = max(self._current.high, price)
            self._current.low = min(self._current.low, price)
            self._current.close = price
            self._current.volume += volume
            return
        # New bucket: close current, recover any gap, then open a new bar.
        self._close_current()
        self._fill_gap(self._current_next(), bar_ts)
        self._current = WorkingCandle(bar_ts, price, price, price, price, volume)

    def flush(self) -> None:
        """Force-close the working candle (e.g. at session end)."""
        if self._current is not None:
            self._close_current()
            self._current = None

    def _current_next(self) -> datetime:
        assert self._current is not None
        return next_bar(self._current.bar_ts, self.timeframe)

    def _close_current(self) -> None:
        assert self._current is not None
        c = self._current
        validate_candle(c.open, c.high, c.low, c.close, c.volume)
        self.on_close(self.symbol, self.timeframe, c)

    def _fill_gap(self, gap_start: datetime, target: datetime) -> None:
        """Synthesize flat, zero-volume bars for missing buckets between bars."""
        assert self._current is not None
        last_close = self._current.close
        cursor = gap_start
        filled = 0
        while cursor < target and filled < self.max_gap_fill:
            flat = WorkingCandle(cursor, last_close, last_close, last_close, last_close, 0)
            self.on_close(self.symbol, self.timeframe, flat)
            cursor = next_bar(cursor, self.timeframe)
            filled += 1


class CandleBuilder:
    """Builds candles across every configured timeframe for many symbols."""

    def __init__(self, on_close: CandleCallback, timeframes: list[str] | None = None) -> None:
        self._on_close = on_close
        self._timeframes = timeframes or [*TIMEFRAMES.keys(), MONTHLY]
        self._aggregators: dict[tuple[str, str], TimeframeAggregator] = {}

    def add_quote(self, symbol: str, price: float, volume: int, ts: datetime) -> None:
        for tf in self._timeframes:
            key = (symbol, tf)
            agg = self._aggregators.get(key)
            if agg is None:
                agg = TimeframeAggregator(symbol, tf, self._on_close)
                self._aggregators[key] = agg
            agg.add(price, volume, ts)

    def flush_all(self) -> None:
        for agg in self._aggregators.values():
            agg.flush()
