"""Chief Investment Officer — synthesizes the committee into a final decision.

The CIO receives every agent report and produces the mandated deliverable:
recommendation, confidence breakdown, bull case, bear case, invalidation, risk,
position size, expected holding time, alternatives, and the reason each other
candidate was rejected. Any agent veto forces a REJECT — the CIO cannot override
the risk circuit breaker.

Fully explainable: every element traces back to cited agent findings.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.modules.committee.base import (
    AgentReport,
    AgentRole,
    CommitteeBrief,
    Finding,
)
from app.modules.strategy.base import Direction

# How much each role's signed stance counts toward the weighted vote. The
# Devil's Advocate and Risk Manager are weighted to enforce caution.
_ROLE_WEIGHTS: dict[AgentRole, float] = {
    AgentRole.STRATEGIST: 1.3,
    AgentRole.TECHNICAL: 1.4,
    AgentRole.OPTIONS: 0.8,
    AgentRole.NEWS: 0.7,
    AgentRole.RISK: 1.5,
    AgentRole.DEVILS_ADVOCATE: 1.2,
    AgentRole.PORTFOLIO_MANAGER: 1.1,
}


class Recommendation(StrEnum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    STRONG_SELL = "strong_sell"
    SELL = "sell"
    HOLD = "hold"  # actionable direction but not enough conviction
    REJECT = "reject"  # vetoed or net-negative


@dataclass(frozen=True, slots=True)
class Alternative:
    symbol: str
    strategy: str
    composite: float
    rejection_reason: str


@dataclass(frozen=True, slots=True)
class CommitteeDecision:
    """The CIO's final, fully-explained verdict."""

    symbol: str
    recommendation: Recommendation
    direction: Direction
    conviction: float  # 0..1 committee-weighted conviction
    consensus: float  # -1..1 signed weighted vote
    confidence_breakdown: dict[str, float]  # per-agent signed contribution
    bull_case: tuple[str, ...]
    bear_case: tuple[str, ...]
    invalidation: str
    risk: dict[str, float]
    position: dict[str, float]
    expected_holding: str
    alternatives: tuple[Alternative, ...]
    rationale: str
    vetoed: bool = False
    veto_reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "recommendation": self.recommendation.value,
            "direction": self.direction.value,
            "conviction": round(self.conviction, 4),
            "consensus": round(self.consensus, 4),
            "confidence_breakdown": {k: round(v, 4) for k, v in self.confidence_breakdown.items()},
            "bull_case": list(self.bull_case),
            "bear_case": list(self.bear_case),
            "invalidation": self.invalidation,
            "risk": {k: round(v, 4) for k, v in self.risk.items()},
            "position": {k: round(v, 4) for k, v in self.position.items()},
            "expected_holding": self.expected_holding,
            "alternatives": [
                {
                    "symbol": a.symbol,
                    "strategy": a.strategy,
                    "composite": round(a.composite, 2),
                    "rejection_reason": a.rejection_reason,
                }
                for a in self.alternatives
            ],
            "rationale": self.rationale,
            "vetoed": self.vetoed,
            "veto_reasons": list(self.veto_reasons),
        }


class ChiefInvestmentOfficer:
    """Aggregates agent reports into the final decision (deterministic)."""

    # Conviction thresholds for the recommendation ladder.
    STRONG = 0.6
    ACT = 0.35

    def decide(self, brief: CommitteeBrief, reports: list[AgentReport]) -> CommitteeDecision:
        by_role = {r.role: r for r in reports}
        sig = brief.opportunity.signal
        direction = sig.direction

        # Weighted signed vote → consensus in [-1, 1].
        total_w = 0.0
        weighted = 0.0
        breakdown: dict[str, float] = {}
        for report in reports:
            w = _ROLE_WEIGHTS.get(report.role, 1.0)
            contribution = report.stance.score * report.confidence * w
            breakdown[report.role.value] = contribution
            weighted += contribution
            total_w += w
        consensus = weighted / total_w if total_w else 0.0
        conviction = max(0.0, consensus)  # only positive consensus is conviction

        vetoes = [r for r in reports if r.veto]
        vetoed = bool(vetoes)

        # Recommendation ladder.
        if vetoed or consensus <= -self.ACT:
            rec = Recommendation.REJECT
        elif consensus >= self.STRONG:
            rec = (
                Recommendation.STRONG_BUY
                if direction is Direction.LONG
                else Recommendation.STRONG_SELL
            )
        elif consensus >= self.ACT:
            rec = Recommendation.BUY if direction is Direction.LONG else Recommendation.SELL
        else:
            rec = Recommendation.HOLD

        bull_case = _collect(reports, bull=True)
        bear_case = _collect(reports, bull=False)

        risk_report = by_role.get(AgentRole.RISK)
        pm_report = by_role.get(AgentRole.PORTFOLIO_MANAGER)
        position = _position(rec, pm_report, risk_report, sig, brief)
        risk = {
            "entry": sig.entry,
            "stop": sig.stop,
            "risk_reward": round(sig.risk_reward, 3),
            "stop_distance_pct": (
                round(sig.risk_per_unit / sig.entry * 100, 3) if sig.entry else 0.0
            ),
            "target_1": sig.targets[0] if sig.targets else 0.0,
        }
        alternatives = _alternatives(brief)
        rationale = _rationale(rec, consensus, conviction, vetoes, brief)

        return CommitteeDecision(
            symbol=brief.symbol,
            recommendation=rec,
            direction=direction,
            conviction=conviction,
            consensus=consensus,
            confidence_breakdown=breakdown,
            bull_case=bull_case,
            bear_case=bear_case,
            invalidation=brief.opportunity.explanation.invalidation,
            risk=risk,
            position=position,
            expected_holding=sig.expected_holding,
            alternatives=alternatives,
            rationale=rationale,
            vetoed=vetoed,
            veto_reasons=tuple(v.veto_reason or "risk veto" for v in vetoes),
        )


def _collect(reports: list[AgentReport], *, bull: bool) -> tuple[str, ...]:
    """Gather the strongest cited findings of one polarity across all agents."""
    picks: list[tuple[float, str]] = []
    for report in reports:
        findings: tuple[Finding, ...] = report.bull_findings if bull else report.bear_findings
        for f in findings:
            role = report.role.value.replace("_", " ").title()
            picks.append((f.weight, f"[{role}] {f.detail} ({f.citation})"))
    picks.sort(key=lambda p: p[0], reverse=True)
    return tuple(text for _w, text in picks[:6])


def _position(
    rec: Recommendation,
    pm: AgentReport | None,
    risk: AgentReport | None,
    sig: object,
    brief: CommitteeBrief,
) -> dict[str, float]:
    if rec is Recommendation.REJECT or pm is None:
        return {"quantity": 0.0, "risk_pct": 0.0, "notional": 0.0}
    qty = pm.metrics.get("recommended_qty", 0.0)
    risk_pct = pm.metrics.get("recommended_risk_pct", 0.0)
    notional = pm.metrics.get("recommended_notional", 0.0)
    # Risk Manager caps the PM's ask.
    if risk is not None:
        risk_pct = min(risk_pct, risk.metrics.get("max_risk_pct", risk_pct))
    return {"quantity": qty, "risk_pct": risk_pct, "notional": notional}


def _alternatives(brief: CommitteeBrief) -> tuple[Alternative, ...]:
    """Other ranked candidates and why they were not the pick."""
    chosen = brief.opportunity.symbol
    out: list[Alternative] = []
    for opp in brief.book.opportunities:
        if opp.symbol == chosen:
            continue
        reason = (
            f"Ranked #{opp.rank} with composite {opp.composite:.0f} vs. the selected "
            f"{brief.opportunity.composite:.0f} — lower committee priority."
        )
        out.append(
            Alternative(
                symbol=opp.symbol,
                strategy=opp.strategy_key,
                composite=opp.composite,
                rejection_reason=reason,
            )
        )
    return tuple(out[:5])


def _rationale(
    rec: Recommendation,
    consensus: float,
    conviction: float,
    vetoes: list[AgentReport],
    brief: CommitteeBrief,
) -> str:
    if vetoes:
        reasons = "; ".join(v.veto_reason or "risk veto" for v in vetoes)
        return (
            f"REJECT — hard veto: {reasons}. No single setup overrides a portfolio circuit breaker."
        )
    verb = {
        Recommendation.STRONG_BUY: "Strong buy",
        Recommendation.BUY: "Buy",
        Recommendation.STRONG_SELL: "Strong sell",
        Recommendation.SELL: "Sell",
        Recommendation.HOLD: "Stand aside (insufficient conviction)",
        Recommendation.REJECT: "Reject",
    }[rec]
    return (
        f"{verb} {brief.symbol} via {brief.opportunity.strategy_name}. Committee consensus "
        f"{consensus:+.2f} (conviction {conviction:.0%}) across 7 independent agents; the "
        f"decision cites the agents' findings above and inherits the regime "
        f"({brief.regime.primary.value})."
    )
