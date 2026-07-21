"""Explainability layer (Sprint 3, Step 6).

Turns a scored candidate into a structured, human-readable justification. Every
recommendation must answer: why this trade, why now, biggest risk, invalidation,
and a confidence breakdown. 'Why not others?' is answered at the book level by the
ranking (each opportunity carries its rank and composite vs. peers).
"""

from __future__ import annotations

from app.modules.ai_engine.scoring import ScoreCard
from app.modules.scanner.opportunity import Explanation
from app.modules.scanner.regime import RegimeState
from app.modules.strategy.base import Direction, StrategyContext, StrategySignal


def build_explanation(
    signal: StrategySignal,
    ctx: StrategyContext,
    regime: RegimeState,
    scorecard: ScoreCard,
    strategy_name: str,
) -> Explanation:
    """Compose the structured explanation for one candidate."""
    why_this: list[str] = [f"{strategy_name}: {r}" for r in signal.rationale]
    why_this.append(
        f"Risk/reward {signal.risk_reward:.1f} to first target "
        f"({signal.expected_holding} horizon)."
    )

    why_now: list[str] = [
        f"Market regime is {regime.primary.value.replace('_', ' ')} "
        f"(confidence {regime.confidence:.0%}).",
    ]
    if regime.overlays:
        overlays = ", ".join(sorted(o.value.replace("_", " ") for o in regime.overlays))
        why_now.append(f"Active overlays: {overlays}")
    if scorecard.trend >= 65:
        why_now.append("Trend and index direction support the entry now.")
    if scorecard.volume >= 65:
        why_now.append("Volume is expanding into the signal.")

    biggest_risk = _biggest_risk(signal, ctx, regime, scorecard)
    side = "closes below" if signal.direction is Direction.LONG else "closes above"
    if signal.entry:
        away = signal.risk_per_unit / signal.entry * 100
        invalidation = (
            f"Thesis is wrong if price {side} the stop at {signal.stop:.2f} ({away:.1f}% away)."
        )
    else:
        invalidation = f"Invalidated at the stop {signal.stop:.2f}."

    breakdown = {
        k: v for k, v in scorecard.as_dict().items() if k not in ("composite", "confidence")
    }
    return Explanation(
        why_this=tuple(why_this),
        why_now=tuple(why_now),
        biggest_risk=biggest_risk,
        invalidation=invalidation,
        confidence_breakdown=breakdown,
    )


def _biggest_risk(
    signal: StrategySignal,
    ctx: StrategyContext,
    regime: RegimeState,
    scorecard: ScoreCard,
) -> str:
    """Pick the single most important risk from the weakest dimension / regime."""
    if regime.is_hostile:
        return "Hostile market regime — broad risk-off can overwhelm any single setup."
    dims = {
        "liquidity": "Thin liquidity — slippage and gap risk on exit.",
        "news": "Adverse news flow could invalidate the technical setup.",
        "volatility": "Elevated volatility widens stops and whipsaws entries.",
        "trend": "Trade is not aligned with the broader index trend.",
        "options": "Options positioning (PCR/OI) leans against this direction.",
    }
    scores = scorecard.as_dict()
    weakest = min(dims, key=lambda d: scores.get(d, 100.0))
    if scores.get(weakest, 100.0) < 50:
        return dims[weakest]
    return (
        "Standard execution risk — a fast move through the stop at "
        f"{signal.stop:.2f} is the primary threat."
    )
