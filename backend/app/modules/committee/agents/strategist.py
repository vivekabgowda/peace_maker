"""Chief Market Strategist — regime, macro, index trend, sector rotation."""

from __future__ import annotations

from app.modules.committee.base import Agent, AgentReport, AgentRole, CommitteeBrief, Finding
from app.modules.strategy.base import Direction
from app.modules.strategy.regime_types import HOSTILE_REGIMES, OVERLAY_REGIMES


class ChiefMarketStrategist(Agent):
    role = AgentRole.STRATEGIST

    def review(self, brief: CommitteeBrief) -> AgentReport:
        regime = brief.regime
        sig = brief.opportunity.signal
        findings: list[Finding] = []
        bull = bear = 0.0

        # Regime alignment.
        aligned = (sig.direction is Direction.LONG and regime.index_trend is Direction.LONG) or (
            sig.direction is Direction.SHORT and regime.index_trend is Direction.SHORT
        )
        if regime.is_hostile:
            findings.append(
                self._bear(
                    f"regime={regime.primary.value}+{sorted(r.value for r in regime.overlays)}",
                    "Hostile regime — broad risk-off overwhelms single-name setups.",
                    weight=2.0,
                )
            )
            bear += 2.0
        elif aligned:
            findings.append(
                self._bull(
                    f"index_trend={regime.index_trend.value}, regime={regime.primary.value}",
                    "Trade is aligned with the prevailing index trend and regime.",
                    weight=1.5,
                )
            )
            bull += 1.5
        elif regime.index_trend is not Direction.NONE:
            findings.append(
                self._bear(
                    f"index_trend={regime.index_trend.value} vs signal={sig.direction.value}",
                    "Trade fights the index trend — lower base rate.",
                    weight=1.0,
                )
            )
            bear += 1.0

        # Regime conviction.
        if regime.confidence >= 0.6:
            findings.append(
                self._bull(
                    f"regime_confidence={regime.confidence:.0%}",
                    "Regime classification is high-confidence.",
                    weight=0.5,
                )
            )
            bull += 0.5
        elif regime.confidence < 0.4:
            findings.append(
                self._note(
                    f"regime_confidence={regime.confidence:.0%}",
                    "Regime is ambiguous — size conservatively.",
                )
            )

        # Macro / event overlays.
        events = regime.overlays & OVERLAY_REGIMES - HOSTILE_REGIMES
        for ev in sorted(events, key=lambda e: e.value):
            findings.append(
                self._note(
                    f"overlay={ev.value}",
                    f"Event overlay active: {ev.value.replace('_', ' ')} — expect elevated noise.",
                    weight=0.4,
                )
            )
            bear += 0.2

        # Sector rotation (relative strength vs. index is the rotation proxy).
        rs = brief.context.relative_strength
        if rs is not None:
            if rs >= 2.0 and sig.direction is Direction.LONG:
                findings.append(
                    self._bull(
                        f"relative_strength=+{rs:.1f}% vs index",
                        "Name is a rotation leader — money is flowing into it.",
                        weight=1.0,
                    )
                )
                bull += 1.0
            elif rs <= -2.0 and sig.direction is Direction.LONG:
                findings.append(
                    self._bear(
                        f"relative_strength={rs:.1f}% vs index",
                        "Name is a laggard while going long — rotation is against it.",
                        weight=1.0,
                    )
                )
                bear += 1.0

        stance = self._stance_from_balance(bull, bear)
        confidence = min(0.95, 0.4 + 0.15 * abs(bull - bear) + 0.2 * regime.confidence)
        headline = (
            f"{regime.primary.value.replace('_', ' ').title()} regime, "
            f"index {regime.index_trend.value}; trade is "
            f"{'aligned' if aligned and not regime.is_hostile else 'not aligned'}."
        )
        return self._report(
            stance=stance, confidence=confidence, headline=headline, findings=findings
        )
