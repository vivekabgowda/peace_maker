"""Options Analyst — Open Interest, PCR, IV, greeks, futures positioning."""

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


class OptionsAnalyst(Agent):
    role = AgentRole.OPTIONS

    def review(self, brief: CommitteeBrief) -> AgentReport:
        opt = brief.context.options
        sig = brief.opportunity.signal
        findings: list[Finding] = []

        if opt is None or opt.pcr is None:
            return self._report(
                stance=Stance.NEUTRAL,
                confidence=0.3,
                headline="No option-chain data for this underlying — abstaining.",
                findings=[self._note("options=none", "No PCR/OI/IV available for this name.")],
            )

        bull = bear = 0.0
        pcr = opt.pcr

        # PCR extremes are contrarian: high PCR (put-heavy fear) supports longs.
        if sig.direction is Direction.LONG:
            if pcr >= 1.3:
                findings.append(
                    self._bull(f"PCR={pcr:.2f}", "Put-heavy positioning — contrarian bullish.", 1.0)
                )
                bull += 1.0
            elif pcr <= 0.7:
                findings.append(
                    self._bear(f"PCR={pcr:.2f}", "Call-heavy/complacent — crowded longs.", 1.0)
                )
                bear += 1.0
        else:
            if pcr <= 0.7:
                findings.append(
                    self._bull(
                        f"PCR={pcr:.2f}", "Call-heavy positioning — contrarian bearish.", 1.0
                    )
                )
                bull += 1.0
            elif pcr >= 1.3:
                findings.append(
                    self._bear(f"PCR={pcr:.2f}", "Put-heavy — crowded shorts, squeeze risk.", 1.0)
                )
                bear += 1.0

        # Max-pain gravity relative to the entry.
        if opt.max_pain is not None and sig.entry:
            drift = (opt.max_pain - sig.entry) / sig.entry * 100
            if sig.direction is Direction.LONG and drift < -1.5:
                findings.append(
                    self._bear(
                        f"max_pain={opt.max_pain:.0f} ({drift:.1f}% below entry)",
                        "Max-pain gravity pulls below entry into expiry.",
                        0.8,
                    )
                )
                bear += 0.8
            elif sig.direction is Direction.LONG and drift > 1.5:
                findings.append(
                    self._bull(
                        f"max_pain={opt.max_pain:.0f} ({drift:.1f}% above entry)",
                        "Max-pain gravity supports upside into expiry.",
                        0.6,
                    )
                )
                bull += 0.6

        # OI skew (CE vs PE) as a positioning read.
        total = opt.total_ce_oi + opt.total_pe_oi
        if total > 0:
            pe_share = opt.total_pe_oi / total
            findings.append(
                self._note(
                    f"OI ce={opt.total_ce_oi:,} pe={opt.total_pe_oi:,}",
                    f"Put OI share {pe_share:.0%} — supports/absorbs at strikes below.",
                    0.4,
                )
            )

        # Implied volatility regime.
        if opt.iv_percentile is not None:
            if opt.iv_percentile >= 80:
                findings.append(
                    self._bear(
                        f"IV %ile={opt.iv_percentile:.0f}", "Rich IV — premium/whipsaw risk.", 0.7
                    )
                )
                bear += 0.7
            elif opt.iv_percentile <= 20:
                findings.append(
                    self._bull(
                        f"IV %ile={opt.iv_percentile:.0f}",
                        "Cheap IV — favorable for directional risk.",
                        0.5,
                    )
                )
                bull += 0.5

        stance = self._stance_from_balance(bull, bear)
        confidence = min(0.9, 0.4 + 0.15 * abs(bull - bear))
        verdict = "supports" if bull >= bear else "cautions on"
        headline = f"Options positioning (PCR {pcr:.2f}) {verdict} the trade."
        return self._report(
            stance=stance,
            confidence=confidence,
            headline=headline,
            findings=findings,
            metrics={"pcr": pcr},
        )
