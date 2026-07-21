"""Strategy plugin contracts — the spine of the Alpha Engine (Sprint 3, Step 2).

Every strategy is a self-contained plugin that:
- declares the regimes it is compatible with,
- receives a read-only :class:`StrategyContext` (bars, indicators, regime, options,
  relative strength, session, news),
- returns at most one :class:`StrategySignal` with full reasoning, risk levels,
  expected holding time and a calibrated confidence, or ``None`` to abstain.

Strategies never mutate shared state, never do I/O, and are pure functions of the
context — which makes them independently unit-testable and backtestable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.modules.strategy.regime_types import MarketRegime


class Direction(StrEnum):
    LONG = "long"
    SHORT = "short"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class Bar:
    """One OHLCV bar. Plain floats — strategies do arithmetic, not persistence."""

    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int

    @property
    def range(self) -> float:
        return self.high - self.low

    @property
    def body(self) -> float:
        return abs(self.close - self.open)

    @property
    def is_up(self) -> bool:
        return self.close >= self.open


@dataclass(frozen=True, slots=True)
class Series:
    """A read-only OHLCV series for one timeframe plus its latest indicators.

    ``bars`` is oldest-first. ``indicators`` is the latest indicator bundle from
    the incremental engine (ema_9, rsi_14, atr_14, vwap, adx_14, ...).
    """

    timeframe: str
    bars: Sequence[Bar]
    indicators: Mapping[str, float | None]

    def __len__(self) -> int:
        return len(self.bars)

    @property
    def last(self) -> Bar:
        return self.bars[-1]

    def closes(self, n: int | None = None) -> list[float]:
        data = [b.close for b in self.bars]
        return data[-n:] if n else data

    def highs(self, n: int | None = None) -> list[float]:
        data = [b.high for b in self.bars]
        return data[-n:] if n else data

    def lows(self, n: int | None = None) -> list[float]:
        data = [b.low for b in self.bars]
        return data[-n:] if n else data

    def volumes(self, n: int | None = None) -> list[int]:
        data = [b.volume for b in self.bars]
        return data[-n:] if n else data

    def ind(self, name: str) -> float | None:
        return self.indicators.get(name)


@dataclass(frozen=True, slots=True)
class OptionContext:
    """Aggregated option metrics for the instrument's underlying (may be absent)."""

    pcr: float | None = None
    max_pain: float | None = None
    total_ce_oi: int = 0
    total_pe_oi: int = 0
    iv: float | None = None
    iv_percentile: float | None = None


@dataclass(frozen=True, slots=True)
class StrategyContext:
    """Everything a strategy needs to make one decision, read-only.

    A strategy reads only what it needs; missing timeframes/fields simply cause it
    to abstain. ``relative_strength`` is the instrument's return vs. its index over
    a lookback (>0 = outperforming). ``session_minutes`` is minutes since the open.
    """

    symbol: str
    instrument_id: int
    now: datetime
    series: Mapping[str, Series]
    regimes: frozenset[MarketRegime]
    sector: str | None = None
    prev_close: float | None = None
    day_open: float | None = None
    relative_strength: float | None = None
    session_minutes: int | None = None
    options: OptionContext | None = None
    news_score: float | None = None  # -1..1 aggregated sentiment*impact
    index_trend: Direction = Direction.NONE

    def tf(self, timeframe: str) -> Series | None:
        return self.series.get(timeframe)

    def has(self, timeframe: str, min_bars: int) -> bool:
        s = self.series.get(timeframe)
        return s is not None and len(s) >= min_bars


@dataclass(frozen=True, slots=True)
class StrategySignal:
    """A fully-reasoned candidate. Never a bare 'buy' — always explains itself."""

    strategy_key: str
    symbol: str
    direction: Direction
    entry: float
    stop: float
    targets: tuple[float, ...]
    confidence: float  # 0..1, calibrated by the strategy
    rationale: tuple[str, ...]  # human-readable "why" bullets
    expected_holding: str  # e.g. "intraday", "2-5 days", "2-4 weeks"
    tags: tuple[str, ...] = ()
    features: Mapping[str, float] = field(default_factory=dict)

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def reward_per_unit(self) -> float:
        if not self.targets:
            return 0.0
        return abs(self.targets[0] - self.entry)

    @property
    def risk_reward(self) -> float:
        risk = self.risk_per_unit
        return self.reward_per_unit / risk if risk > 0 else 0.0


@dataclass
class StrategyStats:
    """Rolling / backtested performance for one strategy (populated by backtests).

    Defaults are deliberately neutral so an un-backtested strategy neither helps
    nor unfairly penalizes its candidates; the scorer treats <MIN_SAMPLES as
    'unproven' and leans on live technical scores instead.
    """

    trades: int = 0
    wins: int = 0
    gross_win: float = 0.0
    gross_loss: float = 0.0
    avg_holding_bars: float = 0.0
    max_drawdown: float = 0.0
    false_positive_rate: float = 0.0

    MIN_SAMPLES: int = 30

    @property
    def win_rate(self) -> float:
        return self.wins / self.trades if self.trades else 0.0

    @property
    def profit_factor(self) -> float:
        return self.gross_win / self.gross_loss if self.gross_loss > 0 else 0.0

    @property
    def expectancy(self) -> float:
        """Average P&L per trade in R-multiples; 0 when unproven."""
        if self.trades < self.MIN_SAMPLES:
            return 0.0
        wr = self.win_rate
        avg_win = self.gross_win / self.wins if self.wins else 0.0
        losses = self.trades - self.wins
        avg_loss = self.gross_loss / losses if losses else 0.0
        return wr * avg_win - (1 - wr) * avg_loss

    @property
    def is_proven(self) -> bool:
        return self.trades >= self.MIN_SAMPLES


class Strategy(ABC):
    """Base class for all strategies. Subclasses are stateless and deterministic."""

    #: Stable identifier used in configs, stats and explanations.
    key: str = ""
    #: Human-readable name.
    name: str = ""
    #: One-line description of the edge.
    description: str = ""
    #: Regimes in which this strategy is allowed to fire.
    compatible_regimes: frozenset[MarketRegime] = frozenset()
    #: Minimum bars required on the primary timeframe.
    primary_timeframe: str = "5m"
    required_history: int = 20
    #: Typical holding horizon, surfaced in signals/explanations.
    expected_holding: str = "intraday"

    def __init__(self) -> None:
        if not self.key:
            raise ValueError(f"{type(self).__name__} must define a 'key'")
        self.stats = StrategyStats()

    def is_compatible(self, regimes: frozenset[MarketRegime]) -> bool:
        """True if the active regime set permits this strategy to fire."""
        if self.compatible_regimes and regimes:
            if not (self.compatible_regimes & regimes):
                return False
        return True

    def _ready(self, ctx: StrategyContext) -> bool:
        return ctx.has(self.primary_timeframe, self.required_history)

    @abstractmethod
    def evaluate(self, ctx: StrategyContext) -> StrategySignal | None:
        """Return a signal or ``None`` to abstain. Pure; no side effects."""

    def signal(
        self,
        ctx: StrategyContext,
        *,
        direction: Direction,
        entry: float,
        stop: float,
        targets: Sequence[float],
        confidence: float,
        rationale: Sequence[str],
        tags: Sequence[str] = (),
        features: Mapping[str, float] | None = None,
    ) -> StrategySignal:
        """Helper to build a well-formed signal with clamped confidence."""
        return StrategySignal(
            strategy_key=self.key,
            symbol=ctx.symbol,
            direction=direction,
            entry=round(entry, 4),
            stop=round(stop, 4),
            targets=tuple(round(t, 4) for t in targets),
            confidence=max(0.0, min(1.0, confidence)),
            rationale=tuple(rationale),
            expected_holding=self.expected_holding,
            tags=tuple(tags),
            features=dict(features or {}),
        )
