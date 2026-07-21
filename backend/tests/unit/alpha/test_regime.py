"""Market Regime Engine tests (Sprint 3, Step 1)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.scanner.regime import RegimeEngine
from app.modules.strategy.base import Direction
from app.modules.strategy.regime_types import MarketRegime

from tests.unit.alpha.factories import series, trending_index


def test_trending_bull_detected() -> None:
    engine = RegimeEngine()
    state = engine.detect(trending_index(Direction.LONG, adx=32))
    assert state.primary is MarketRegime.TRENDING_BULL
    assert state.index_trend is Direction.LONG
    assert state.confidence > 0.5


def test_trending_bear_detected() -> None:
    engine = RegimeEngine()
    state = engine.detect(trending_index(Direction.SHORT, adx=32))
    assert state.primary is MarketRegime.TRENDING_BEAR
    assert state.index_trend is Direction.SHORT


def test_range_when_adx_weak() -> None:
    # Choppy closes with a low ADX → range, not a trend.
    closes = [100 + (1 if i % 2 else -1) for i in range(60)]
    s = series("1d", closes, indicators={"ema_21": 100, "ema_50": 100, "adx_14": 12, "atr_14": 1.0})
    state = RegimeEngine().detect(s)
    assert state.primary is MarketRegime.RANGE


def test_high_volatility_overlay() -> None:
    s = trending_index(Direction.LONG)
    # ATR ~ 3% of price → high-vol overlay.
    s = series(
        "1d",
        s.closes(),
        indicators={**s.indicators, "atr_14": s.last.close * 0.03},
    )
    state = RegimeEngine().detect(s)
    assert MarketRegime.HIGH_VOLATILITY in state.regimes


def test_low_volatility_overlay() -> None:
    s = trending_index(Direction.LONG)
    s = series("1d", s.closes(), indicators={**s.indicators, "atr_14": s.last.close * 0.005})
    state = RegimeEngine().detect(s)
    assert MarketRegime.LOW_VOLATILITY in state.regimes


def test_gap_up_and_gap_down_panic() -> None:
    engine = RegimeEngine()
    s = trending_index(Direction.LONG)
    up = engine.detect(s, prev_close=100.0, day_open=101.5)
    assert MarketRegime.GAP_UP_TREND in up.regimes
    panic = engine.detect(s, prev_close=100.0, day_open=97.5)
    assert MarketRegime.GAP_DOWN_PANIC in panic.regimes
    assert MarketRegime.GLOBAL_RISK_OFF in panic.regimes  # inferred from sharp gap down
    assert panic.is_hostile


def test_event_overlays_from_calendar() -> None:
    engine = RegimeEngine()
    s = trending_index(Direction.LONG)
    # 2026-02-06 is an RBI policy day; 2026-02-01 budget day.
    rbi = engine.detect(s, now=datetime(2026, 2, 6, 6, 0, tzinfo=UTC))
    assert MarketRegime.RBI_DAY in rbi.regimes
    budget = engine.detect(s, now=datetime(2026, 2, 1, 6, 0, tzinfo=UTC))
    assert MarketRegime.BUDGET_DAY in budget.regimes


def test_explicit_global_risk_off_flag() -> None:
    s = trending_index(Direction.LONG)
    state = RegimeEngine().detect(s, global_risk_off=True)
    assert MarketRegime.GLOBAL_RISK_OFF in state.regimes
    assert state.is_hostile
