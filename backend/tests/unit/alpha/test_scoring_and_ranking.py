"""Scoring, opportunity ranking, and NO-TRADE verdict tests (Steps 4-6)."""

from __future__ import annotations

from app.modules.ai_engine.scoring import ScoringEngine
from app.modules.scanner.explain import build_explanation
from app.modules.scanner.opportunity import (
    MIN_BEST_COMPOSITE,
    Opportunity,
    rank_opportunities,
)
from app.modules.scanner.regime import RegimeEngine
from app.modules.strategy.base import Direction, StrategySignal
from app.modules.strategy.regime_types import MarketRegime

from tests.unit.alpha.factories import ctx, series, trending_index


def _signal(key: str = "ema_trend", conf: float = 0.7) -> StrategySignal:
    return StrategySignal(
        strategy_key=key,
        symbol="TCS",
        direction=Direction.LONG,
        entry=100.0,
        stop=97.0,
        targets=(106.0, 112.0),
        confidence=conf,
        rationale=("clean setup",),
        expected_holding="swing",
        tags=("swing", "trend"),
        features={"volume_surge": 2.0},
    )


def _ctx_long() -> object:
    s = series("1d", [100 + i * 0.4 for i in range(40)], indicators={"atr_14": 1.0})
    return ctx(series_map={"1d": s, "5m": s}, index_trend=Direction.LONG, relative_strength=4.0)


def test_scorecard_has_all_dimensions_and_bounds() -> None:
    regime = RegimeEngine().detect(trending_index(Direction.LONG))
    card = ScoringEngine().score(_signal(), _ctx_long(), regime)
    d = card.as_dict()
    for key in (
        "technical",
        "volume",
        "trend",
        "volatility",
        "liquidity",
        "sector",
        "news",
        "options",
        "regime",
        "risk",
        "portfolio_impact",
    ):
        assert 0.0 <= d[key] <= 100.0, key
    assert 0.0 <= card.composite <= 100.0
    assert 0.0 <= card.confidence <= 1.0


def test_hostile_regime_crushes_score() -> None:
    engine = ScoringEngine()
    good_regime = RegimeEngine().detect(trending_index(Direction.LONG))
    risk_off = RegimeEngine().detect(trending_index(Direction.LONG), global_risk_off=True)
    good = engine.score(_signal(), _ctx_long(), good_regime)
    bad = engine.score(_signal(), _ctx_long(), risk_off)
    assert bad.composite < good.composite
    assert bad.confidence < good.confidence


def _opp(symbol: str, composite: float, direction: Direction = Direction.LONG) -> Opportunity:
    regime = RegimeEngine().detect(trending_index(Direction.LONG))
    sig = StrategySignal(
        strategy_key="ema_trend",
        symbol=symbol,
        direction=direction,
        entry=100.0,
        stop=97.0,
        targets=(106.0,),
        confidence=0.6,
        rationale=("r",),
        expected_holding="swing",
    )
    card = ScoringEngine().score(sig, _ctx_long(), regime)
    # Force a known composite for deterministic ranking assertions.
    from dataclasses import replace

    card = replace(card, composite=composite)
    expl = build_explanation(sig, _ctx_long(), regime, card, "EMA Trend")
    return Opportunity(
        symbol=symbol,
        instrument_id=hash(symbol) % 1000,
        strategy_key="ema_trend",
        strategy_name="EMA Trend",
        signal=sig,
        scorecard=card,
        explanation=expl,
    )


def test_ranking_orders_by_composite_and_assigns_rank() -> None:
    regime = RegimeEngine().detect(trending_index(Direction.LONG))
    book = rank_opportunities(
        [_opp("A", 62), _opp("B", 80), _opp("C", 71)],
        regime,
        universe_size=3,
        scanned_strategies=13,
    )
    assert not book.no_trade
    syms = [o.symbol for o in book.opportunities]
    assert syms == ["B", "C", "A"]
    assert [o.rank for o in book.opportunities] == [1, 2, 3]


def test_below_floor_is_no_trade() -> None:
    regime = RegimeEngine().detect(trending_index(Direction.LONG))
    book = rank_opportunities(
        [_opp("A", MIN_BEST_COMPOSITE - 5)],
        regime,
        universe_size=1,
        scanned_strategies=13,
    )
    assert book.no_trade
    assert "conviction floor" in (book.no_trade_reason or "")


def test_hostile_regime_forces_no_trade_even_with_candidates() -> None:
    regime = RegimeEngine().detect(trending_index(Direction.LONG), global_risk_off=True)
    assert regime.is_hostile
    book = rank_opportunities(
        [_opp("A", 90)],
        regime,
        universe_size=1,
        scanned_strategies=13,
    )
    assert book.no_trade
    assert "hostile" in (book.no_trade_reason or "").lower()


def test_explanation_answers_the_six_questions() -> None:
    regime = RegimeEngine().detect(trending_index(Direction.LONG))
    card = ScoringEngine().score(_signal(), _ctx_long(), regime)
    expl = build_explanation(_signal(), _ctx_long(), regime, card, "EMA Trend")
    assert expl.why_this and expl.why_now
    assert expl.biggest_risk
    assert "stop" in expl.invalidation.lower()
    assert set(expl.confidence_breakdown) >= {"technical", "trend", "regime", "risk"}
    assert MarketRegime.TRENDING_BULL.value.replace("_", " ") in " ".join(expl.why_now)
