"""Volatility family: Volatility Contraction Pattern (VCP) breakout."""

from __future__ import annotations

from app.modules.strategy.base import Direction, Strategy, StrategyContext, StrategySignal
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.registry import register
from app.modules.strategy.ta import highest, is_contracting, sma


@register()
class VolatilityContraction(Strategy):
    key = "vcp"
    name = "Volatility Contraction Pattern"
    description = "Tightening ranges near a pivot high, then a breakout on volume (Minervini VCP)."
    compatible_regimes = frozenset(
        {MarketRegime.TRENDING_BULL, MarketRegime.ACCUMULATION, MarketRegime.LOW_VOLATILITY}
    )
    primary_timeframe = "1d"
    required_history = 30
    expected_holding = "2-6 weeks"

    LOOKBACK = 20

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx):
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        atr = s.ind("atr_14")
        if atr is None or atr <= 0:
            return None
        # Measure contraction on the bars *before* the breakout bar — the
        # breakout itself expands range and would otherwise mask the setup.
        ranges = [b.range for b in s.bars[:-1]]
        contracting = is_contracting(ranges, lookback=6)
        pivot = highest(s.highs()[:-1], self.LOOKBACK)
        vol_avg = sma(s.volumes()[:-1], self.LOOKBACK)
        if pivot is None or vol_avg is None:
            return None
        last = s.last
        surge = last.volume / vol_avg if vol_avg else 0.0
        # Breakout out of a contraction, above the pivot, on expanding volume.
        if contracting and last.close > pivot and surge >= 1.5 and last.is_up:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=last.close - 1.5 * atr,
                targets=[last.close + 2.5 * atr, last.close + 5 * atr],
                confidence=min(0.85, 0.55 + 0.1 * (surge - 1)),
                rationale=[
                    "Ranges contracted then broke the pivot high",
                    f"Breakout volume {surge:.1f}x the 20-day average",
                ],
                tags=["swing", "vcp", "volatility"],
                features={"volume_surge": surge, "pivot": pivot},
            )
        return None
