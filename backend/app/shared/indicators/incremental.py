"""Incremental (stateful) indicators — O(1) per bar, no DB reloads.

Replaces the "reload 300 candles from Postgres on every close" pattern
(Technical Design Review R0 #5, #6). Each instrument/timeframe keeps a small
rolling state in memory and updates on candle close in well under the 5 ms
target. VWAP is **session-anchored** and resets on each NSE session
(R0 #4) via the market calendar.

The output bundle matches the batch ``compute_bundle`` keys so downstream code
is unchanged.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

from app.shared.indicators.core import adx as _adx_batch
from app.shared.indicators.core import bollinger as _bollinger_batch
from app.shared.market_calendar import session_open_dt


class IncrementalEMA:
    def __init__(self, period: int) -> None:
        self.period = period
        self.k = 2.0 / (period + 1)
        self._seed: list[float] = []
        self.value: float | None = None

    def update(self, price: float) -> float | None:
        if self.value is None:
            self._seed.append(price)
            if len(self._seed) == self.period:
                self.value = sum(self._seed) / self.period
            return self.value
        self.value = price * self.k + self.value * (1 - self.k)
        return self.value


class IncrementalRSI:
    def __init__(self, period: int = 14) -> None:
        self.period = period
        self._prev: float | None = None
        self._gains: list[float] = []
        self._losses: list[float] = []
        self.avg_gain: float | None = None
        self.avg_loss: float | None = None
        self.value: float | None = None

    def update(self, close: float) -> float | None:
        if self._prev is None:
            self._prev = close
            return None
        change = close - self._prev
        self._prev = close
        gain, loss = max(change, 0.0), max(-change, 0.0)
        if self.avg_gain is None:
            self._gains.append(gain)
            self._losses.append(loss)
            if len(self._gains) == self.period:
                self.avg_gain = sum(self._gains) / self.period
                self.avg_loss = sum(self._losses) / self.period
                self.value = self._rsi()
            return self.value
        assert self.avg_gain is not None and self.avg_loss is not None
        self.avg_gain = (self.avg_gain * (self.period - 1) + gain) / self.period
        self.avg_loss = (self.avg_loss * (self.period - 1) + loss) / self.period
        self.value = self._rsi()
        return self.value

    def _rsi(self) -> float:
        assert self.avg_gain is not None and self.avg_loss is not None
        if self.avg_loss == 0:
            return 100.0
        rs = self.avg_gain / self.avg_loss
        return 100.0 - 100.0 / (1.0 + rs)


class IncrementalATR:
    def __init__(self, period: int = 14) -> None:
        self.period = period
        self._prev_close: float | None = None
        self._seed: list[float] = []
        self.value: float | None = None

    def update(self, high: float, low: float, close: float) -> float | None:
        if self._prev_close is None:
            tr = high - low
            self._prev_close = close
        else:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
            self._prev_close = close
        if self.value is None:
            self._seed.append(tr)
            if len(self._seed) == self.period:
                self.value = sum(self._seed) / self.period
            return self.value
        self.value = (self.value * (self.period - 1) + tr) / self.period
        return self.value


class IncrementalMACD:
    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9) -> None:
        self.fast = IncrementalEMA(fast)
        self.slow = IncrementalEMA(slow)
        self.signal = IncrementalEMA(signal)
        self.macd: float | None = None
        self.signal_value: float | None = None

    def update(self, close: float) -> tuple[float | None, float | None]:
        f = self.fast.update(close)
        s = self.slow.update(close)
        if f is not None and s is not None:
            self.macd = f - s
            self.signal_value = self.signal.update(self.macd)
        return self.macd, self.signal_value


class IncrementalSupertrend:
    def __init__(self, period: int = 10, mult: float = 3.0) -> None:
        self.atr = IncrementalATR(period)
        self.mult = mult
        self._prev_upper: float | None = None
        self._prev_lower: float | None = None
        self._prev_st: float | None = None
        self._prev_close: float | None = None
        self.dir = 1
        self.value: float | None = None

    def update(self, high: float, low: float, close: float) -> tuple[float | None, int | None]:
        a = self.atr.update(high, low, close)
        if a is None:
            self._prev_close = close
            return None, None
        mid = (high + low) / 2
        basic_upper = mid + self.mult * a
        basic_lower = mid - self.mult * a
        upper, lower = basic_upper, basic_lower
        if self._prev_upper is not None and self._prev_close is not None:
            assert self._prev_lower is not None
            if not (basic_upper < self._prev_upper or self._prev_close > self._prev_upper):
                upper = self._prev_upper
            if not (basic_lower > self._prev_lower or self._prev_close < self._prev_lower):
                lower = self._prev_lower
        if self._prev_st is None:
            self.dir = 1 if close >= mid else -1
            st = lower if self.dir == 1 else upper
        elif close > (self._prev_upper if self.dir == -1 else self._prev_st):  # type: ignore[operator]
            self.dir, st = 1, lower
        elif close < (self._prev_lower if self.dir == 1 else self._prev_st):  # type: ignore[operator]
            self.dir, st = -1, upper
        else:
            st = lower if self.dir == 1 else upper
        self._prev_upper, self._prev_lower, self._prev_st, self._prev_close = (
            upper,
            lower,
            st,
            close,
        )
        self.value = st
        return st, self.dir


class SessionVWAP:
    """Session-anchored VWAP — resets at each NSE session open (R0 #4)."""

    def __init__(self) -> None:
        self._session: datetime | None = None
        self._cum_pv = 0.0
        self._cum_vol = 0.0
        self.value: float | None = None

    def update(
        self, high: float, low: float, close: float, volume: int, bar_ts: datetime
    ) -> float | None:
        session = session_open_dt(bar_ts)
        if session is not None and session != self._session:
            self._session = session
            self._cum_pv = 0.0
            self._cum_vol = 0.0
        typical = (high + low + close) / 3
        self._cum_pv += typical * volume
        self._cum_vol += volume
        self.value = self._cum_pv / self._cum_vol if self._cum_vol else None
        return self.value


class RollingIndicatorState:
    """All tracked indicators for one (symbol, timeframe), updated per closed bar."""

    def __init__(self, window: int = 250) -> None:
        self.ema9 = IncrementalEMA(9)
        self.ema21 = IncrementalEMA(21)
        self.ema50 = IncrementalEMA(50)
        self.ema200 = IncrementalEMA(200)
        self.rsi = IncrementalRSI(14)
        self.atr = IncrementalATR(14)
        self.macd = IncrementalMACD()
        self.supertrend = IncrementalSupertrend()
        self.vwap = SessionVWAP()
        # Small bounded window only for ADX/Bollinger (cheap batch recompute).
        self._highs: deque[float] = deque(maxlen=window)
        self._lows: deque[float] = deque(maxlen=window)
        self._closes: deque[float] = deque(maxlen=window)

    def update(
        self, high: float, low: float, close: float, volume: int, bar_ts: datetime
    ) -> dict[str, float | None]:
        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)
        macd, macd_signal = self.macd.update(close)
        st, st_dir = self.supertrend.update(high, low, close)
        h, low_, c = list(self._highs), list(self._lows), list(self._closes)
        adx_res = _adx_batch(h, low_, c)
        boll = _bollinger_batch(c)
        return {
            "ema_9": self.ema9.update(close),
            "ema_21": self.ema21.update(close),
            "ema_50": self.ema50.update(close),
            "ema_200": self.ema200.update(close),
            "rsi_14": self.rsi.update(close),
            "macd": macd,
            "macd_signal": macd_signal,
            "atr_14": self.atr.update(high, low, close),
            "adx_14": _last(adx_res.adx),
            "vwap": self.vwap.update(high, low, close, volume, bar_ts),
            "supertrend": st,
            "supertrend_dir": float(st_dir) if st_dir is not None else None,
            "bb_upper": _last(boll.upper),
            "bb_lower": _last(boll.lower),
        }


def _last(series: list[float | None]) -> float | None:
    for v in reversed(series):
        if v is not None:
            return v
    return None
