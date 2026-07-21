"""Portfolio Manager — allocate capital? how much? reduce another position?"""

from __future__ import annotations

from app.modules.committee.base import (
    Agent,
    AgentReport,
    AgentRole,
    CommitteeBrief,
    Finding,
    Position,
    Stance,
)
from app.modules.strategy.base import Direction


class PortfolioManager(Agent):
    role = AgentRole.PORTFOLIO_MANAGER

    def review(self, brief: CommitteeBrief) -> AgentReport:
        pf = brief.portfolio
        sig = brief.opportunity.signal
        ctx = brief.context
        card = brief.opportunity.scorecard
        findings: list[Finding] = []

        headroom = pf.max_portfolio_heat_pct - pf.portfolio_heat_pct
        can_allocate = headroom >= pf.per_trade_risk_pct * 0.5 and sig.risk_per_unit > 0

        # Size scaled by conviction, capped by heat headroom.
        conviction = card.confidence
        target_risk_pct = min(pf.per_trade_risk_pct * (0.5 + conviction), headroom)
        target_risk_pct = max(0.0, round(target_risk_pct, 3))
        risk_capital = pf.equity * target_risk_pct / 100.0
        qty = int(risk_capital / sig.risk_per_unit) if sig.risk_per_unit > 0 else 0
        notional = qty * sig.entry

        if not can_allocate or qty <= 0:
            findings.append(
                self._bear(
                    f"heat_headroom={headroom:.1f}%",
                    "Insufficient risk budget to open a meaningful position.",
                    1.5,
                )
            )
            return self._report(
                stance=Stance.OPPOSE,
                confidence=0.7,
                headline="No capital to allocate — book is at its risk budget.",
                findings=findings,
                metrics={"recommended_qty": 0.0, "recommended_risk_pct": 0.0},
            )

        findings.append(
            self._bull(
                f"size={qty}@{sig.entry:.2f} (~{target_risk_pct:.2f}% risk)",
                f"Allocate ~₹{notional:,.0f} notional at {target_risk_pct:.2f}% portfolio risk.",
                1.0,
            )
        )

        # Correlation: suggest trimming a same-sector, weaker or losing position.
        reduce: Position | None = _reduce_candidate(pf, ctx.sector, sig.direction)
        if reduce is not None:
            findings.append(
                self._note(
                    f"reduce={reduce.symbol}",
                    f"Consider trimming {reduce.symbol} ({reduce.sector}, "
                    f"{reduce.unrealized_pct:+.1f}%) to make room and cut correlation.",
                    0.6,
                )
            )

        # Conviction gate on committing capital.
        if conviction >= 0.6:
            findings.append(
                self._bull(
                    f"conviction={conviction:.0%}",
                    "High conviction justifies a full-size clip.",
                    0.6,
                )
            )
            stance = (
                Stance.STRONG_SUPPORT
                if target_risk_pct >= pf.per_trade_risk_pct
                else Stance.SUPPORT
            )
        else:
            findings.append(
                self._note(f"conviction={conviction:.0%}", "Moderate conviction — half-size clip.")
            )
            stance = Stance.SUPPORT

        headline = f"Allocate {qty} sh (~₹{notional:,.0f}, {target_risk_pct:.2f}% risk)" + (
            f"; trim {reduce.symbol}." if reduce else "."
        )
        return self._report(
            stance=stance,
            confidence=min(0.9, 0.55 + conviction * 0.3),
            headline=headline,
            findings=findings,
            metrics={
                "recommended_qty": float(qty),
                "recommended_notional": round(notional, 2),
                "recommended_risk_pct": target_risk_pct,
            },
        )


def _reduce_candidate(pf: object, sector: str | None, direction: Direction) -> Position | None:
    from app.modules.committee.base import PortfolioState

    assert isinstance(pf, PortfolioState)
    if sector is None:
        return None
    same = [p for p in pf.open_positions if p.sector == sector and p.direction == direction.value]
    if not same:
        return None
    # Trim the weakest (most negative unrealized) same-sector position.
    return min(same, key=lambda p: p.unrealized_pct)
