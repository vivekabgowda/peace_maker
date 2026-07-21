"""Breakout family: Opening Range Breakout, VWAP breakout, Volume breakout, CPR.

Each strategy is a pure function of the context and abstains (returns ``None``)
unless its precise setup is present — no forced trades.
"""

from __future__ import annotations

from app.modules.strategy.base import Bar, Direction, Strategy, StrategyContext, StrategySignal
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.registry import register
from app.modules.strategy.ta import central_pivot_range, highest, sma

_TREND = frozenset({MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR, MarketRegime.RANGE})


@register()
class OpeningRangeBreakout(Strategy):
    key = "orb"
    name = "Opening Range Breakout"
    description = "Breaks the first-N-minute range with momentum and volume expansion."
    compatible_regimes = frozenset(
        {MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR, MarketRegime.GAP_UP_TREND}
    )
    primary_timeframe = "5m"
    required_history = 6
    expected_holding = "intraday"

    OPENING_BARS = 3  # first 15 minutes on 5m

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx) or ctx.session_minutes is None:
            return None
        # Only valid after the opening range forms and before the last hour.
        if ctx.session_minutes < self.OPENING_BARS * 5 or ctx.session_minutes > 300:
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        opening = s.bars[: self.OPENING_BARS]
        or_high = max(b.high for b in opening)
        or_low = min(b.low for b in opening)
        last = s.last
        atr = s.ind("atr_14") or (or_high - or_low)
        vol_avg = sma(s.volumes(), 20) or 0.0
        vol_ok = last.volume > 1.2 * vol_avg if vol_avg else True

        if last.close > or_high and vol_ok:
            stop = or_low if (last.close - or_low) < 2 * atr else last.close - 1.5 * atr
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=stop,
                targets=[last.close + (last.close - stop) * r for r in (1.5, 2.5)],
                confidence=0.55 + (0.1 if vol_ok else 0.0),
                rationale=[
                    f"Closed above the opening range high {or_high:.2f}",
                    "Volume expansion confirms the breakout" if vol_ok else "Range break",
                ],
                tags=["intraday", "breakout"],
                features={"or_high": or_high, "or_low": or_low},
            )
        if last.close < or_low and vol_ok:
            stop = or_high if (or_high - last.close) < 2 * atr else last.close + 1.5 * atr
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=stop,
                targets=[last.close - (stop - last.close) * r for r in (1.5, 2.5)],
                confidence=0.55 + (0.1 if vol_ok else 0.0),
                rationale=[
                    f"Closed below the opening range low {or_low:.2f}",
                    "Volume expansion confirms the breakdown" if vol_ok else "Range break",
                ],
                tags=["intraday", "breakout"],
                features={"or_high": or_high, "or_low": or_low},
            )
        return None


@register()
class VWAPBreakout(Strategy):
    key = "vwap_breakout"
    name = "VWAP Breakout"
    description = "Reclaims/loses session VWAP with trend alignment — institutional bias flip."
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
        vwap = s.ind("vwap")
        atr = s.ind("atr_14")
        if vwap is None or atr is None or atr <= 0:
            return None
        last, prev = s.bars[-1], s.bars[-2]
        crossed_up = prev.close <= vwap < last.close
        crossed_dn = prev.close >= vwap > last.close
        if crossed_up and ctx.index_trend is not Direction.SHORT:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=vwap - 0.5 * atr,
                targets=[last.close + atr, last.close + 2 * atr],
                confidence=0.5 + (0.12 if ctx.index_trend is Direction.LONG else 0.0),
                rationale=[
                    f"Reclaimed session VWAP ({vwap:.2f})",
                    "Index trend aligned" if ctx.index_trend is Direction.LONG else "VWAP flip",
                ],
                tags=["intraday", "vwap"],
            )
        if crossed_dn and ctx.index_trend is not Direction.LONG:
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=vwap + 0.5 * atr,
                targets=[last.close - atr, last.close - 2 * atr],
                confidence=0.5 + (0.12 if ctx.index_trend is Direction.SHORT else 0.0),
                rationale=[
                    f"Lost session VWAP ({vwap:.2f})",
                    "Index trend aligned" if ctx.index_trend is Direction.SHORT else "VWAP flip",
                ],
                tags=["intraday", "vwap"],
            )
        return None


@register()
class VolumeBreakout(Strategy):
    key = "volume_breakout"
    name = "Volume Breakout"
    description = "N-day high broken on a volume surge vs. the 20-bar average."
    compatible_regimes = _TREND
    primary_timeframe = "1d"
    required_history = 25
    expected_holding = "2-10 days"

    LOOKBACK = 20

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx):
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        last: Bar = s.last
        prior_high = highest(s.highs()[:-1], self.LOOKBACK)
        vol_avg = sma(s.volumes()[:-1], self.LOOKBACK)
        atr = s.ind("atr_14")
        if prior_high is None or vol_avg is None or atr is None or atr <= 0:
            return None
        surge = last.volume / vol_avg if vol_avg else 0.0
        if last.close > prior_high and surge >= 2.0 and last.is_up:
            stop = last.close - 2 * atr
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=stop,
                targets=[last.close + 2 * atr, last.close + 4 * atr],
                confidence=min(0.85, 0.5 + 0.1 * (surge - 1)),
                rationale=[
                    f"Broke the {self.LOOKBACK}-day high {prior_high:.2f}",
                    f"Volume {surge:.1f}x the 20-day average",
                ],
                tags=["swing", "breakout", "volume"],
                features={"volume_surge": surge},
            )
        return None


@register()
class CPRBreakout(Strategy):
    key = "cpr_breakout"
    name = "CPR Breakout"
    description = "Breaks a narrow Central Pivot Range — trend-day expansion setup."
    compatible_regimes = frozenset({MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR})
    primary_timeframe = "5m"
    required_history = 10
    expected_holding = "intraday"

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx) or ctx.prev_close is None:
            return None
        daily = ctx.tf("1d")
        s = ctx.tf(self.primary_timeframe)
        if s is None or daily is None or len(daily) < 2:
            return None
        prior = daily.bars[-2]  # yesterday's completed session
        cpr = central_pivot_range(prior.high, prior.low, prior.close)
        # Narrow CPR (< 0.4% of price) precedes trend days.
        if cpr.width > 0.004 * prior.close:
            return None
        last = s.last
        if last.close > cpr.tc and last.close > cpr.pivot:
            stop = cpr.bc
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=stop,
                targets=[cpr.r1, cpr.r2],
                confidence=0.55,
                rationale=[
                    f"Broke a narrow CPR (TC {cpr.tc:.2f})",
                    "Narrow CPR precedes trend-day expansion",
                ],
                tags=["intraday", "cpr"],
                features={"cpr_width": cpr.width},
            )
        if last.close < cpr.bc and last.close < cpr.pivot:
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=cpr.tc,
                targets=[cpr.s1, cpr.s2],
                confidence=0.55,
                rationale=[
                    f"Broke below a narrow CPR (BC {cpr.bc:.2f})",
                    "Narrow CPR precedes trend-day expansion",
                ],
                tags=["intraday", "cpr"],
                features={"cpr_width": cpr.width},
            )
        return None
