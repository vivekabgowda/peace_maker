"""Backtest domain — trades and aggregated results (Sprint 5).

A backtest replays a strategy over historical bars and records the trades it would
have taken. Results roll up into the same :class:`StrategyStats` the live scoring
engine and the committee already consume — so backtesting a strategy makes its
live confidence *earned* rather than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.modules.strategy.base import Direction, StrategyStats


class TradeOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    TIMEOUT = "timeout"  # closed by the time-stop, neither target nor stop hit


@dataclass(frozen=True, slots=True)
class Trade:
    """One simulated round-trip."""

    symbol: str
    strategy_key: str
    direction: Direction
    entry_ts: datetime
    entry: float
    stop: float
    target: float
    exit_ts: datetime
    exit: float
    holding_bars: int
    outcome: TradeOutcome

    @property
    def risk_per_unit(self) -> float:
        return abs(self.entry - self.stop)

    @property
    def r_multiple(self) -> float:
        """P&L in units of initial risk (R). Direction-adjusted."""
        risk = self.risk_per_unit
        if risk <= 0:
            return 0.0
        long = self.direction is Direction.LONG
        raw = (self.exit - self.entry) if long else (self.entry - self.exit)
        return raw / risk

    @property
    def is_win(self) -> bool:
        return self.r_multiple > 0

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "strategy": self.strategy_key,
            "direction": self.direction.value,
            "entry_ts": self.entry_ts.isoformat(),
            "entry": round(self.entry, 4),
            "stop": round(self.stop, 4),
            "target": round(self.target, 4),
            "exit_ts": self.exit_ts.isoformat(),
            "exit": round(self.exit, 4),
            "holding_bars": self.holding_bars,
            "r_multiple": round(self.r_multiple, 4),
            "outcome": self.outcome.value,
        }


@dataclass
class BacktestResult:
    """Aggregated performance for one strategy over one universe/period."""

    strategy_key: str
    trades: list[Trade] = field(default_factory=list)
    bars_tested: int = 0
    symbols_tested: int = 0

    # -- Core metrics -------------------------------------------------------
    @property
    def total(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.is_win)

    @property
    def losses(self) -> int:
        return sum(1 for t in self.trades if t.r_multiple < 0)

    @property
    def win_rate(self) -> float:
        return self.wins / self.total if self.total else 0.0

    @property
    def gross_win_r(self) -> float:
        return sum(t.r_multiple for t in self.trades if t.r_multiple > 0)

    @property
    def gross_loss_r(self) -> float:
        return sum(-t.r_multiple for t in self.trades if t.r_multiple < 0)

    @property
    def profit_factor(self) -> float:
        return self.gross_win_r / self.gross_loss_r if self.gross_loss_r > 0 else 0.0

    @property
    def expectancy_r(self) -> float:
        """Average R per trade — the strategy's edge."""
        return sum(t.r_multiple for t in self.trades) / self.total if self.total else 0.0

    @property
    def avg_holding_bars(self) -> float:
        return sum(t.holding_bars for t in self.trades) / self.total if self.total else 0.0

    @property
    def false_positive_rate(self) -> float:
        """Share of signals that were losers or stopped-out timeouts — the
        engine's discipline metric (a low value means few bad triggers)."""
        if not self.total:
            return 0.0
        bad = sum(
            1
            for t in self.trades
            if t.r_multiple < 0 or (t.outcome is TradeOutcome.TIMEOUT and t.r_multiple <= 0)
        )
        return bad / self.total

    @property
    def max_drawdown_r(self) -> float:
        """Peak-to-trough of the cumulative-R equity curve."""
        peak = 0.0
        equity = 0.0
        max_dd = 0.0
        for t in self.trades:
            equity += t.r_multiple
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        return max_dd

    def equity_curve(self) -> list[float]:
        curve: list[float] = []
        equity = 0.0
        for t in self.trades:
            equity += t.r_multiple
            curve.append(round(equity, 4))
        return curve

    def to_stats(self) -> StrategyStats:
        """Project into the live :class:`StrategyStats` container."""
        stats = StrategyStats(
            trades=self.total,
            wins=self.wins,
            gross_win=self.gross_win_r,
            gross_loss=self.gross_loss_r,
            avg_holding_bars=self.avg_holding_bars,
            max_drawdown=self.max_drawdown_r,
            false_positive_rate=self.false_positive_rate,
        )
        return stats

    def summary(self) -> dict[str, object]:
        return {
            "strategy": self.strategy_key,
            "trades": self.total,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "expectancy_r": round(self.expectancy_r, 4),
            "avg_holding_bars": round(self.avg_holding_bars, 2),
            "max_drawdown_r": round(self.max_drawdown_r, 4),
            "false_positive_rate": round(self.false_positive_rate, 4),
            "is_proven": self.total >= StrategyStats.MIN_SAMPLES,
            "symbols_tested": self.symbols_tested,
            "bars_tested": self.bars_tested,
        }
