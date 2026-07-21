"""News Analyst — earnings, corporate actions, sentiment, economic calendar."""

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
from app.modules.strategy.regime_types import MarketRegime

_EVENT_REGIMES = {
    MarketRegime.RBI_DAY: "RBI policy decision",
    MarketRegime.BUDGET_DAY: "Union Budget",
    MarketRegime.ELECTION_EVENT: "election event window",
    MarketRegime.EXPIRY_DAY: "F&O expiry",
}


class NewsAnalyst(Agent):
    role = AgentRole.NEWS

    def review(self, brief: CommitteeBrief) -> AgentReport:
        ctx = brief.context
        sig = brief.opportunity.signal
        findings: list[Finding] = []
        bull = bear = 0.0

        # Aggregated sentiment*impact score in [-1, 1].
        score = ctx.news_score
        if score is None:
            findings.append(self._note("news=none", "No material news flow for this name."))
        else:
            directional = score if sig.direction is Direction.LONG else -score
            if directional >= 0.3:
                findings.append(
                    self._bull(
                        f"news_score={score:+.2f}", "News flow supports the trade direction.", 1.0
                    )
                )
                bull += 1.0
            elif directional <= -0.3:
                findings.append(
                    self._bear(
                        f"news_score={score:+.2f}",
                        "News flow leans against the trade direction.",
                        1.2,
                    )
                )
                bear += 1.2
            else:
                findings.append(
                    self._note(f"news_score={score:+.2f}", "News flow is broadly neutral.")
                )

        # Economic / event calendar from the regime overlays.
        event_hits = [name for reg, name in _EVENT_REGIMES.items() if reg in brief.regime.regimes]
        for name in event_hits:
            findings.append(
                self._bear(
                    f"calendar={name}",
                    f"{name} today — headline risk can override technicals.",
                    0.6,
                )
            )
            bear += 0.6

        stance = self._stance_from_balance(bull, bear)
        confidence = (
            0.35 if score is None and not event_hits else min(0.85, 0.45 + 0.15 * abs(bull - bear))
        )
        if score is None and not event_hits:
            stance = Stance.NEUTRAL
        headline = "Clear news calendar; sentiment " + (
            "supportive." if bull > bear else "cautious." if bear > bull else "neutral."
        )
        return self._report(
            stance=stance, confidence=confidence, headline=headline, findings=findings
        )
