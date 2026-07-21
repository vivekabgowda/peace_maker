"""Momentum family: Relative Strength (vs index) and price Momentum."""

from __future__ import annotations

from app.modules.strategy.base import Direction, Strategy, StrategyContext, StrategySignal
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.registry import register
from app.modules.strategy.ta import pct_change


@register()
class RelativeStrength(Strategy):
    key = "relative_strength"
    name = "Relative Strength"
    description = "Outperforms its index while both trend up — leadership continuation."
    compatible_regimes = frozenset({MarketRegime.TRENDING_BULL, MarketRegime.GAP_UP_TREND})
    primary_timeframe = "1d"
    required_history = 30
    expected_holding = "1-4 weeks"

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx) or ctx.relative_strength is None:
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        e50, atr = s.ind("ema_50"), s.ind("atr_14")
        if e50 is None or atr is None or atr <= 0:
            return None
        last = s.last
        leading = ctx.relative_strength > 2.0  # >2% ahead of index over lookback
        if leading and last.close > e50 and ctx.index_trend is Direction.LONG:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=e50 - atr,
                targets=[last.close + 2 * atr, last.close + 4 * atr],
                confidence=min(0.85, 0.5 + 0.03 * ctx.relative_strength),
                rationale=[
                    f"Outperforming its index by {ctx.relative_strength:.1f}%",
                    "Above the 50 EMA with the index also trending up",
                ],
                tags=["swing", "relative-strength", "leadership"],
                features={"relative_strength": ctx.relative_strength},
            )
        return None


@register()
class RelativeWeakness(Strategy):
    key = "relative_weakness"
    name = "Relative Weakness"
    description = "Underperforms its index while both trend down — laggard short."
    compatible_regimes = frozenset({MarketRegime.TRENDING_BEAR, MarketRegime.GAP_DOWN_PANIC})
    primary_timeframe = "1d"
    required_history = 30
    expected_holding = "1-3 weeks"

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx) or ctx.relative_strength is None:
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        e50, atr = s.ind("ema_50"), s.ind("atr_14")
        if e50 is None or atr is None or atr <= 0:
            return None
        last = s.last
        lagging = ctx.relative_strength < -2.0
        if lagging and last.close < e50 and ctx.index_trend is Direction.SHORT:
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=e50 + atr,
                targets=[last.close - 2 * atr, last.close - 4 * atr],
                confidence=min(0.85, 0.5 + 0.03 * abs(ctx.relative_strength)),
                rationale=[
                    f"Underperforming its index by {abs(ctx.relative_strength):.1f}%",
                    "Below the 50 EMA with the index also trending down",
                ],
                tags=["swing", "relative-weakness"],
                features={"relative_strength": ctx.relative_strength},
            )
        return None


@register()
class Momentum(Strategy):
    key = "momentum"
    name = "Momentum"
    description = "Strong multi-bar momentum with RSI thrust, not yet exhausted."
    compatible_regimes = frozenset({MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR})
    primary_timeframe = "1d"
    required_history = 30
    expected_holding = "3-15 days"

    LOOKBACK = 10

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx):
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        atr, rsi = s.ind("atr_14"), s.ind("rsi_14")
        if atr is None or atr <= 0 or rsi is None:
            return None
        closes = s.closes()
        mom = pct_change(closes[-self.LOOKBACK - 1], closes[-1])
        last = s.last
        # Long: strong up-momentum with RSI in thrust band but below overbought.
        if mom > 6.0 and 55 <= rsi <= 72:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=last.close - 2 * atr,
                targets=[last.close + 2 * atr, last.close + 3.5 * atr],
                confidence=min(0.8, 0.5 + 0.02 * mom),
                rationale=[
                    f"{self.LOOKBACK}-bar momentum +{mom:.1f}%",
                    f"RSI {rsi:.0f} in the thrust zone, not overbought",
                ],
                tags=["swing", "momentum"],
                features={"momentum_pct": mom},
            )
        if mom < -6.0 and 28 <= rsi <= 45:
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=last.close + 2 * atr,
                targets=[last.close - 2 * atr, last.close - 3.5 * atr],
                confidence=min(0.8, 0.5 + 0.02 * abs(mom)),
                rationale=[
                    f"{self.LOOKBACK}-bar momentum {mom:.1f}%",
                    f"RSI {rsi:.0f} in the down-thrust zone, not oversold",
                ],
                tags=["swing", "momentum"],
                features={"momentum_pct": mom},
            )
        return None
