"""News Analyst — institutional news intelligence in the committee (Sprint 11).

When the standardized :class:`NewsAssessment` is attached to the brief (produced
by the single shared News Intelligence engine), this agent votes on that rich,
verified, session-aware signal — reliability and corroboration flow straight into
its *confidence*, so the CIO weights trustworthy news more heavily while news
still only *influences* rather than overrides the technical read. Without an
assessment it falls back to the legacy aggregate ``news_score``.
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
        if brief.news_assessment is not None:
            return self._review_assessment(brief)
        return self._review_legacy(brief)

    # -- Sprint 11: rich, standardized assessment --------------------------
    def _review_assessment(self, brief: CommitteeBrief) -> AgentReport:
        a = brief.news_assessment
        assert a is not None
        long = brief.opportunity.signal.direction is Direction.LONG
        directional = a.signed_unit if long else -a.signed_unit

        findings: list[Finding] = []
        for ev in a.events[:4]:
            if abs(ev.polarity) < 0.15:
                continue
            supportive = (ev.polarity > 0) == long
            cite = f"{ev.event.value}@{ev.source}({ev.reliability})"
            detail = f"{ev.headline} — {ev.impact_timing.label.lower()}."
            findings.append(
                self._bull(cite, detail, ev.reliability / 100.0)
                if supportive
                else self._bear(cite, detail, ev.reliability / 100.0)
            )
        for risk in a.risk_factors:
            findings.append(self._note("news_risk", risk, 0.5))
        if not findings:
            findings.append(
                self._note("news=quiet", "No decisive, trusted news events for the name.")
            )

        # Stance from the directional, reliability-weighted score.
        if directional >= 0.35:
            stance = Stance.STRONG_SUPPORT if directional >= 0.6 else Stance.SUPPORT
        elif directional <= -0.35:
            stance = Stance.OPPOSE if directional <= -0.6 else Stance.CONCERN
        else:
            stance = Stance.NEUTRAL

        headline = (
            f"News {a.sentiment.value.replace('_', ' ')} "
            f"(score {a.news_score:+d}, {a.verification_status.value}, "
            f"reliability {a.source_reliability}/100) — {a.impact_horizon.label}."
        )
        return self._report(
            stance=stance,
            confidence=a.confidence,  # already blends reliability + verification + session
            headline=headline,
            findings=findings,
            metrics={
                "news_score": float(a.news_score),
                "source_reliability": float(a.source_reliability),
                "article_count": float(a.article_count),
            },
        )

    # -- Legacy fallback (pre-Sprint 11 aggregate score) -------------------
    def _review_legacy(self, brief: CommitteeBrief) -> AgentReport:
        ctx = brief.context
        sig = brief.opportunity.signal
        findings: list[Finding] = []
        bull = bear = 0.0

        score = ctx.news_score
        if score is None:
            findings.append(self._note("news=none", "No material news flow for this name."))
        else:
            directional = score if sig.direction is Direction.LONG else -score
            if directional >= 0.3:
                findings.append(
                    self._bull(f"news_score={score:+.2f}", "News flow supports the trade.", 1.0)
                )
                bull += 1.0
            elif directional <= -0.3:
                findings.append(
                    self._bear(
                        f"news_score={score:+.2f}", "News flow leans against the trade.", 1.2
                    )
                )
                bear += 1.2
            else:
                findings.append(
                    self._note(f"news_score={score:+.2f}", "News flow is broadly neutral.")
                )

        event_hits = [name for reg, name in _EVENT_REGIMES.items() if reg in brief.regime.regimes]
        for name in event_hits:
            findings.append(self._bear(f"calendar={name}", f"{name} today — headline risk.", 0.6))
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
