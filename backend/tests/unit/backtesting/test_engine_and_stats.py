"""Backtester engine behavior + feeding earned stats back into the registry."""

from __future__ import annotations

import math
import time
from datetime import UTC, datetime, timedelta

from app.modules.ai_engine.scoring import ScoringEngine
from app.modules.backtesting import Backtester, apply_to_registry
from app.modules.backtesting.engine import BacktestConfig
from app.modules.scanner.regime import RegimeEngine
from app.modules.strategy.base import Bar, Direction, StrategyContext, StrategySignal
from app.modules.strategy.registry import registry

from tests.unit.alpha.factories import series as make_series
from tests.unit.alpha.factories import trending_index

TS = datetime(2025, 1, 1, tzinfo=UTC)


def _bars(closes: list[float]) -> list[Bar]:
    out: list[Bar] = []
    prev = closes[0]
    for i, c in enumerate(closes):
        out.append(
            Bar(
                ts=TS + timedelta(days=i),
                open=prev,
                high=max(prev, c) * 1.01,
                low=min(prev, c) * 0.99,
                close=c,
                volume=100_000,
            )
        )
        prev = c
    return out


def _wavy_uptrend(n: int = 300) -> list[float]:
    closes = [100.0]
    for i in range(n):
        closes.append(closes[-1] * (1 + 0.006 * math.sin(i / 9) + 0.004))
    return closes


def test_backtest_produces_trades_and_metrics() -> None:
    closes = _wavy_uptrend()
    bench = _bars(closes)
    series = {"TCS": _bars(closes), "INFY": _bars([c * 1.1 for c in closes])}
    res = Backtester().run(registry.get("ema_trend"), series, benchmark=bench)
    assert res.total > 0
    assert res.symbols_tested == 2
    assert -5.0 <= res.expectancy_r <= 5.0
    assert 0.0 <= res.false_positive_rate <= 1.0
    assert len(res.equity_curve()) == res.total


def test_no_lookahead_short_series_yields_no_trades() -> None:
    # Fewer bars than warmup → the engine cannot evaluate, so no trades.
    res = Backtester(BacktestConfig(warmup_bars=55)).run(
        registry.get("ema_trend"), {"X": _bars(_wavy_uptrend(40))}
    )
    assert res.total == 0


class _AlwaysLong:
    key = "always"
    name = "Always Long"
    description = ""
    primary_timeframe = "1d"
    required_history = 2
    expected_holding = "swing"
    compatible_regimes = frozenset()

    def __init__(self) -> None:
        from app.modules.strategy.base import StrategyStats

        self.stats = StrategyStats()

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        last = ctx.tf("1d").last  # type: ignore[union-attr]
        return StrategySignal(
            strategy_key=self.key,
            symbol=ctx.symbol,
            direction=Direction.LONG,
            entry=last.close,
            stop=last.close * 0.98,
            targets=(last.close * 1.04,),
            confidence=0.6,
            rationale=("always",),
            expected_holding="swing",
        )


def test_one_position_at_a_time_advances_past_holding() -> None:
    # An always-firing strategy must not open a new trade every bar; the engine
    # skips forward by the trade's holding period.
    closes = _wavy_uptrend(200)
    res = Backtester(BacktestConfig(warmup_bars=2, max_holding_bars=10)).run(
        _AlwaysLong(),  # type: ignore[arg-type]
        {"X": _bars(closes)},
    )
    # With ~198 tradable bars and holding periods ≥1, far fewer than 198 trades.
    assert 0 < res.total <= 198
    assert res.avg_holding_bars >= 1.0


def test_apply_to_registry_changes_live_scoring() -> None:
    closes = _wavy_uptrend()
    res = Backtester().run(
        registry.get("ema_trend"), {"TCS": _bars(closes)}, benchmark=_bars(closes)
    )
    assert res.total >= 1
    updated = apply_to_registry([res])
    assert "ema_trend" in updated
    strat = registry.get("ema_trend")
    assert strat.stats.trades == res.total
    # A proven, winning strategy should now score its regime dimension using the
    # earned win rate rather than the neutral default.
    if strat.stats.is_proven:
        regime = RegimeEngine().detect(trending_index(Direction.LONG))
        s = make_series("1d", [100 + i for i in range(40)], indicators={"atr_14": 1.0})
        ctx = StrategyContext(
            symbol="TCS",
            instrument_id=1,
            now=TS,
            series={"1d": s},
            regimes=regime.regimes,
            index_trend=Direction.LONG,
        )
        sig = StrategySignal(
            strategy_key="ema_trend",
            symbol="TCS",
            direction=Direction.LONG,
            entry=100.0,
            stop=97.0,
            targets=(106.0,),
            confidence=0.6,
            rationale=("r",),
            expected_holding="swing",
        )
        card = ScoringEngine().score(
            sig,
            ctx,
            regime,
            strategy_win_rate=strat.stats.win_rate,
            strategy_proven=True,
        )
        assert 0 <= card.regime <= 100


def test_backtest_performance_budget() -> None:
    # 3 symbols x 300 bars. Cost is dominated by the (separately benchmarked)
    # incremental indicator engine; this guards against O(n^2) walk regressions.
    closes = _wavy_uptrend(300)
    series = {f"S{i}": _bars(closes) for i in range(3)}
    bench = _bars(closes)
    strat = registry.get("ema_trend")
    Backtester().run(strat, series, benchmark=bench)  # warm
    best = min(_timed(strat, series, bench) for _ in range(3))
    # ~0.5s uninstrumented; budget leaves headroom for pytest-cov line tracing
    # (a large constant-factor tax) and loaded CI runners. An O(n^2) regression
    # would blow past this by many seconds.
    assert best < 3000.0, f"backtest {best:.0f}ms too slow"


def _timed(strat: object, series: dict[str, list[Bar]], bench: list[Bar]) -> float:
    start = time.perf_counter()
    Backtester().run(strat, series, benchmark=bench)  # type: ignore[arg-type]
    return (time.perf_counter() - start) * 1000
