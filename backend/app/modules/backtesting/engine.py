"""Backtester — replays a strategy over historical bars, bar by bar (Sprint 5).

At each bar the engine reconstructs exactly the :class:`StrategyContext` the live
scanner would have built from the trailing window (same incremental indicators,
same relative-strength math), evaluates the strategy, and — when a signal fires —
simulates the trade on the bars that follow. Strictly causal: bar *i* only ever
sees bars ``0..i``. Holds one position per strategy per symbol at a time.

Because the strategy code is identical in live and backtest, a green backtest is
real evidence about the live edge, not a separate model.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.modules.backtesting.models import BacktestResult
from app.modules.backtesting.simulator import simulate_trade
from app.modules.strategy.base import Bar, Direction, Series, Strategy, StrategyContext
from app.shared.indicators.incremental import RollingIndicatorState


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    max_holding_bars: int = 20
    warmup_bars: int = 55  # let EMAs/RSI/ATR settle before trading
    rs_lookback: int = 20


class Backtester:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self._config = config or BacktestConfig()

    def run(
        self,
        strategy: Strategy,
        series_by_symbol: Mapping[str, Sequence[Bar]],
        *,
        benchmark: Sequence[Bar] | None = None,
    ) -> BacktestResult:
        """Backtest ``strategy`` across every symbol's bar series."""
        result = BacktestResult(strategy_key=strategy.key)
        bench_closes = [b.close for b in benchmark] if benchmark else None
        bench_ind = _replay_all(benchmark) if benchmark else None
        for symbol, bars in series_by_symbol.items():
            n = self._run_symbol(strategy, symbol, bars, bench_closes, bench_ind, result)
            if n > 0 or len(bars) > self._config.warmup_bars:
                result.symbols_tested += 1
            result.bars_tested += len(bars)
        return result

    def _run_symbol(
        self,
        strategy: Strategy,
        symbol: str,
        bars: Sequence[Bar],
        bench_closes: list[float] | None,
        bench_ind: list[dict[str, float | None]] | None,
        result: BacktestResult,
    ) -> int:
        cfg = self._config
        tf = strategy.primary_timeframe
        warmup = max(cfg.warmup_bars, strategy.required_history)
        if len(bars) <= warmup + 1:
            return 0

        # Precompute the incremental indicator bundle at every bar (causal).
        indicators = _replay_all(bars)
        # Strategies only scan the trailing window; cap the bars slice we hand
        # them to keep the walk O(n·k) instead of O(n²). Indicators are already
        # full-history-correct (incremental), so this doesn't change results.
        window_cap = max(strategy.required_history, cfg.warmup_bars)
        taken = 0
        i = warmup
        while i < len(bars) - 1:
            window = bars[max(0, i + 1 - window_cap) : i + 1]
            ctx = self._context(symbol, tf, window, indicators[i], bench_closes, bench_ind, i)
            signal = strategy.evaluate(ctx)
            if signal is None or signal.direction is Direction.NONE:
                i += 1
                continue
            trade = simulate_trade(
                signal,
                bars[i],
                # Only the holding horizon is needed — slicing the full tail here
                # would make the walk O(trades x n). Keep it O(max_holding_bars).
                bars[i + 1 : i + 1 + cfg.max_holding_bars],
                max_holding_bars=cfg.max_holding_bars,
            )
            result.trades.append(trade)
            taken += 1
            # Skip forward past the trade's holding period (one position at a time).
            i += max(1, trade.holding_bars)
        return taken

    def _context(
        self,
        symbol: str,
        timeframe: str,
        window: Sequence[Bar],
        indicators: dict[str, float | None],
        bench_closes: list[float] | None,
        bench_ind: list[dict[str, float | None]] | None,
        idx: int,
    ) -> StrategyContext:
        series = Series(timeframe=timeframe, bars=list(window), indicators=indicators)
        rs = _relative_strength(window, bench_closes, idx, self._config.rs_lookback)
        index_trend = _index_trend(bench_ind, idx)
        prev_close = window[-2].close if len(window) >= 2 else None
        return StrategyContext(
            symbol=symbol,
            instrument_id=0,
            now=window[-1].ts,
            series={timeframe: series},
            regimes=frozenset(),
            sector=None,
            prev_close=prev_close,
            day_open=None,
            relative_strength=rs,
            session_minutes=None,
            index_trend=index_trend,
        )


def _replay_all(bars: Sequence[Bar] | None) -> list[dict[str, float | None]]:
    """Indicator bundle at each bar index, computed causally (O(n))."""
    out: list[dict[str, float | None]] = []
    if not bars:
        return out
    state = RollingIndicatorState()
    for b in bars:
        out.append(state.update(b.high, b.low, b.close, b.volume, b.ts))
    return out


def _relative_strength(
    window: Sequence[Bar],
    bench_closes: list[float] | None,
    idx: int,
    lookback: int,
) -> float | None:
    if bench_closes is None or idx < lookback or len(window) <= lookback:
        return None
    stock_ret = (window[-1].close / window[-1 - lookback].close - 1) * 100
    index_ret = (bench_closes[idx] / bench_closes[idx - lookback] - 1) * 100
    return stock_ret - index_ret


def _index_trend(bench_ind: list[dict[str, float | None]] | None, idx: int) -> Direction:
    if bench_ind is None or idx >= len(bench_ind):
        return Direction.NONE
    bundle = bench_ind[idx]
    e21, e50 = bundle.get("ema_21"), bundle.get("ema_50")
    if e21 is None or e50 is None:
        return Direction.NONE
    if e21 > e50:
        return Direction.LONG
    if e21 < e50:
        return Direction.SHORT
    return Direction.NONE
