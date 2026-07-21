"""Portfolio awareness tests (Sprint 3, Step 7)."""

from __future__ import annotations

from dataclasses import replace

from app.modules.portfolio.awareness import (
    Held,
    PortfolioConstraints,
    PortfolioManager,
)
from app.modules.scanner.regime import RegimeEngine
from app.modules.strategy.base import Direction

from tests.unit.alpha.test_scoring_and_ranking import _opp


def _sectorize(symbol: str, composite: float, sector: str, direction=Direction.LONG):  # type: ignore[no-untyped-def]
    o = _opp(symbol, composite, direction)
    return replace(o, signal=replace(o.signal, tags=(*o.signal.tags, f"sector:{sector}")))


def test_sector_concentration_cap() -> None:
    # Disable correlation dedup (threshold > 1) to isolate the sector cap.
    mgr = PortfolioManager(
        PortfolioConstraints(max_per_sector=2, max_positions=10, correlation_threshold=2.0)
    )
    ranked = [
        _sectorize("A", 90, "IT"),
        _sectorize("B", 85, "IT"),
        _sectorize("C", 80, "IT"),  # third IT name → dropped
        _sectorize("D", 75, "BANK"),
    ]
    result = mgr.apply(ranked)
    kept = {o.symbol for o in result.accepted}
    assert "C" not in kept
    assert {"A", "B", "D"} <= kept
    assert any("sector cap" in reason for _, reason in result.dropped)


def test_correlation_dedup_same_sector_same_direction() -> None:
    mgr = PortfolioManager(PortfolioConstraints(correlation_threshold=0.7, max_per_sector=5))
    ranked = [_sectorize("A", 90, "IT"), _sectorize("B", 85, "IT")]
    # Default correlation proxy: same sector ⇒ 0.8 ≥ 0.7 ⇒ B is a correlated dupe.
    result = mgr.apply(ranked)
    assert [o.symbol for o in result.accepted] == ["A"]
    assert any("correlated" in reason for _, reason in result.dropped)


def test_opposite_direction_not_treated_as_correlated() -> None:
    mgr = PortfolioManager(PortfolioConstraints(correlation_threshold=0.7, max_per_sector=5))
    ranked = [
        _sectorize("A", 90, "IT", Direction.LONG),
        _sectorize("B", 85, "IT", Direction.SHORT),
    ]
    result = mgr.apply(ranked)
    assert {o.symbol for o in result.accepted} == {"A", "B"}


def test_total_risk_budget_caps_positions() -> None:
    mgr = PortfolioManager(
        PortfolioConstraints(per_trade_risk_pct=1.0, max_total_risk_pct=2.0, max_per_sector=9)
    )
    ranked = [_sectorize(s, 90 - i, f"S{i}") for i, s in enumerate(["A", "B", "C", "D"])]
    result = mgr.apply(ranked)
    assert len(result.accepted) == 2  # 2 x 1pct = 2pct budget
    assert result.total_risk_pct == 2.0


def test_held_positions_consume_sector_budget() -> None:
    mgr = PortfolioManager(PortfolioConstraints(max_per_sector=1))
    held = [Held(symbol="INFY", sector="IT", direction=Direction.LONG)]
    ranked = [_sectorize("A", 90, "IT")]
    result = mgr.apply(ranked, held=held)
    assert not result.accepted  # IT budget already used by the held position


def test_regime_engine_available_for_fixtures() -> None:
    # Guards the shared fixture import used across the suite.
    assert RegimeEngine() is not None
