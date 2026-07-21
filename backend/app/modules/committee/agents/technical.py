"""Technical Analyst — price action, multi-timeframe, indicators, chart structure."""

from __future__ import annotations

from app.modules.committee.base import Agent, AgentReport, AgentRole, CommitteeBrief, Finding
from app.modules.strategy.base import Direction


class TechnicalAnalyst(Agent):
    role = AgentRole.TECHNICAL

    def review(self, brief: CommitteeBrief) -> AgentReport:
        sig = brief.opportunity.signal
        card = brief.opportunity.scorecard
        ctx = brief.context
        findings: list[Finding] = []
        bull = bear = 0.0

        # The strategy setup itself (already validated) — cite its rationale.
        for r in sig.rationale[:3]:
            findings.append(self._bull(f"{brief.opportunity.strategy_key}", r, weight=0.8))
        bull += 0.8

        # Risk/reward geometry.
        rr = sig.risk_reward
        if rr >= 2.0:
            findings.append(
                self._bull(
                    f"risk_reward={rr:.1f}", "Clean ≥2:1 reward-to-risk to first target.", 1.2
                )
            )
            bull += 1.2
        elif rr < 1.2:
            findings.append(
                self._bear(f"risk_reward={rr:.1f}", "Sub-1.2:1 reward-to-risk — thin edge.", 1.0)
            )
            bear += 1.0

        # Multi-timeframe / indicator confirmation from the daily bundle.
        daily = ctx.tf("1d") or ctx.tf("5m")
        if daily is not None:
            rsi = daily.ind("rsi_14")
            adx = daily.ind("adx_14")
            e21, e50 = daily.ind("ema_21"), daily.ind("ema_50")
            if adx is not None and adx >= 25:
                findings.append(self._bull(f"ADX(14)={adx:.0f}", "Trending tape (ADX≥25).", 0.8))
                bull += 0.8
            if rsi is not None:
                if sig.direction is Direction.LONG and rsi >= 75:
                    findings.append(
                        self._bear(
                            f"RSI(14)={rsi:.0f}", "Overbought — chase risk into strength.", 1.0
                        )
                    )
                    bear += 1.0
                elif sig.direction is Direction.LONG and 50 <= rsi < 70:
                    findings.append(
                        self._bull(f"RSI(14)={rsi:.0f}", "Momentum positive, not overbought.", 0.6)
                    )
                    bull += 0.6
            if e21 is not None and e50 is not None:
                stacked_up = e21 > e50
                if (sig.direction is Direction.LONG) == stacked_up:
                    findings.append(
                        self._bull(
                            f"EMA21{'>' if stacked_up else '<'}EMA50",
                            "Moving-average structure confirms the direction.",
                            0.7,
                        )
                    )
                    bull += 0.7
                else:
                    findings.append(
                        self._bear(
                            f"EMA21{'>' if stacked_up else '<'}EMA50",
                            "Moving-average structure disagrees with the direction.",
                            0.8,
                        )
                    )
                    bear += 0.8

        # Composite technical/volume scores from the scoring engine.
        if card.technical >= 65:
            bull += 0.4
        if card.volume >= 65:
            findings.append(
                self._bull(
                    f"volume_score={card.volume:.0f}", "Volume expanding into the signal.", 0.6
                )
            )
            bull += 0.6
        elif card.volume < 45:
            findings.append(
                self._bear(
                    f"volume_score={card.volume:.0f}", "Weak participation on the move.", 0.6
                )
            )
            bear += 0.6

        stance = self._stance_from_balance(bull, bear)
        confidence = min(0.95, 0.45 + 0.12 * abs(bull - bear))
        verdict = "supports" if bull >= bear else "questions"
        headline = f"Technical structure {verdict} the setup (RR {rr:.1f})."
        return self._report(
            stance=stance, confidence=confidence, headline=headline, findings=findings
        )
