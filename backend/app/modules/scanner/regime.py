"""Market Regime Engine (Sprint 3, Step 1).

Classifies the current market into one *primary* structure regime plus any active
*overlay* regimes (volatility, event, gap), from index bars/indicators and the
calendars. Every strategy consults the regime before firing — the engine is the
platform's first gate against trading the wrong environment.

Pure and deterministic given its inputs, so it is fully unit-testable and
identical between live scanning and backtests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.modules.scanner import macro_events
from app.modules.strategy.base import Direction, Series
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.ta import pct_change, slope
from app.shared.market_calendar import IST, nearest_weekly_expiry

logger = get_logger("regime_engine")


@dataclass(frozen=True, slots=True)
class RegimeState:
    """The classified environment at a point in time."""

    primary: MarketRegime
    overlays: frozenset[MarketRegime]
    confidence: float  # 0..1 for the primary classification
    index_trend: Direction
    features: dict[str, float] = field(default_factory=dict)
    ts: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def regimes(self) -> frozenset[MarketRegime]:
        """Full active set (primary + overlays) used by strategy gating."""
        return frozenset({self.primary}) | self.overlays

    @property
    def is_hostile(self) -> bool:
        from app.modules.strategy.regime_types import HOSTILE_REGIMES

        return bool(self.regimes & HOSTILE_REGIMES)


class RegimeEngine:
    """Detects the market regime from the benchmark index series + calendars."""

    # Thresholds (percent unless noted). Kept as class attributes so they are
    # tunable/overridable without touching logic.
    ADX_TREND = 22.0
    ADX_STRONG = 30.0
    HIGH_VOL_ATR_PCT = 2.2  # daily ATR as % of price
    LOW_VOL_ATR_PCT = 0.8
    GAP_UP_PCT = 0.75
    GAP_DOWN_PANIC_PCT = -1.5
    RISK_OFF_GAP_PCT = -1.0

    def detect(
        self,
        index_series: Series,
        *,
        now: datetime | None = None,
        prev_close: float | None = None,
        day_open: float | None = None,
        breadth: float | None = None,
        global_risk_off: bool | None = None,
    ) -> RegimeState:
        """Classify the regime.

        ``index_series`` is the daily benchmark (e.g. NIFTY) with indicators.
        ``breadth`` is advance/decline ratio (>1 bullish) when available.
        ``global_risk_off`` is an external cue (SGX/VIX) overriding inference.
        """
        now = now or datetime.now(UTC)
        features: dict[str, float] = {}

        primary, trend, conf = self._primary(index_series, breadth, features)
        overlays = self._overlays(
            index_series,
            now=now,
            prev_close=prev_close,
            day_open=day_open,
            global_risk_off=global_risk_off,
            features=features,
        )
        return RegimeState(
            primary=primary,
            overlays=frozenset(overlays),
            confidence=conf,
            index_trend=trend,
            features=features,
            ts=now,
        )

    # -- Primary structure --------------------------------------------------
    def _primary(
        self, s: Series, breadth: float | None, features: dict[str, float]
    ) -> tuple[MarketRegime, Direction, float]:
        if len(s) < 50:
            return MarketRegime.RANGE, Direction.NONE, 0.3
        e21, e50 = s.ind("ema_21"), s.ind("ema_50")
        adx = s.ind("adx_14") or 0.0
        last = s.last
        closes = s.closes()
        e50_slope = slope(closes[-20:])
        features.update({"adx": adx, "ema50_slope": e50_slope})

        up = e21 is not None and e50 is not None and e21 > e50 and last.close > e50
        down = e21 is not None and e50 is not None and e21 < e50 and last.close < e50

        if adx >= self.ADX_TREND and up:
            conf = min(0.95, 0.55 + (adx - self.ADX_TREND) / 40)
            return MarketRegime.TRENDING_BULL, Direction.LONG, conf
        if adx >= self.ADX_TREND and down:
            conf = min(0.95, 0.55 + (adx - self.ADX_TREND) / 40)
            return MarketRegime.TRENDING_BEAR, Direction.SHORT, conf

        # Weak trend → range/accumulation/distribution by position + drift.
        rng_hi = max(s.highs(20))
        rng_lo = min(s.lows(20))
        span = rng_hi - rng_lo
        pos = (last.close - rng_lo) / span if span > 0 else 0.5
        features["range_position"] = pos
        b = breadth if breadth is not None else 1.0
        if pos <= 0.35 and e50_slope >= 0 and b >= 1.0:
            return MarketRegime.ACCUMULATION, Direction.NONE, 0.5
        if pos >= 0.65 and e50_slope <= 0 and b < 1.0:
            return MarketRegime.DISTRIBUTION, Direction.NONE, 0.5
        trend = Direction.LONG if up else Direction.SHORT if down else Direction.NONE
        return MarketRegime.RANGE, trend, 0.45

    # -- Overlays -----------------------------------------------------------
    def _overlays(
        self,
        s: Series,
        *,
        now: datetime,
        prev_close: float | None,
        day_open: float | None,
        global_risk_off: bool | None,
        features: dict[str, float],
    ) -> set[MarketRegime]:
        overlays: set[MarketRegime] = set()
        day = now.astimezone(IST).date()

        # Volatility overlay from daily ATR as a percent of price.
        atr = s.ind("atr_14")
        price = s.last.close
        if atr is not None and price > 0:
            atr_pct = atr / price * 100.0
            features["atr_pct"] = atr_pct
            if atr_pct >= self.HIGH_VOL_ATR_PCT:
                overlays.add(MarketRegime.HIGH_VOLATILITY)
            elif atr_pct <= self.LOW_VOL_ATR_PCT:
                overlays.add(MarketRegime.LOW_VOLATILITY)

        # Event overlays from the calendars.
        if nearest_weekly_expiry(day) == day:
            overlays.add(MarketRegime.EXPIRY_DAY)
        if macro_events.is_rbi_day(day):
            overlays.add(MarketRegime.RBI_DAY)
        if macro_events.is_budget_day(day):
            overlays.add(MarketRegime.BUDGET_DAY)
        if macro_events.is_election_event(day):
            overlays.add(MarketRegime.ELECTION_EVENT)

        # Gap overlays from the session open vs. prior close.
        if prev_close is not None and day_open is not None and prev_close > 0:
            gap = pct_change(prev_close, day_open)
            features["index_gap_pct"] = gap
            if gap >= self.GAP_UP_PCT:
                overlays.add(MarketRegime.GAP_UP_TREND)
            elif gap <= self.GAP_DOWN_PANIC_PCT:
                overlays.add(MarketRegime.GAP_DOWN_PANIC)
            # Infer risk-off from a sharp gap-down unless told otherwise.
            if global_risk_off is None and gap <= self.RISK_OFF_GAP_PCT:
                overlays.add(MarketRegime.GLOBAL_RISK_OFF)

        if global_risk_off:
            overlays.add(MarketRegime.GLOBAL_RISK_OFF)

        return overlays
