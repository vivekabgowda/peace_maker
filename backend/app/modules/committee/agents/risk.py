"""Risk Manager — position sizing, correlation, portfolio heat, drawdown limits.

Holds a hard veto: if a portfolio-level risk limit is breached, no single trade,
however attractive, may be taken. This is the committee's circuit breaker.
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


class RiskManager(Agent):
    role = AgentRole.RISK

    def review(self, brief: CommitteeBrief) -> AgentReport:
        pf = brief.portfolio
        sig = brief.opportunity.signal
        ctx = brief.context
        findings: list[Finding] = []

        # -- Hard vetoes (portfolio circuit breakers) --------------------------
        if pf.current_drawdown_pct >= pf.max_drawdown_pct:
            return self._veto(
                f"drawdown={pf.current_drawdown_pct:.1f}% ≥ max {pf.max_drawdown_pct:.1f}%",
                "Portfolio in max drawdown — halt new risk until recovery.",
            )
        if pf.daily_loss_pct >= pf.max_daily_loss_pct:
            return self._veto(
                f"daily_loss={pf.daily_loss_pct:.1f}% ≥ max {pf.max_daily_loss_pct:.1f}%",
                "Daily loss limit hit — stop trading for the day.",
            )
        if pf.portfolio_heat_pct + pf.per_trade_risk_pct > pf.max_portfolio_heat_pct:
            return self._veto(
                f"heat={pf.portfolio_heat_pct:.1f}%+{pf.per_trade_risk_pct:.1f}% > "
                f"max {pf.max_portfolio_heat_pct:.1f}%",
                "No heat budget left for another position.",
            )

        bull = bear = 0.0

        # Stop distance sanity.
        risk_pct = sig.risk_per_unit / sig.entry * 100 if sig.entry else 100.0
        if risk_pct > 6.0:
            findings.append(
                self._bear(
                    f"stop_distance={risk_pct:.1f}%",
                    "Stop wider than 6% — expensive risk unit.",
                    1.2,
                )
            )
            bear += 1.2
        elif risk_pct <= 3.0:
            findings.append(
                self._bull(f"stop_distance={risk_pct:.1f}%", "Tight, well-defined stop.", 0.6)
            )
            bull += 0.6

        # Reward-to-risk.
        if sig.risk_reward >= 2.0:
            bull += 0.6
        elif sig.risk_reward < 1.5:
            findings.append(
                self._bear(
                    f"risk_reward={sig.risk_reward:.1f}", "Reward-to-risk below the 1.5 floor.", 0.8
                )
            )
            bear += 0.8

        # Correlation with existing book (same sector, same direction).
        same_sector = pf.sector_exposure(ctx.sector)
        if same_sector >= 2:
            findings.append(
                self._bear(
                    f"sector_exposure({ctx.sector})={same_sector}",
                    "Already concentrated in this sector — correlated risk.",
                    1.0,
                )
            )
            bear += 1.0

        # Heat headroom.
        headroom = pf.max_portfolio_heat_pct - pf.portfolio_heat_pct
        findings.append(
            self._note(
                f"heat={pf.portfolio_heat_pct:.1f}% / max {pf.max_portfolio_heat_pct:.1f}%",
                f"{headroom:.1f}% risk budget remaining.",
                0.3,
            )
        )

        # Recommended risk sizing scaled by conviction (composite/confidence).
        conviction = brief.opportunity.scorecard.confidence
        rec_risk_pct = round(
            min(pf.per_trade_risk_pct, pf.per_trade_risk_pct * (0.5 + conviction)), 3
        )

        stance = self._stance_from_balance(bull, bear)
        confidence = min(0.9, 0.5 + 0.12 * abs(bull - bear))
        headline = (
            f"Risk acceptable: {risk_pct:.1f}% stop, RR {sig.risk_reward:.1f}, "
            f"{headroom:.1f}% heat headroom."
            if stance in (Stance.SUPPORT, Stance.STRONG_SUPPORT, Stance.NEUTRAL)
            else f"Risk concerns: {risk_pct:.1f}% stop, RR {sig.risk_reward:.1f}."
        )
        return self._report(
            stance=stance,
            confidence=confidence,
            headline=headline,
            findings=findings,
            metrics={
                "max_risk_pct": pf.per_trade_risk_pct,
                "recommended_risk_pct": rec_risk_pct,
                "stop_distance_pct": round(risk_pct, 3),
                "heat_headroom_pct": round(headroom, 3),
            },
        )

    def _veto(self, citation: str, detail: str) -> AgentReport:
        return self._report(
            stance=Stance.OPPOSE,
            confidence=1.0,
            headline=f"VETO — {detail}",
            findings=[self._bear(citation, detail, weight=3.0)],
            veto=True,
            veto_reason=detail,
            metrics={"recommended_risk_pct": 0.0},
        )
