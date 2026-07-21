"""Each committee agent's behavior + the no-black-box citation guarantee."""

from __future__ import annotations

from app.modules.committee.agents import (
    DEFAULT_AGENTS,
    ChiefMarketStrategist,
    DevilsAdvocate,
    OptionsAnalyst,
    RiskManager,
)
from app.modules.committee.base import AgentRole, PortfolioState, Stance
from app.modules.scanner.regime import RegimeEngine
from app.modules.strategy.base import Direction, OptionContext

from tests.unit.alpha.factories import trending_index
from tests.unit.committee.factories import leader_ctx, make_brief


def test_roster_is_the_seven_roles() -> None:
    roles = {cls().role for cls in DEFAULT_AGENTS}
    assert roles == set(AgentRole)
    assert len(DEFAULT_AGENTS) == 7


def test_every_finding_cites_a_rule_indicator_or_condition() -> None:
    brief = make_brief()
    for cls in DEFAULT_AGENTS:
        report = cls().review(brief)
        for f in report.findings:
            assert f.citation.strip(), f"{report.role} finding lacks a citation"
            assert f.detail.strip()


def test_strategist_supports_aligned_trend() -> None:
    report = ChiefMarketStrategist().review(make_brief())
    assert report.stance in (Stance.SUPPORT, Stance.STRONG_SUPPORT)
    assert any("index_trend" in f.citation for f in report.bull_findings)


def test_strategist_opposes_in_hostile_regime() -> None:
    hostile = RegimeEngine().detect(trending_index(Direction.LONG), global_risk_off=True)
    report = ChiefMarketStrategist().review(make_brief(regime=hostile))
    assert report.stance in (Stance.CONCERN, Stance.OPPOSE)
    assert report.bear_findings


def test_risk_manager_vetoes_on_drawdown_breach() -> None:
    pf = PortfolioState(current_drawdown_pct=15.0, max_drawdown_pct=12.0)
    report = RiskManager().review(make_brief(portfolio=pf))
    assert report.veto is True
    assert report.veto_reason
    assert report.metrics["recommended_risk_pct"] == 0.0


def test_risk_manager_vetoes_on_daily_loss_and_heat() -> None:
    dl = RiskManager().review(make_brief(portfolio=PortfolioState(daily_loss_pct=5.0)))
    assert dl.veto
    heat = RiskManager().review(
        make_brief(portfolio=PortfolioState(portfolio_heat_pct=6.0, max_portfolio_heat_pct=6.0))
    )
    assert heat.veto


def test_devils_advocate_never_supports() -> None:
    report = DevilsAdvocate().review(make_brief())
    assert report.stance in (Stance.NEUTRAL, Stance.CONCERN, Stance.OPPOSE)
    assert all(f.polarity.value != "bull" for f in report.findings)


def test_options_abstains_without_data_and_reads_pcr() -> None:
    no_data = OptionsAnalyst().review(make_brief())  # leader_ctx has no option data
    assert no_data.stance is Stance.NEUTRAL

    ctx = leader_ctx(
        options=OptionContext(pcr=1.5, max_pain=140.0, total_ce_oi=100, total_pe_oi=180)
    )
    report = OptionsAnalyst().review(make_brief(context=ctx))
    # High PCR is contrarian-bullish for a long.
    assert any("PCR" in f.citation for f in report.findings)
    assert report.metrics["pcr"] == 1.5
