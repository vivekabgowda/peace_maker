"""AI evaluation — the 11-factor scorecard (Sprint 3, Step 4).

Every candidate signal is scored on eleven independent 0-100 dimensions, then
combined into a weighted composite and a calibrated confidence. Scores are
transparent (each is a documented function of observable features) so the
Explainability layer can show *why* a candidate ranks where it does.

This is deterministic, side-effect-free math — no model weights to train in V1;
the design leaves clean seams to swap any single dimension for a learned model
later without touching the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.scanner.regime import RegimeState
from app.modules.strategy.base import Direction, StrategyContext, StrategySignal
from app.modules.strategy.regime_types import HOSTILE_REGIMES, MarketRegime
from app.modules.strategy.ta import sma


def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


@dataclass(frozen=True, slots=True)
class ScoreCard:
    """The eleven dimension scores (0-100) plus the composite and confidence."""

    technical: float
    volume: float
    trend: float
    volatility: float
    liquidity: float
    sector: float
    news: float
    options: float
    regime: float
    risk: float
    portfolio_impact: float
    composite: float
    confidence: float

    def as_dict(self) -> dict[str, float]:
        return {
            "technical": self.technical,
            "volume": self.volume,
            "trend": self.trend,
            "volatility": self.volatility,
            "liquidity": self.liquidity,
            "sector": self.sector,
            "news": self.news,
            "options": self.options,
            "regime": self.regime,
            "risk": self.risk,
            "portfolio_impact": self.portfolio_impact,
            "composite": self.composite,
            "confidence": self.confidence,
        }


# Composite weights (sum need not be 1; normalized at combine time). Regime and
# risk are weighted heavily — a great setup in a hostile regime should not rank.
_WEIGHTS: dict[str, float] = {
    "technical": 1.6,
    "volume": 1.0,
    "trend": 1.4,
    "volatility": 0.8,
    "liquidity": 0.9,
    "sector": 0.7,
    "news": 0.6,
    "options": 0.6,
    "regime": 1.5,
    "risk": 1.4,
    "portfolio_impact": 1.0,
}


@dataclass
class PortfolioImpact:
    """Inputs describing how a candidate would fit the current book (0-100)."""

    score: float = 100.0
    notes: list[str] = field(default_factory=list)


class ScoringEngine:
    """Computes a :class:`ScoreCard` for a candidate signal in its context."""

    def score(
        self,
        signal: StrategySignal,
        ctx: StrategyContext,
        regime: RegimeState,
        *,
        strategy_win_rate: float | None = None,
        strategy_proven: bool = False,
        portfolio: PortfolioImpact | None = None,
        median_turnover: float | None = None,
    ) -> ScoreCard:
        technical = self._technical(signal, ctx)
        volume = self._volume(signal, ctx)
        trend = self._trend(signal, ctx, regime)
        volatility = self._volatility(signal, ctx, regime)
        liquidity = self._liquidity(ctx, median_turnover)
        sector = self._sector(signal, ctx, regime)
        news = self._news(signal, ctx)
        options = self._options(signal, ctx)
        regime_s = self._regime(signal, regime, strategy_win_rate, strategy_proven)
        risk = self._risk(signal)
        pimpact = portfolio.score if portfolio else 100.0

        scores = {
            "technical": technical,
            "volume": volume,
            "trend": trend,
            "volatility": volatility,
            "liquidity": liquidity,
            "sector": sector,
            "news": news,
            "options": options,
            "regime": regime_s,
            "risk": risk,
            "portfolio_impact": pimpact,
        }
        total_w = sum(_WEIGHTS.values())
        composite = sum(scores[k] * _WEIGHTS[k] for k in scores) / total_w
        # Confidence blends the strategy's own calibrated confidence with the
        # composite and is knocked down hard in hostile regimes.
        conf = (0.5 * signal.confidence + 0.5 * composite / 100.0) * self._regime_penalty(regime)
        return ScoreCard(
            composite=round(composite, 2),
            confidence=round(_clamp(conf * 100, 0, 100) / 100, 4),
            **{k: round(v, 2) for k, v in scores.items()},
        )

    # -- Individual dimensions ---------------------------------------------
    def _technical(self, sig: StrategySignal, ctx: StrategyContext) -> float:
        """Reward clean risk/reward and strategy confidence."""
        rr = sig.risk_reward
        base = 40 + 20 * sig.confidence
        base += min(30.0, rr * 12)  # RR of 2.5 ≈ +30
        return _clamp(base)

    def _volume(self, sig: StrategySignal, ctx: StrategyContext) -> float:
        surge = sig.features.get("volume_surge")
        if surge is not None:
            return _clamp(45 + 20 * (surge - 1))
        s = ctx.tf(sig_primary_tf(ctx))
        if s is None or len(s) < 21:
            return 50.0
        last_vol = s.last.volume
        avg = sma(s.volumes()[:-1], 20) or 0.0
        if avg <= 0:
            return 50.0
        return _clamp(40 + 25 * (last_vol / avg - 1))

    def _trend(self, sig: StrategySignal, ctx: StrategyContext, regime: RegimeState) -> float:
        aligned = (sig.direction is Direction.LONG and regime.index_trend is Direction.LONG) or (
            sig.direction is Direction.SHORT and regime.index_trend is Direction.SHORT
        )
        counter = (sig.direction is Direction.LONG and regime.index_trend is Direction.SHORT) or (
            sig.direction is Direction.SHORT and regime.index_trend is Direction.LONG
        )
        base = 75.0 if aligned else 35.0 if counter else 55.0
        adx = regime.features.get("adx", 0.0)
        return _clamp(base + min(15.0, adx / 3) * (1 if aligned else -1 if counter else 0))

    def _volatility(self, sig: StrategySignal, ctx: StrategyContext, regime: RegimeState) -> float:
        """Prefer orderly volatility; penalize extreme/thin conditions."""
        if MarketRegime.HIGH_VOLATILITY in regime.regimes:
            return 40.0
        if MarketRegime.LOW_VOLATILITY in regime.regimes:
            return 65.0
        return 60.0

    def _liquidity(self, ctx: StrategyContext, median_turnover: float | None) -> float:
        s = ctx.tf(sig_primary_tf(ctx))
        if s is None:
            return 50.0
        turnover = s.last.close * s.last.volume
        if median_turnover and median_turnover > 0:
            return _clamp(40 + 30 * min(2.0, turnover / median_turnover))
        # Absolute fallback: ₹ turnover buckets.
        if turnover >= 5e8:
            return 85.0
        if turnover >= 1e8:
            return 70.0
        if turnover >= 2e7:
            return 55.0
        return 35.0

    def _sector(self, sig: StrategySignal, ctx: StrategyContext, regime: RegimeState) -> float:
        if ctx.relative_strength is None:
            return 55.0
        # A leader in an aligned trend scores higher.
        return _clamp(55 + ctx.relative_strength * 2)

    def _news(self, sig: StrategySignal, ctx: StrategyContext) -> float:
        if ctx.news_score is None:
            return 55.0
        directional = ctx.news_score if sig.direction is Direction.LONG else -ctx.news_score
        return _clamp(55 + directional * 40)

    def _options(self, sig: StrategySignal, ctx: StrategyContext) -> float:
        if ctx.options is None or ctx.options.pcr is None:
            return 55.0
        pcr = ctx.options.pcr
        # PCR extremes are contrarian: high PCR (fear) favors longs, low favors shorts.
        if sig.direction is Direction.LONG:
            return _clamp(45 + (pcr - 1.0) * 30)
        return _clamp(45 + (1.0 - pcr) * 30)

    def _regime(
        self,
        sig: StrategySignal,
        regime: RegimeState,
        win_rate: float | None,
        proven: bool,
    ) -> float:
        if regime.regimes & HOSTILE_REGIMES:
            return 20.0
        base = 45 + 40 * regime.confidence
        if proven and win_rate is not None:
            base = 0.6 * base + 0.4 * (win_rate * 100)
        return _clamp(base)

    def _risk(self, sig: StrategySignal) -> float:
        """Reward defined, sensible risk and good RR; penalize wide/absent stops."""
        if sig.risk_per_unit <= 0 or not sig.targets:
            return 20.0
        risk_pct = sig.risk_per_unit / sig.entry * 100 if sig.entry else 100
        rr = sig.risk_reward
        base = 50 + min(30.0, rr * 12)
        if risk_pct > 6:  # stop wider than 6% of price is expensive
            base -= min(25.0, (risk_pct - 6) * 4)
        return _clamp(base)

    def _regime_penalty(self, regime: RegimeState) -> float:
        if regime.regimes & HOSTILE_REGIMES:
            return 0.5
        return 1.0


def sig_primary_tf(ctx: StrategyContext) -> str:
    """Best available timeframe for volume/liquidity reads (prefer intraday 5m)."""
    for tf in ("5m", "15m", "1d", "1h"):
        if ctx.tf(tf) is not None:
            return tf
    keys = list(ctx.series.keys())
    return keys[0] if keys else "1d"
