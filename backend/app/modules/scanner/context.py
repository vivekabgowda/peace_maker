"""Context assembly — the I/O layer that feeds the pure scanner (Sprint 3, Step 3).

Reads recent candles from the market-data store, rebuilds the latest indicator
bundle by replaying them through the incremental engine, computes relative
strength vs. the benchmark, and packages everything into read-only
:class:`StrategyContext` objects. Kept separate from :mod:`engine` so the
orchestration logic stays pure and unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.modules.market_data.orm import Candle, Instrument
from app.modules.market_data.repository import MarketDataRepository
from app.modules.scanner.engine import RegimeInputs
from app.modules.strategy.base import Bar, OptionContext, Series, StrategyContext
from app.shared.indicators.incremental import RollingIndicatorState
from app.shared.market_calendar import session_open_dt
from app.shared.market_calendar.calendar import IST

logger = get_logger("scan_context")


@dataclass(frozen=True, slots=True)
class UniverseContexts:
    """Everything the scanner needs for one scan pass."""

    index_series: Series
    contexts: list[StrategyContext]
    regime_inputs: RegimeInputs
    median_turnover: float | None


class ContextBuilder:
    """Builds scan contexts from the market-data store."""

    def __init__(
        self,
        repo: MarketDataRepository,
        *,
        benchmark: str = "NIFTY",
        timeframes: tuple[str, ...] = ("5m", "1d"),
        rs_lookback: int = 20,
        history: int = 260,
    ) -> None:
        self._repo = repo
        self._benchmark = benchmark
        self._timeframes = timeframes
        self._rs_lookback = rs_lookback
        self._history = history

    async def build(
        self, *, fno_only: bool = False, now: datetime | None = None
    ) -> UniverseContexts:
        now = now or datetime.now(UTC)
        instruments = await self._repo.list_instruments(fno_only=fno_only)
        by_symbol = {i.symbol: i for i in instruments}

        index_inst = by_symbol.get(self._benchmark)
        # The regime engine runs off the daily benchmark series.
        index_daily = (
            await self._one_series(index_inst.id, "1d") if index_inst is not None else None
        )
        if index_daily is None:
            raise ValueError(f"benchmark {self._benchmark!r} has no daily history")

        index_closes = index_daily.closes()
        prev_close, day_open = await self._session_levels(index_inst, now)

        contexts: list[StrategyContext] = []
        turnovers: list[float] = []
        for inst in instruments:
            if inst.symbol == self._benchmark:
                continue
            ctx = await self._context_for(inst, index_closes, now)
            if ctx is None:
                continue
            contexts.append(ctx)
            s = ctx.tf(self._timeframes[0]) or next(iter(ctx.series.values()), None)
            if s is not None and len(s):
                turnovers.append(s.last.close * s.last.volume)

        median_turnover = _median(turnovers) if turnovers else None
        regime_inputs = RegimeInputs(now=now, prev_close=prev_close, day_open=day_open)
        return UniverseContexts(
            index_series=index_daily,
            contexts=contexts,
            regime_inputs=regime_inputs,
            median_turnover=median_turnover,
        )

    # -- Internals ----------------------------------------------------------
    async def _context_for(
        self, inst: Instrument, index_closes: list[float], now: datetime
    ) -> StrategyContext | None:
        series: dict[str, Series] = {}
        for tf in self._timeframes:
            s = await self._one_series(inst.id, tf)
            if s is not None:
                series[tf] = s
        if not series:
            return None

        daily = series.get("1d")
        rs = self._relative_strength(daily, index_closes) if daily else None
        prev_close = daily.bars[-2].close if daily and len(daily) >= 2 else None
        intraday = series.get("5m")
        day_open = intraday.bars[0].open if intraday and len(intraday) else None
        session_minutes = _session_minutes(now)

        return StrategyContext(
            symbol=inst.symbol,
            instrument_id=inst.id,
            now=now,
            series=series,
            regimes=frozenset(),  # filled by the engine from the detected regime
            sector=inst.sector,
            prev_close=prev_close,
            day_open=day_open,
            relative_strength=rs,
            session_minutes=session_minutes,
            options=OptionContext(),
        )

    async def _one_series(self, instrument_id: int, timeframe: str) -> Series | None:
        candles = await self._repo.recent_candles(instrument_id, timeframe, self._history)
        if not candles:
            return None
        bars = [_to_bar(c) for c in candles]
        indicators = _replay_indicators(bars)
        return Series(timeframe=timeframe, bars=bars, indicators=indicators)

    async def _session_levels(
        self, index_inst: Instrument | None, now: datetime
    ) -> tuple[float | None, float | None]:
        if index_inst is None:
            return None, None
        daily = await self._repo.recent_candles(index_inst.id, "1d", 3)
        intraday = await self._repo.recent_candles(index_inst.id, "5m", 5)
        prev_close = float(daily[-2].close) if len(daily) >= 2 else None
        day_open = float(intraday[0].open) if intraday else None
        return prev_close, day_open

    def _relative_strength(self, daily: Series, index_closes: list[float]) -> float | None:
        n = self._rs_lookback
        closes = daily.closes()
        if len(closes) < n + 1 or len(index_closes) < n + 1:
            return None
        stock_ret = (closes[-1] / closes[-n - 1] - 1) * 100
        index_ret = (index_closes[-1] / index_closes[-n - 1] - 1) * 100
        return stock_ret - index_ret


def _to_bar(c: Candle) -> Bar:
    return Bar(
        ts=c.ts,
        open=float(c.open),
        high=float(c.high),
        low=float(c.low),
        close=float(c.close),
        volume=int(c.volume),
    )


def _replay_indicators(bars: list[Bar]) -> dict[str, float | None]:
    """Rebuild the latest indicator bundle by replaying bars through the engine."""
    state = RollingIndicatorState()
    latest: dict[str, float | None] = {}
    for b in bars:
        latest = state.update(b.high, b.low, b.close, b.volume, b.ts)
    return latest


def _session_minutes(now: datetime) -> int | None:
    open_dt = session_open_dt(now)
    if open_dt is None:
        return None
    delta = now.astimezone(IST) - open_dt.astimezone(IST)
    minutes = int(delta.total_seconds() // 60)
    return minutes if minutes >= 0 else None


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
