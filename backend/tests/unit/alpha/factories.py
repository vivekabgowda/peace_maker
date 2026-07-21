"""Synthetic data factories for Alpha Engine tests.

Builds deterministic Series/StrategyContext objects with injectable indicators, so
each strategy and the regime engine can be exercised in isolation without a DB.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta

from app.modules.strategy.base import (
    Bar,
    Direction,
    OptionContext,
    Series,
    StrategyContext,
)
from app.modules.strategy.regime_types import MarketRegime

BASE_TS = datetime(2026, 3, 10, 4, 0, tzinfo=UTC)  # a normal trading Tuesday (UTC)


def bars(
    closes: Sequence[float],
    *,
    tf_minutes: int = 1440,
    volumes: Sequence[int] | None = None,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    start: datetime = BASE_TS,
) -> list[Bar]:
    out: list[Bar] = []
    prev = closes[0]
    for i, c in enumerate(closes):
        hi = highs[i] if highs else max(prev, c) * 1.004
        lo = lows[i] if lows else min(prev, c) * 0.996
        vol = volumes[i] if volumes else 100_000
        out.append(
            Bar(
                ts=start + timedelta(minutes=tf_minutes * i),
                open=prev,
                high=hi,
                low=lo,
                close=c,
                volume=vol,
            )
        )
        prev = c
    return out


def series(
    timeframe: str,
    closes: Sequence[float],
    *,
    indicators: Mapping[str, float | None] | None = None,
    volumes: Sequence[int] | None = None,
    highs: Sequence[float] | None = None,
    lows: Sequence[float] | None = None,
    tf_minutes: int | None = None,
) -> Series:
    minutes = tf_minutes if tf_minutes is not None else (5 if timeframe == "5m" else 1440)
    return Series(
        timeframe=timeframe,
        bars=bars(closes, tf_minutes=minutes, volumes=volumes, highs=highs, lows=lows),
        indicators=dict(indicators or {}),
    )


def ctx(
    *,
    symbol: str = "TCS",
    instrument_id: int = 1,
    series_map: Mapping[str, Series],
    regimes: frozenset[MarketRegime] = frozenset(),
    index_trend: Direction = Direction.NONE,
    sector: str | None = "IT",
    prev_close: float | None = None,
    day_open: float | None = None,
    relative_strength: float | None = None,
    session_minutes: int | None = 60,
    options: OptionContext | None = None,
    news_score: float | None = None,
    now: datetime | None = None,
) -> StrategyContext:
    return StrategyContext(
        symbol=symbol,
        instrument_id=instrument_id,
        now=now or BASE_TS,
        series=dict(series_map),
        regimes=regimes,
        sector=sector,
        prev_close=prev_close,
        day_open=day_open,
        relative_strength=relative_strength,
        session_minutes=session_minutes,
        options=options,
        news_score=news_score,
        index_trend=index_trend,
    )


def trending_index(direction: Direction = Direction.LONG, *, adx: float = 30.0) -> Series:
    """A daily benchmark series with a clean up/down EMA stack for regime tests."""
    if direction is Direction.LONG:
        closes = [100 + i * 0.8 for i in range(60)]
        ind = {"ema_21": closes[-1] - 2, "ema_50": closes[-1] - 6, "adx_14": adx, "atr_14": 1.2}
    else:
        closes = [150 - i * 0.8 for i in range(60)]
        ind = {"ema_21": closes[-1] + 2, "ema_50": closes[-1] + 6, "adx_14": adx, "atr_14": 1.2}
    return series("1d", closes, indicators=ind)
