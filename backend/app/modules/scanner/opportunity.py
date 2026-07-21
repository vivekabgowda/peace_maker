"""Opportunity Book — ranking, Top-N and the NO-TRADE verdict (Sprint 3, Step 5).

The scanner emits one :class:`Opportunity` per surviving candidate. The book
ranks them by composite score (regime- and risk-weighted), exposes the Top-N, and
— crucially — issues a NO-TRADE verdict when the environment is hostile or nothing
clears the quality bar. The engine never forces trades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.modules.ai_engine.scoring import ScoreCard
from app.modules.scanner.regime import RegimeState
from app.modules.strategy.base import Direction, StrategySignal


@dataclass(frozen=True, slots=True)
class Explanation:
    """Structured answer to 'why this trade?' (Sprint 3, Step 6)."""

    why_this: tuple[str, ...]
    why_now: tuple[str, ...]
    biggest_risk: str
    invalidation: str
    confidence_breakdown: dict[str, float]

    def as_dict(self) -> dict[str, object]:
        return {
            "why_this": list(self.why_this),
            "why_now": list(self.why_now),
            "biggest_risk": self.biggest_risk,
            "invalidation": self.invalidation,
            "confidence_breakdown": self.confidence_breakdown,
        }


@dataclass(frozen=True, slots=True)
class Opportunity:
    """A ranked, scored, fully-explained trade candidate."""

    symbol: str
    instrument_id: int
    strategy_key: str
    strategy_name: str
    signal: StrategySignal
    scorecard: ScoreCard
    explanation: Explanation
    rank: int = 0

    @property
    def direction(self) -> Direction:
        return self.signal.direction

    @property
    def composite(self) -> float:
        return self.scorecard.composite

    def summary(self) -> dict[str, object]:
        sig = self.signal
        return {
            "rank": self.rank,
            "symbol": self.symbol,
            "strategy": self.strategy_key,
            "strategy_name": self.strategy_name,
            "direction": sig.direction.value,
            "entry": sig.entry,
            "stop": sig.stop,
            "targets": list(sig.targets),
            "risk_reward": round(sig.risk_reward, 2),
            "expected_holding": sig.expected_holding,
            "composite": self.composite,
            "confidence": self.scorecard.confidence,
            "scores": self.scorecard.as_dict(),
            "explanation": self.explanation.as_dict(),
            "tags": list(sig.tags),
        }


@dataclass(frozen=True, slots=True)
class OpportunityBook:
    """Ranked opportunities for one scan, with a NO-TRADE verdict when warranted."""

    generated_at: datetime
    regime: RegimeState
    opportunities: tuple[Opportunity, ...]
    universe_size: int
    no_trade: bool
    no_trade_reason: str | None = None
    rejected: int = 0
    scanned_strategies: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def top(self, n: int = 20) -> list[Opportunity]:
        return list(self.opportunities[:n])

    def as_dict(self, top_n: int = 20) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "regime": {
                "primary": self.regime.primary.value,
                "overlays": sorted(r.value for r in self.regime.overlays),
                "confidence": self.regime.confidence,
                "index_trend": self.regime.index_trend.value,
            },
            "no_trade": self.no_trade,
            "no_trade_reason": self.no_trade_reason,
            "universe_size": self.universe_size,
            "candidates": len(self.opportunities),
            "rejected": self.rejected,
            "top": [o.summary() for o in self.top(top_n)],
            "warnings": list(self.warnings),
        }


# Minimum composite an opportunity must clear to be shown. Below this the book
# prefers to say nothing rather than surface weak trades.
MIN_COMPOSITE = 55.0
# If the best composite is below this, the whole book is a NO-TRADE.
MIN_BEST_COMPOSITE = 60.0


def rank_opportunities(
    candidates: list[Opportunity],
    regime: RegimeState,
    *,
    universe_size: int,
    scanned_strategies: int,
    generated_at: datetime | None = None,
) -> OpportunityBook:
    """Sort, threshold, and decide NO-TRADE for a scan's candidates."""
    generated_at = generated_at or datetime.now(UTC)
    warnings: list[str] = []

    # Quality gate: drop sub-threshold candidates.
    qualified = [c for c in candidates if c.composite >= MIN_COMPOSITE]
    rejected = len(candidates) - len(qualified)
    qualified.sort(key=lambda o: o.composite, reverse=True)
    ranked = tuple(
        Opportunity(
            symbol=o.symbol,
            instrument_id=o.instrument_id,
            strategy_key=o.strategy_key,
            strategy_name=o.strategy_name,
            signal=o.signal,
            scorecard=o.scorecard,
            explanation=o.explanation,
            rank=i + 1,
        )
        for i, o in enumerate(qualified)
    )

    no_trade = False
    reason: str | None = None
    if regime.is_hostile:
        no_trade = True
        reason = (
            f"Hostile regime ({regime.primary.value} with "
            f"{sorted(r.value for r in regime.overlays)}); standing aside."
        )
    elif not ranked:
        no_trade = True
        reason = "No candidate cleared the quality bar."
    elif ranked[0].composite < MIN_BEST_COMPOSITE:
        no_trade = True
        reason = (
            f"Best composite {ranked[0].composite:.0f} below the "
            f"{MIN_BEST_COMPOSITE:.0f} conviction floor."
        )

    if regime.confidence < 0.4:
        warnings.append("Low regime confidence — size down and confirm.")

    # A NO-TRADE verdict shows no recommendations — standing aside means no book.
    shown = () if no_trade else ranked

    return OpportunityBook(
        generated_at=generated_at,
        regime=regime,
        opportunities=shown,
        universe_size=universe_size,
        no_trade=no_trade,
        no_trade_reason=reason,
        rejected=rejected,
        scanned_strategies=scanned_strategies,
        warnings=tuple(warnings),
    )
