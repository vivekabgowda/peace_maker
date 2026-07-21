"""Investment Committee orchestrator (Sprint 4).

Runs the seven independent agents over a shared :class:`CommitteeBrief`, then
hands every report to the CIO for synthesis. Agents are pure and independent, so
they could run concurrently; the work is microsecond-scale, so we run them
sequentially and instrument each one. A misbehaving agent is isolated — its
failure becomes an OPPOSE-with-veto-off note rather than sinking the deliberation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from app.core.logging import get_logger
from app.modules.committee import metrics
from app.modules.committee.agents import DEFAULT_AGENTS
from app.modules.committee.base import (
    Agent,
    AgentReport,
    AgentRole,
    CommitteeBrief,
    Finding,
    Polarity,
    Stance,
)
from app.modules.committee.cio import ChiefInvestmentOfficer, CommitteeDecision

logger = get_logger("investment_committee")


@dataclass(frozen=True, slots=True)
class Deliberation:
    """The full record of one committee session — decision plus every report."""

    decision: CommitteeDecision
    reports: tuple[AgentReport, ...]
    elapsed_ms: float

    def as_dict(self) -> dict[str, object]:
        return {
            "decision": self.decision.as_dict(),
            "reports": [r.as_dict() for r in self.reports],
            "elapsed_ms": round(self.elapsed_ms, 3),
        }


class InvestmentCommittee:
    def __init__(
        self,
        agents: list[Agent] | None = None,
        cio: ChiefInvestmentOfficer | None = None,
    ) -> None:
        self._agents = agents if agents is not None else [cls() for cls in DEFAULT_AGENTS]
        self._cio = cio or ChiefInvestmentOfficer()

    @property
    def roster(self) -> list[AgentRole]:
        return [a.role for a in self._agents]

    def deliberate(self, brief: CommitteeBrief) -> Deliberation:
        started = time.perf_counter()
        reports: list[AgentReport] = []
        for agent in self._agents:
            reports.append(self._run_agent(agent, brief))
        decision = self._cio.decide(brief, reports)
        elapsed_ms = (time.perf_counter() - started) * 1000

        metrics.DELIBERATION_LATENCY.observe(elapsed_ms / 1000)
        metrics.DECISIONS.labels(recommendation=decision.recommendation.value).inc()
        logger.info(
            "committee_decision",
            symbol=brief.symbol,
            recommendation=decision.recommendation.value,
            consensus=round(decision.consensus, 3),
            vetoed=decision.vetoed,
            elapsed_ms=round(elapsed_ms, 2),
        )
        return Deliberation(decision=decision, reports=tuple(reports), elapsed_ms=elapsed_ms)

    def _run_agent(self, agent: Agent, brief: CommitteeBrief) -> AgentReport:
        started = time.perf_counter()
        try:
            report = agent.review(brief)
        except Exception:  # isolate a broken agent — never sink the committee
            logger.warning("agent_error", role=agent.role.value, symbol=brief.symbol)
            report = AgentReport(
                role=agent.role,
                stance=Stance.NEUTRAL,
                confidence=0.0,
                headline="Agent error — abstaining.",
                findings=(Finding(Polarity.NEUTRAL, "agent_error", "Analyzer raised; abstained."),),
            )
        metrics.AGENT_LATENCY.labels(role=agent.role.value).observe(time.perf_counter() - started)
        metrics.AGENT_STANCE.labels(role=agent.role.value, stance=report.stance.value).inc()
        if report.veto:
            metrics.AGENT_VETOES.labels(role=agent.role.value).inc()
        return report
