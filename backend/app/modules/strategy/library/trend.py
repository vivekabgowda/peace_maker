"""Trend family: EMA trend-following, EMA pullback, VWAP pullback.

Pullback strategies buy strength into support rather than chasing extension —
they abstain unless price is stretched back toward a moving reference in an
established trend.
"""

from __future__ import annotations

from app.modules.strategy.base import Direction, Strategy, StrategyContext, StrategySignal
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.registry import register

_UPTRENDS = frozenset({MarketRegime.TRENDING_BULL, MarketRegime.GAP_UP_TREND})
_DOWNTRENDS = frozenset({MarketRegime.TRENDING_BEAR, MarketRegime.GAP_DOWN_PANIC})


@register()
class EMATrend(Strategy):
    key = "ema_trend"
    name = "EMA Trend"
    description = "Aligned 9/21/50 EMA stack with price above/below — ride the trend."
    compatible_regimes = _UPTRENDS | _DOWNTRENDS
    primary_timeframe = "1d"
    required_history = 55
    expected_holding = "1-3 weeks"

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx):
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        e9, e21, e50 = s.ind("ema_9"), s.ind("ema_21"), s.ind("ema_50")
        atr, adx = s.ind("atr_14"), s.ind("adx_14")
        if None in (e9, e21, e50, atr) or atr is None or atr <= 0:
            return None
        assert e9 is not None and e21 is not None and e50 is not None
        last = s.last
        strong = (adx or 0.0) >= 20
        if e9 > e21 > e50 and last.close > e21:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=e50 - atr,
                targets=[last.close + 2 * atr, last.close + 4 * atr],
                confidence=0.5 + (0.12 if strong else 0.0),
                rationale=[
                    "EMA stack 9>21>50 with price above the 21 EMA",
                    f"ADX {adx:.0f} confirms trend strength" if strong else "Trend intact",
                ],
                tags=["swing", "trend"],
                features={"adx": adx or 0.0},
            )
        if e9 < e21 < e50 and last.close < e21:
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=e50 + atr,
                targets=[last.close - 2 * atr, last.close - 4 * atr],
                confidence=0.5 + (0.12 if strong else 0.0),
                rationale=[
                    "EMA stack 9<21<50 with price below the 21 EMA",
                    f"ADX {adx:.0f} confirms trend strength" if strong else "Trend intact",
                ],
                tags=["swing", "trend"],
                features={"adx": adx or 0.0},
            )
        return None


@register()
class EMAPullback(Strategy):
    key = "ema_pullback"
    name = "EMA Pullback"
    description = "Buys a pullback to the 21 EMA inside an uptrend (or sells to it in a downtrend)."
    compatible_regimes = _UPTRENDS | _DOWNTRENDS
    primary_timeframe = "1d"
    required_history = 55
    expected_holding = "3-10 days"

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx):
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        e21, e50 = s.ind("ema_21"), s.ind("ema_50")
        atr, rsi = s.ind("atr_14"), s.ind("rsi_14")
        if e21 is None or e50 is None or atr is None or atr <= 0:
            return None
        last = s.last
        near_21 = abs(last.low - e21) <= 0.5 * atr or (last.low <= e21 <= last.high)
        if e21 > e50 and near_21 and last.close > e21 and (rsi is None or 40 <= rsi <= 65):
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=min(last.low, e50) - 0.2 * atr,
                targets=[last.close + 1.5 * atr, last.close + 3 * atr],
                confidence=0.55,
                rationale=[
                    "Pullback tagged the rising 21 EMA and closed back above it",
                    "RSI in the healthy 40-65 pullback zone" if rsi else "Trend pullback",
                ],
                tags=["swing", "pullback", "trend"],
            )
        near_21_dn = abs(last.high - e21) <= 0.5 * atr or (last.low <= e21 <= last.high)
        if e21 < e50 and near_21_dn and last.close < e21 and (rsi is None or 35 <= rsi <= 60):
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=max(last.high, e50) + 0.2 * atr,
                targets=[last.close - 1.5 * atr, last.close - 3 * atr],
                confidence=0.55,
                rationale=[
                    "Rally tagged the falling 21 EMA and closed back below it",
                    "RSI in the 35-60 counter-trend zone" if rsi else "Trend pullback",
                ],
                tags=["swing", "pullback", "trend"],
            )
        return None


@register()
class VWAPPullback(Strategy):
    key = "vwap_pullback"
    name = "VWAP Pullback"
    description = "Intraday pullback to a rising/falling VWAP that holds — continuation entry."
    compatible_regimes = frozenset({MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR})
    primary_timeframe = "5m"
    required_history = 15
    expected_holding = "intraday"

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx):
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        vwap, atr = s.ind("vwap"), s.ind("atr_14")
        if vwap is None or atr is None or atr <= 0:
            return None
        last, prev = s.bars[-1], s.bars[-2]
        touched = last.low <= vwap <= last.high
        long_ok = last.close > vwap and prev.close > vwap and ctx.index_trend is Direction.LONG
        if touched and long_ok:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=vwap - 0.75 * atr,
                targets=[last.close + atr, last.close + 2 * atr],
                confidence=0.55,
                rationale=[
                    f"Held the rising VWAP ({vwap:.2f}) on a pullback",
                    "Index trend supports continuation",
                ],
                tags=["intraday", "vwap", "pullback"],
            )
        if (
            touched
            and last.close < vwap
            and prev.close < vwap
            and ctx.index_trend is Direction.SHORT
        ):
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=vwap + 0.75 * atr,
                targets=[last.close - atr, last.close - 2 * atr],
                confidence=0.55,
                rationale=[
                    f"Rejected the falling VWAP ({vwap:.2f}) on a bounce",
                    "Index trend supports continuation",
                ],
                tags=["intraday", "vwap", "pullback"],
            )
        return None
