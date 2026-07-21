"""Gap family: Gap & Go (continuation) and Gap Fill (fade)."""

from __future__ import annotations

from app.modules.strategy.base import Direction, Strategy, StrategyContext, StrategySignal
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.registry import register
from app.modules.strategy.ta import pct_change, sma


@register()
class GapAndGo(Strategy):
    key = "gap_and_go"
    name = "Gap & Go"
    description = "Meaningful gap that holds above the open on volume — momentum continuation."
    compatible_regimes = frozenset(
        {MarketRegime.GAP_UP_TREND, MarketRegime.TRENDING_BULL, MarketRegime.TRENDING_BEAR}
    )
    primary_timeframe = "5m"
    required_history = 4
    expected_holding = "intraday"

    MIN_GAP = 1.5  # percent

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx) or ctx.prev_close is None or ctx.day_open is None:
            return None
        if ctx.session_minutes is None or ctx.session_minutes > 90:
            return None  # only the first 90 minutes
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        gap = pct_change(ctx.prev_close, ctx.day_open)
        last = s.last
        atr = s.ind("atr_14") or abs(ctx.day_open - ctx.prev_close)
        vol_avg = sma(s.volumes(), 20) or 0.0
        vol_ok = last.volume > 1.2 * vol_avg if vol_avg else True
        if gap >= self.MIN_GAP and last.close > ctx.day_open and vol_ok:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=ctx.day_open - 0.3 * atr,
                targets=[last.close + 1.5 * atr, last.close + 3 * atr],
                confidence=0.5 + min(0.2, 0.03 * gap),
                rationale=[
                    f"Gapped up {gap:.1f}% and holding above the open",
                    "Volume confirms continuation" if vol_ok else "Holding the open",
                ],
                tags=["intraday", "gap", "momentum"],
                features={"gap_pct": gap},
            )
        if gap <= -self.MIN_GAP and last.close < ctx.day_open and vol_ok:
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=ctx.day_open + 0.3 * atr,
                targets=[last.close - 1.5 * atr, last.close - 3 * atr],
                confidence=0.5 + min(0.2, 0.03 * abs(gap)),
                rationale=[
                    f"Gapped down {gap:.1f}% and holding below the open",
                    "Volume confirms continuation" if vol_ok else "Holding the open",
                ],
                tags=["intraday", "gap", "momentum"],
                features={"gap_pct": gap},
            )
        return None


@register()
class GapFill(Strategy):
    key = "gap_fill"
    name = "Gap Fill"
    description = "Fades a moderate gap that stalls, targeting the prior close (gap fill)."
    compatible_regimes = frozenset({MarketRegime.RANGE, MarketRegime.DISTRIBUTION})
    primary_timeframe = "5m"
    required_history = 4
    expected_holding = "intraday"

    MIN_GAP = 1.0
    MAX_GAP = 3.0  # don't fade runaway gaps

    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        if not self._ready(ctx) or ctx.prev_close is None or ctx.day_open is None:
            return None
        if ctx.session_minutes is None or ctx.session_minutes > 120:
            return None
        s = ctx.tf(self.primary_timeframe)
        if s is None:
            return None
        gap = pct_change(ctx.prev_close, ctx.day_open)
        last, prev = s.bars[-1], s.bars[-2]
        atr = s.ind("atr_14") or abs(ctx.day_open - ctx.prev_close)
        # Gap up that stalls (lower high + failing) → fade toward prior close.
        if self.MIN_GAP <= gap <= self.MAX_GAP and last.close < prev.close < ctx.day_open:
            return self.signal(
                ctx,
                direction=Direction.SHORT,
                entry=last.close,
                stop=ctx.day_open + 0.5 * atr,
                targets=[ctx.prev_close],
                confidence=0.5,
                rationale=[
                    f"Gap up {gap:.1f}% stalled and is rolling over",
                    f"Targeting the gap fill at prior close {ctx.prev_close:.2f}",
                ],
                tags=["intraday", "gap", "mean-reversion"],
                features={"gap_pct": gap},
            )
        if -self.MAX_GAP <= gap <= -self.MIN_GAP and last.close > prev.close > ctx.day_open:
            return self.signal(
                ctx,
                direction=Direction.LONG,
                entry=last.close,
                stop=ctx.day_open - 0.5 * atr,
                targets=[ctx.prev_close],
                confidence=0.5,
                rationale=[
                    f"Gap down {gap:.1f}% stalled and is bouncing",
                    f"Targeting the gap fill at prior close {ctx.prev_close:.2f}",
                ],
                tags=["intraday", "gap", "mean-reversion"],
                features={"gap_pct": gap},
            )
        return None
