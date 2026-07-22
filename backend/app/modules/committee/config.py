"""Build an :class:`InvestmentCommittee` from operator configuration (Sprint 12).

The Admin dashboard persists a committee config document; this turns it into a
live committee — disabling agents, overriding role weights, and adjusting the
CIO conviction thresholds. A ``None`` config reproduces the built-in defaults.
"""

from __future__ import annotations

from typing import Any

from app.modules.committee.agents import DEFAULT_AGENTS
from app.modules.committee.base import Agent, AgentRole
from app.modules.committee.cio import DEFAULT_ROLE_WEIGHTS, ChiefInvestmentOfficer
from app.modules.committee.committee import InvestmentCommittee

_ROLE_BY_VALUE = {role.value: role for role in AgentRole}


def build_committee_from_config(config: dict[str, Any] | None) -> InvestmentCommittee:
    if not config:
        return InvestmentCommittee()

    agent_entries = config.get("agents") or []
    by_role: dict[str, dict[str, Any]] = {}
    for entry in agent_entries:
        role = entry.get("role")
        if isinstance(role, str):
            by_role[role] = entry

    enabled_agents: list[Agent] = []
    role_weights: dict[AgentRole, float] = dict(DEFAULT_ROLE_WEIGHTS)
    for cls in DEFAULT_AGENTS:
        role_value = cls.role.value
        entry = by_role.get(role_value, {})
        if entry.get("enabled", True):
            enabled_agents.append(cls())
        weight = entry.get("weight")
        if isinstance(weight, int | float):
            role_weights[cls.role] = float(weight)

    thresholds = config.get("thresholds") or {}
    strong = thresholds.get("strong")
    act = thresholds.get("act")

    cio = ChiefInvestmentOfficer(
        role_weights=role_weights,
        strong=float(strong) if isinstance(strong, int | float) else None,
        act=float(act) if isinstance(act, int | float) else None,
    )
    return InvestmentCommittee(agents=enabled_agents, cio=cio)
