"""Static, real definitions backing the Admin dashboard.

These are not mock data — they describe the platform's actual RBAC design and
the committee's real default configuration. The committee defaults are derived
from the live CIO constants so this file cannot drift from the engine.
"""

from __future__ import annotations

from typing import Any

from app.modules.committee.agents import DEFAULT_AGENTS
from app.modules.committee.cio import DEFAULT_ROLE_WEIGHTS, ChiefInvestmentOfficer

# Role → capability matrix. Mirrors the require_role guards across the API:
# every mutating/privileged route is admin-only; the rest is available to any
# authenticated user.
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "user": [
        "view_dashboard",
        "view_market_data",
        "view_recommendations",
        "run_committee_review",
        "manage_own_paper_account",
        "view_own_journal_analytics",
        "edit_own_settings",
    ],
    "admin": [
        "view_dashboard",
        "view_market_data",
        "view_recommendations",
        "run_committee_review",
        "manage_own_paper_account",
        "view_own_journal_analytics",
        "edit_own_settings",
        "view_system_health",
        "manage_users",
        "configure_committee",
        "view_logs",
        "view_audit_trail",
    ],
}


def default_committee_config() -> dict[str, Any]:
    """The committee's built-in configuration, expressed as an editable document."""
    agents = []
    for cls in DEFAULT_AGENTS:
        role = cls.role.value
        agents.append(
            {
                "role": role,
                "name": cls.__name__,
                "enabled": True,
                "weight": round(DEFAULT_ROLE_WEIGHTS.get(cls.role, 1.0), 3),
            }
        )
    return {
        "agents": agents,
        "thresholds": {
            "strong": ChiefInvestmentOfficer.STRONG,
            "act": ChiefInvestmentOfficer.ACT,
        },
    }
