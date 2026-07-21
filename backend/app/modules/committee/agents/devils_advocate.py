"""Devil's Advocate — actively find reasons NOT to take the trade.

Its job is to invalidate the bullish thesis. It only ever produces bear findings
or neutral notes, and it never supports; the strongest it gets is NEUTRAL when it
genuinely cannot find a hole. This deliberate asymmetry is a bias check on the
rest of the committee.
"""

from __future__ import annotations

from app.modules.committee.base import (
    Agent,
    AgentReport,
    AgentRole,
    CommitteeBrief,
    Finding,
    Stance,
)
from app.modules.strategy.base import Direction


class DevilsAdvocate(Agent):
    role = AgentRole.DEVILS_ADVOCATE

    def review(self, brief: CommitteeBrief) -> AgentReport:
        sig = brief.opportunity.signal
        card = brief.opportunity.scorecard
        ctx = brief.context
        regime = brief.regime
        objections: list[Finding] = []

        # 1) Fighting the tape.
        counter = (sig.direction is Direction.LONG and regime.index_trend is Direction.SHORT) or (
            sig.direction is Direction.SHORT and regime.index_trend is Direction.LONG
        )
        if counter:
            objections.append(
                self._bear(
                    f"index_trend={regime.index_trend.value} vs {sig.direction.value}",
                    "The trade fights the index — most such trades fail.",
                    1.5,
                )
            )

        # 2) Extension / chase risk.
        daily = ctx.tf("1d") or ctx.tf("5m")
        rsi = daily.ind("rsi_14") if daily else None
        if rsi is not None and sig.direction is Direction.LONG and rsi >= 72:
            objections.append(
                self._bear(
                    f"RSI(14)={rsi:.0f}", "Buying an overbought reading — poor entry location.", 1.0
                )
            )
        if rsi is not None and sig.direction is Direction.SHORT and rsi <= 28:
            objections.append(
                self._bear(f"RSI(14)={rsi:.0f}", "Shorting an oversold reading — bounce risk.", 1.0)
            )

        # 3) Thin liquidity.
        if card.liquidity < 50:
            objections.append(
                self._bear(
                    f"liquidity_score={card.liquidity:.0f}",
                    "Thin liquidity — slippage and gap risk.",
                    1.0,
                )
            )

        # 4) Marginal edge.
        if sig.risk_reward < 1.5:
            objections.append(
                self._bear(
                    f"risk_reward={sig.risk_reward:.1f}",
                    "Reward barely exceeds risk — no margin for error.",
                    0.8,
                )
            )
        if card.composite < 62:
            objections.append(
                self._bear(
                    f"composite={card.composite:.0f}",
                    "Composite is only marginally above the bar.",
                    0.7,
                )
            )

        # 5) Event / regime hazard.
        if regime.overlays:
            objections.append(
                self._bear(
                    f"overlays={sorted(o.value for o in regime.overlays)}",
                    "Active event/volatility overlays raise the odds of a whipsaw.",
                    0.6,
                )
            )

        # 6) Weak participation.
        if card.volume < 45:
            objections.append(
                self._bear(
                    f"volume_score={card.volume:.0f}", "Move lacks volume confirmation.", 0.7
                )
            )

        total_weight = sum(o.weight for o in objections)
        if not objections:
            return self._report(
                stance=Stance.NEUTRAL,
                confidence=0.5,
                headline="Could not invalidate the thesis — no material objection found.",
                findings=[
                    self._note("no_objection", "Setup withstands scrutiny on the available data.")
                ],
            )
        stance = Stance.OPPOSE if total_weight >= 2.5 else Stance.CONCERN
        confidence = min(0.9, 0.5 + 0.1 * len(objections))
        headline = f"{len(objections)} objection(s) to the bull thesis (weight {total_weight:.1f})."
        return self._report(
            stance=stance,
            confidence=confidence,
            headline=headline,
            findings=objections,
            metrics={"objection_weight": total_weight, "objection_count": float(len(objections))},
        )
