"""AI Investment Committee — agent contracts (Sprint 4).

A recommendation is NEVER issued by a single analyzer. Seven independent agents
review the same :class:`CommitteeBrief` from different perspectives and each emit
a structured :class:`AgentReport`. The CIO then synthesizes a final decision.

**No black box.** Every agent is a deterministic rule engine that emits
:class:`Finding` objects citing the exact rule, indicator, or condition behind
each judgement — so the whole recommendation is explainable end to end. The
:class:`Agent` interface is intentionally narrow (``review(brief) -> report``) so
any single agent can later be swapped for an LLM-backed analyst without changing
the CIO, the orchestrator, or the API.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from app.modules.scanner.opportunity import Opportunity, OpportunityBook
from app.modules.scanner.regime import RegimeState
from app.modules.strategy.base import StrategyContext


class AgentRole(StrEnum):
    STRATEGIST = "chief_market_strategist"
    TECHNICAL = "technical_analyst"
    OPTIONS = "options_analyst"
    NEWS = "news_analyst"
    RISK = "risk_manager"
    DEVILS_ADVOCATE = "devils_advocate"
    PORTFOLIO_MANAGER = "portfolio_manager"


class Stance(StrEnum):
    """An agent's directional judgement on the proposed trade."""

    STRONG_SUPPORT = "strong_support"
    SUPPORT = "support"
    NEUTRAL = "neutral"
    CONCERN = "concern"
    OPPOSE = "oppose"

    @property
    def score(self) -> float:
        """Map to a signed weight in [-1, 1] for the CIO's weighted vote."""
        return {
            Stance.STRONG_SUPPORT: 1.0,
            Stance.SUPPORT: 0.5,
            Stance.NEUTRAL: 0.0,
            Stance.CONCERN: -0.5,
            Stance.OPPOSE: -1.0,
        }[self]


class Polarity(StrEnum):
    BULL = "bull"
    BEAR = "bear"
    NEUTRAL = "neutral"


@dataclass(frozen=True, slots=True)
class Finding:
    """One cited observation. The citation is what makes the system explainable."""

    polarity: Polarity
    citation: str  # the exact rule/indicator/condition, e.g. "RSI(14)=62 in thrust band"
    detail: str  # human-readable interpretation
    weight: float = 1.0  # relative importance within the agent's report

    def as_dict(self) -> dict[str, object]:
        return {
            "polarity": self.polarity.value,
            "citation": self.citation,
            "detail": self.detail,
            "weight": round(self.weight, 3),
        }


@dataclass(frozen=True, slots=True)
class AgentReport:
    """One agent's perspective on the trade."""

    role: AgentRole
    stance: Stance
    confidence: float  # 0..1, the agent's certainty in its own stance
    headline: str
    findings: tuple[Finding, ...]
    veto: bool = False  # a hard objection the CIO must not override
    veto_reason: str | None = None
    metrics: Mapping[str, float] = field(default_factory=dict)  # structured numeric outputs

    @property
    def bull_findings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.polarity is Polarity.BULL)

    @property
    def bear_findings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.polarity is Polarity.BEAR)

    def as_dict(self) -> dict[str, object]:
        return {
            "role": self.role.value,
            "stance": self.stance.value,
            "confidence": round(self.confidence, 4),
            "headline": self.headline,
            "veto": self.veto,
            "veto_reason": self.veto_reason,
            "findings": [f.as_dict() for f in self.findings],
            "metrics": {k: round(v, 4) for k, v in self.metrics.items()},
        }


@dataclass(frozen=True, slots=True)
class Position:
    """An open position in the book (for correlation/heat/allocation reasoning)."""

    symbol: str
    sector: str | None
    direction: str  # "long" | "short"
    risk_pct: float  # capital at risk on this position (% of equity)
    unrealized_pct: float = 0.0


@dataclass(frozen=True, slots=True)
class PortfolioState:
    """The book the committee must keep coherent (advisory inputs)."""

    equity: float = 1_000_000.0
    open_positions: tuple[Position, ...] = ()
    portfolio_heat_pct: float = 0.0  # total capital at risk across open positions
    current_drawdown_pct: float = 0.0  # peak-to-trough on equity (>=0)
    daily_loss_pct: float = 0.0  # today's realized loss (>=0)
    max_portfolio_heat_pct: float = 6.0
    max_drawdown_pct: float = 12.0
    max_daily_loss_pct: float = 3.0
    per_trade_risk_pct: float = 1.0

    def sector_exposure(self, sector: str | None) -> int:
        if sector is None:
            return 0
        return sum(1 for p in self.open_positions if p.sector == sector)


@dataclass(frozen=True, slots=True)
class CommitteeBrief:
    """The packet every agent reviews — one opportunity in full context."""

    opportunity: Opportunity
    context: StrategyContext
    regime: RegimeState
    book: OpportunityBook  # the full ranked book (for alternatives/rejections)
    portfolio: PortfolioState = field(default_factory=PortfolioState)

    @property
    def symbol(self) -> str:
        return self.opportunity.symbol


class Agent(ABC):
    """Base class for committee agents. Deterministic and side-effect-free."""

    role: AgentRole

    @abstractmethod
    def review(self, brief: CommitteeBrief) -> AgentReport:
        """Analyze the brief from this agent's perspective. Pure; no I/O."""

    # -- helpers for subclasses --------------------------------------------
    def _report(
        self,
        *,
        stance: Stance,
        confidence: float,
        headline: str,
        findings: list[Finding],
        veto: bool = False,
        veto_reason: str | None = None,
        metrics: Mapping[str, float] | None = None,
    ) -> AgentReport:
        return AgentReport(
            role=self.role,
            stance=stance,
            confidence=max(0.0, min(1.0, confidence)),
            headline=headline,
            findings=tuple(findings),
            veto=veto,
            veto_reason=veto_reason,
            metrics=dict(metrics or {}),
        )

    @staticmethod
    def _bull(citation: str, detail: str, weight: float = 1.0) -> Finding:
        return Finding(Polarity.BULL, citation, detail, weight)

    @staticmethod
    def _bear(citation: str, detail: str, weight: float = 1.0) -> Finding:
        return Finding(Polarity.BEAR, citation, detail, weight)

    @staticmethod
    def _note(citation: str, detail: str, weight: float = 1.0) -> Finding:
        return Finding(Polarity.NEUTRAL, citation, detail, weight)

    @staticmethod
    def _stance_from_balance(bull: float, bear: float) -> Stance:
        """Derive a stance from weighted bull vs. bear evidence."""
        net = bull - bear
        if net >= 1.5:
            return Stance.STRONG_SUPPORT
        if net >= 0.5:
            return Stance.SUPPORT
        if net <= -1.5:
            return Stance.OPPOSE
        if net <= -0.5:
            return Stance.CONCERN
        return Stance.NEUTRAL
