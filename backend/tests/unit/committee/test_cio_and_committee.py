"""CIO synthesis, veto handling, and the committee orchestrator + performance."""

from __future__ import annotations

import time

from app.modules.committee.base import (
    Agent,
    AgentReport,
    AgentRole,
    CommitteeBrief,
    PortfolioState,
    Stance,
)
from app.modules.committee.cio import ChiefInvestmentOfficer, Recommendation
from app.modules.committee.committee import InvestmentCommittee

from tests.unit.committee.factories import make_brief


def test_full_deliberation_produces_seven_reports_and_a_decision() -> None:
    result = InvestmentCommittee().deliberate(make_brief())
    assert len(result.reports) == 7
    d = result.decision
    # The mandated CIO deliverable is fully populated.
    assert d.recommendation in set(Recommendation)
    assert d.confidence_breakdown and len(d.confidence_breakdown) == 7
    assert d.bull_case  # aligned leader long has a bull case
    assert d.invalidation and "stop" in d.invalidation.lower()
    assert set(d.risk) >= {"entry", "stop", "risk_reward"}
    assert set(d.position) >= {"quantity", "risk_pct"}
    assert d.expected_holding
    assert d.rationale


def test_risk_veto_forces_reject_regardless_of_others() -> None:
    pf = PortfolioState(current_drawdown_pct=20.0, max_drawdown_pct=12.0)
    result = InvestmentCommittee().deliberate(make_brief(portfolio=pf))
    assert result.decision.vetoed is True
    assert result.decision.recommendation is Recommendation.REJECT
    assert result.decision.position["quantity"] == 0.0
    assert result.decision.veto_reasons


class _Bull(Agent):
    def __init__(self, role: AgentRole) -> None:
        self.role = role

    def review(self, brief: CommitteeBrief) -> AgentReport:
        return self._report(
            stance=Stance.STRONG_SUPPORT,
            confidence=1.0,
            headline="all in",
            findings=[self._bull("unanimous", "everyone agrees")],
            metrics={"recommended_qty": 10.0, "recommended_risk_pct": 1.0},
        )


def test_unanimous_support_yields_strong_buy() -> None:
    brief = make_brief()
    agents = [_Bull(role) for role in AgentRole]
    result = InvestmentCommittee(agents=agents).deliberate(brief)
    assert result.decision.recommendation is Recommendation.STRONG_BUY
    assert result.decision.consensus > 0.6


def test_alternatives_shape_holds() -> None:
    primary = make_brief()
    assert primary.opportunity.rank == 1
    decision = ChiefInvestmentOfficer().decide(
        primary, list(InvestmentCommittee().deliberate(primary).reports)
    )
    assert isinstance(decision.alternatives, tuple)


class _Broken(Agent):
    def __init__(self, role: AgentRole) -> None:
        self.role = role

    def review(self, brief: CommitteeBrief) -> AgentReport:
        raise RuntimeError("boom")


def test_broken_agent_is_isolated() -> None:
    brief = make_brief()
    agents: list[Agent] = [_Broken(AgentRole.TECHNICAL)]
    result = InvestmentCommittee(agents=agents).deliberate(brief)
    assert len(result.reports) == 1
    assert result.reports[0].stance is Stance.NEUTRAL  # abstained, did not crash


def test_deliberation_latency_under_25ms() -> None:
    brief = make_brief()
    committee = InvestmentCommittee()
    committee.deliberate(brief)  # warm up
    best_ms = min(_timed(committee, brief) for _ in range(5))
    assert best_ms < 25.0, f"committee deliberation {best_ms:.2f}ms exceeds 25ms budget"


def _timed(committee: InvestmentCommittee, brief: CommitteeBrief) -> float:
    start = time.perf_counter()
    committee.deliberate(brief)
    return (time.perf_counter() - start) * 1000
