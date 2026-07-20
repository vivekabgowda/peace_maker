"""Pure, deterministic technical-indicator functions.

No framework, provider, or database coupling — just numbers in, numbers out.
Each function returns a list aligned to the input length, with ``None`` for
warm-up bars where the indicator is not yet defined. This makes them trivially
unit-testable against golden values and safe to reuse in live and backtest paths.

Conventions:
- ``values``/``close`` etc. are lists of floats, oldest first.
- Multi-output indicators return a dataclass of aligned lists.
"""

from __future__ import annotations

from dataclasses import dataclass

Series = list[float]
OptSeries = list[float | None]


def _check(length: int, period: int) -> None:
    if period <= 0:
        raise ValueError("period must be positive")
    if length < 0:
        raise ValueError("empty series")


def sma(values: Series, period: int) -> OptSeries:
    """Simple moving average."""
    _check(len(values), period)
    out: OptSeries = [None] * len(values)
    if len(values) < period:
        return out
    window_sum = sum(values[:period])
    out[period - 1] = window_sum / period
    for i in range(period, len(values)):
        window_sum += values[i] - values[i - period]
        out[i] = window_sum / period
    return out


def ema(values: Series, period: int) -> OptSeries:
    """Exponential moving average (seeded with the SMA of the first ``period``)."""
    _check(len(values), period)
    out: OptSeries = [None] * len(values)
    if len(values) < period:
        return out
    k = 2.0 / (period + 1)
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def wilder_smooth(values: Series, period: int) -> OptSeries:
    """Wilder's RMA (used by RSI/ATR/ADX)."""
    _check(len(values), period)
    out: OptSeries = [None] * len(values)
    if len(values) < period:
        return out
    prev = sum(values[:period]) / period
    out[period - 1] = prev
    for i in range(period, len(values)):
        prev = (prev * (period - 1) + values[i]) / period
        out[i] = prev
    return out


def rsi(close: Series, period: int = 14) -> OptSeries:
    """Relative Strength Index (Wilder)."""
    n = len(close)
    out: OptSeries = [None] * n
    if n <= period:
        return out
    gains: Series = [0.0]
    losses: Series = [0.0]
    for i in range(1, n):
        change = close[i] - close[i - 1]
        gains.append(max(change, 0.0))
        losses.append(max(-change, 0.0))
    avg_gain = sum(gains[1 : period + 1]) / period
    avg_loss = sum(losses[1 : period + 1]) / period
    out[period] = _rsi_value(avg_gain, avg_loss)
    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out[i] = _rsi_value(avg_gain, avg_loss)
    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


@dataclass(frozen=True)
class MACDResult:
    macd: OptSeries
    signal: OptSeries
    histogram: OptSeries


def macd(close: Series, fast: int = 12, slow: int = 26, signal: int = 9) -> MACDResult:
    """Moving Average Convergence/Divergence."""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line: OptSeries = [
        (f - s) if f is not None and s is not None else None
        for f, s in zip(ema_fast, ema_slow, strict=True)
    ]
    # Signal = EMA of the defined portion of the MACD line.
    defined = [(i, v) for i, v in enumerate(macd_line) if v is not None]
    signal_line: OptSeries = [None] * len(close)
    hist: OptSeries = [None] * len(close)
    if len(defined) >= signal:
        vals = [v for _, v in defined]
        sig_vals = ema(vals, signal)
        for (idx, _), sig in zip(defined, sig_vals, strict=True):
            if sig is not None:
                signal_line[idx] = sig
                m = macd_line[idx]
                hist[idx] = (m - sig) if m is not None else None
    return MACDResult(macd_line, signal_line, hist)


def true_range(high: Series, low: Series, close: Series) -> Series:
    """True Range series (first bar uses high-low)."""
    n = len(close)
    tr: Series = [high[0] - low[0]] if n else []
    for i in range(1, n):
        tr.append(
            max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )
        )
    return tr


def atr(high: Series, low: Series, close: Series, period: int = 14) -> OptSeries:
    """Average True Range (Wilder)."""
    tr = true_range(high, low, close)
    return wilder_smooth(tr, period)


@dataclass(frozen=True)
class ADXResult:
    adx: OptSeries
    plus_di: OptSeries
    minus_di: OptSeries


def adx(high: Series, low: Series, close: Series, period: int = 14) -> ADXResult:
    """Average Directional Index with +DI/-DI."""
    n = len(close)
    empty: OptSeries = [None] * n
    if n <= period * 2:
        return ADXResult(list(empty), list(empty), list(empty))
    plus_dm: Series = [0.0]
    minus_dm: Series = [0.0]
    for i in range(1, n):
        up = high[i] - high[i - 1]
        down = low[i - 1] - low[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
    tr = true_range(high, low, close)
    atr_s = wilder_smooth(tr, period)
    plus_sm = wilder_smooth(plus_dm, period)
    minus_sm = wilder_smooth(minus_dm, period)

    plus_di: OptSeries = [None] * n
    minus_di: OptSeries = [None] * n
    dx: OptSeries = [None] * n
    for i in range(n):
        a = atr_s[i]
        if a and a != 0 and plus_sm[i] is not None and minus_sm[i] is not None:
            pdi = 100.0 * (plus_sm[i] / a)  # type: ignore[operator]
            mdi = 100.0 * (minus_sm[i] / a)  # type: ignore[operator]
            plus_di[i] = pdi
            minus_di[i] = mdi
            denom = pdi + mdi
            dx[i] = 100.0 * abs(pdi - mdi) / denom if denom else 0.0

    adx_out: OptSeries = [None] * n
    dx_defined = [(i, v) for i, v in enumerate(dx) if v is not None]
    if len(dx_defined) >= period:
        idxs = [i for i, _ in dx_defined]
        vals = [v for _, v in dx_defined]
        smoothed = wilder_smooth(vals, period)
        for pos, val in zip(idxs, smoothed, strict=True):
            adx_out[pos] = val
    return ADXResult(adx_out, plus_di, minus_di)


@dataclass(frozen=True)
class BollingerResult:
    upper: OptSeries
    middle: OptSeries
    lower: OptSeries


def bollinger(close: Series, period: int = 20, mult: float = 2.0) -> BollingerResult:
    """Bollinger Bands (population standard deviation)."""
    mid = sma(close, period)
    upper: OptSeries = [None] * len(close)
    lower: OptSeries = [None] * len(close)
    for i in range(period - 1, len(close)):
        window = close[i - period + 1 : i + 1]
        m = mid[i]
        if m is None:
            continue
        variance = sum((x - m) ** 2 for x in window) / period
        sd = variance**0.5
        upper[i] = m + mult * sd
        lower[i] = m - mult * sd
    return BollingerResult(upper, mid, lower)


@dataclass(frozen=True)
class SupertrendResult:
    line: OptSeries
    direction: list[int | None]  # 1 = uptrend, -1 = downtrend


def supertrend(
    high: Series, low: Series, close: Series, period: int = 10, mult: float = 3.0
) -> SupertrendResult:
    """SuperTrend indicator."""
    n = len(close)
    atr_s = atr(high, low, close, period)
    line: OptSeries = [None] * n
    direction: list[int | None] = [None] * n
    prev_upper = prev_lower = prev_st = None
    prev_dir = 1
    for i in range(n):
        a = atr_s[i]
        if a is None:
            continue
        mid = (high[i] + low[i]) / 2
        basic_upper = mid + mult * a
        basic_lower = mid - mult * a
        upper = basic_upper
        lower = basic_lower
        if prev_upper is not None:
            assert prev_lower is not None  # set together with prev_upper
            keep_upper = basic_upper < prev_upper or close[i - 1] > prev_upper
            keep_lower = basic_lower > prev_lower or close[i - 1] < prev_lower
            upper = basic_upper if keep_upper else prev_upper
            lower = basic_lower if keep_lower else prev_lower
        if prev_st is None:
            cur_dir = 1 if close[i] >= mid else -1
            st = lower if cur_dir == 1 else upper
        elif close[i] > (prev_upper if prev_dir == -1 else prev_st):  # type: ignore[operator]
            cur_dir = 1
            st = lower
        elif close[i] < (prev_lower if prev_dir == 1 else prev_st):  # type: ignore[operator]
            cur_dir = -1
            st = upper
        else:
            cur_dir = prev_dir
            st = lower if cur_dir == 1 else upper
        line[i] = st
        direction[i] = cur_dir
        prev_upper, prev_lower, prev_st, prev_dir = upper, lower, st, cur_dir
    return SupertrendResult(line, direction)


@dataclass(frozen=True)
class DonchianResult:
    upper: OptSeries
    lower: OptSeries
    middle: OptSeries


def donchian(high: Series, low: Series, period: int = 20) -> DonchianResult:
    """Donchian Channel."""
    n = len(high)
    upper: OptSeries = [None] * n
    lower: OptSeries = [None] * n
    middle: OptSeries = [None] * n
    for i in range(period - 1, n):
        hi = max(high[i - period + 1 : i + 1])
        lo = min(low[i - period + 1 : i + 1])
        upper[i] = hi
        lower[i] = lo
        middle[i] = (hi + lo) / 2
    return DonchianResult(upper, lower, middle)


def vwap(high: Series, low: Series, close: Series, volume: list[int]) -> OptSeries:
    """Session (cumulative) Volume-Weighted Average Price."""
    n = len(close)
    out: OptSeries = [None] * n
    cum_pv = 0.0
    cum_vol = 0.0
    for i in range(n):
        typical = (high[i] + low[i] + close[i]) / 3
        cum_pv += typical * volume[i]
        cum_vol += volume[i]
        out[i] = (cum_pv / cum_vol) if cum_vol else None
    return out


def obv(close: Series, volume: list[int]) -> Series:
    """On-Balance Volume."""
    n = len(close)
    out: Series = [0.0] * n
    for i in range(1, n):
        if close[i] > close[i - 1]:
            out[i] = out[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            out[i] = out[i - 1] - volume[i]
        else:
            out[i] = out[i - 1]
    return out


def volume_sma(volume: list[int], period: int = 20) -> OptSeries:
    """Simple moving average of volume."""
    return sma([float(v) for v in volume], period)
