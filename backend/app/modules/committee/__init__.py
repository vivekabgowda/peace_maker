"""AI Investment Committee subsystem (Sprint 4).

A recommendation is never issued by a single analyzer: seven independent agents
review each opportunity and the CIO synthesizes a fully-explainable decision.
"""

from __future__ import annotations

from app.modules.committee.base import (
    Agent,
    AgentReport,
    AgentRole,
    CommitteeBrief,
    Finding,
    PortfolioState,
    Position,
    Stance,
)
from app.modules.committee.cio import (
    ChiefInvestmentOfficer,
    CommitteeDecision,
    Recommendation,
)
from app.modules.committee.committee import Deliberation, InvestmentCommittee

__all__ = [
    "Agent",
    "AgentReport",
    "AgentRole",
    "ChiefInvestmentOfficer",
    "CommitteeBrief",
    "CommitteeDecision",
    "Deliberation",
    "Finding",
    "InvestmentCommittee",
    "PortfolioState",
    "Position",
    "Recommendation",
    "Stance",
]
