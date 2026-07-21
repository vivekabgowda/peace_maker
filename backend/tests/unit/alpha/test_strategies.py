"""Strategy plugin tests — each fires on its setup and abstains otherwise."""

from __future__ import annotations

from app.modules.strategy.base import Direction
from app.modules.strategy.library import breakout, gap, momentum, trend, volatility
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.registry import registry

from tests.unit.alpha.factories import ctx, series


def test_all_plugins_registered() -> None:
    keys = set(registry.keys())
    assert {"orb", "vwap_breakout", "ema_trend", "vcp", "gap_and_go", "relative_strength"} <= keys
    assert len(registry) >= 12


def test_orb_fires_long_on_range_break_with_volume() -> None:
    # 6 five-minute bars; opening range = first 3. Last bar breaks above with volume.
    closes = [100, 100.5, 100.2, 100.8, 101.0, 101.6]
    vols = [100_000, 90_000, 95_000, 120_000, 130_000, 300_000]
    s = series("5m", closes, volumes=vols, indicators={"atr_14": 0.5})
    c = ctx(series_map={"5m": s}, session_minutes=30)
    sig = breakout.OpeningRangeBreakout().evaluate(c)
    assert sig is not None
    assert sig.direction is Direction.LONG
    assert sig.entry > sig.stop
    assert sig.risk_reward > 1


def test_orb_abstains_before_range_forms() -> None:
    s = series("5m", [100, 100.5, 100.2, 100.8], volumes=[1] * 4, indicators={"atr_14": 0.5})
    c = ctx(series_map={"5m": s}, session_minutes=5)  # too early
    assert breakout.OpeningRangeBreakout().evaluate(c) is None


def test_ema_trend_long_requires_stacked_emas() -> None:
    closes = [100 + i * 0.5 for i in range(60)]
    ind = {"ema_9": 128, "ema_21": 126, "ema_50": 120, "atr_14": 1.0, "adx_14": 28}
    s = series("1d", closes, indicators=ind)
    c = ctx(series_map={"1d": s}, index_trend=Direction.LONG)
    sig = trend.EMATrend().evaluate(c)
    assert sig is not None and sig.direction is Direction.LONG

    # Break the stack → abstain.
    s2 = series("1d", closes, indicators={**ind, "ema_9": 118})
    assert trend.EMATrend().evaluate(ctx(series_map={"1d": s2})) is None


def test_vcp_breakout_requires_contraction_and_volume() -> None:
    # Rising base (25 bars), tightening ranges (4 bars), then a breakout on 2.6x volume.
    base = [90 + i * 0.3 for i in range(25)]  # up to 97.2
    closes = [*base, 98.0, 98.05, 98.0, 98.02, 101.0]
    half = [1.0] * 23 + [0.9, 0.75, 0.6, 0.45, 0.32, 0.25, 0.6]  # shrinking, then breakout expands
    highs = [c + h for c, h in zip(closes, half, strict=True)]
    lows = [c - h for c, h in zip(closes, half, strict=True)]
    vols = [100_000] * (len(closes) - 1) + [260_000]
    s = series("1d", closes, highs=highs, lows=lows, volumes=vols, indicators={"atr_14": 1.0})
    sig = volatility.VolatilityContraction().evaluate(ctx(series_map={"1d": s}))
    assert sig is not None and sig.direction is Direction.LONG
    assert sig.features["volume_surge"] >= 1.5


def test_gap_and_go_fires_on_holding_gap() -> None:
    closes = [102.0, 102.5, 103.0, 103.4]
    s = series("5m", closes, volumes=[300_000] * 4, indicators={"atr_14": 0.6})
    c = ctx(series_map={"5m": s}, prev_close=100.0, day_open=102.0, session_minutes=20)
    sig = gap.GapAndGo().evaluate(c)
    assert sig is not None and sig.direction is Direction.LONG
    assert sig.features["gap_pct"] > 1.5


def test_relative_strength_needs_leadership_and_index_up() -> None:
    closes = [100 + i * 0.4 for i in range(40)]
    s = series("1d", closes, indicators={"ema_50": closes[-1] - 4, "atr_14": 1.0})
    strong = ctx(series_map={"1d": s}, relative_strength=5.0, index_trend=Direction.LONG)
    assert momentum.RelativeStrength().evaluate(strong) is not None
    # Lagging vs index → abstain.
    weak = ctx(series_map={"1d": s}, relative_strength=-1.0, index_trend=Direction.LONG)
    assert momentum.RelativeStrength().evaluate(weak) is None


def test_strategy_confidence_is_bounded() -> None:
    closes = [100 + i * 0.5 for i in range(60)]
    ind = {"ema_9": 128, "ema_21": 126, "ema_50": 120, "atr_14": 1.0, "adx_14": 60}
    s = series("1d", closes, indicators=ind)
    sig = trend.EMATrend().evaluate(ctx(series_map={"1d": s}, index_trend=Direction.LONG))
    assert sig is not None
    assert 0.0 <= sig.confidence <= 1.0


def test_compatibility_gate() -> None:
    orb = breakout.OpeningRangeBreakout()
    assert orb.is_compatible(frozenset({MarketRegime.TRENDING_BULL}))
    assert not orb.is_compatible(frozenset({MarketRegime.RANGE}))
