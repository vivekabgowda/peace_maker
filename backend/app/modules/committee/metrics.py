"""Prometheus metrics for the AI Investment Committee (Sprint 4 observability).

Exposed on the app's existing ``/metrics`` endpoint. Covers per-agent latency,
stance distribution, vetoes, and the final recommendation mix.
"""

from __future__ import annotations

from prometheus_client import Counter, Histogram

AGENT_LATENCY = Histogram(
    "bkn_committee_agent_seconds",
    "Time for one agent to review one brief",
    ["role"],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
)
DELIBERATION_LATENCY = Histogram(
    "bkn_committee_deliberation_seconds",
    "Time for the full committee (7 agents + CIO) to reach a decision",
    buckets=(0.0005, 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25),
)
AGENT_STANCE = Counter(
    "bkn_committee_agent_stance_total",
    "Agent stances emitted",
    ["role", "stance"],
)
AGENT_VETOES = Counter("bkn_committee_vetoes_total", "Hard vetoes raised by agents", ["role"])
DECISIONS = Counter(
    "bkn_committee_decisions_total",
    "Final CIO recommendations",
    ["recommendation"],
)
