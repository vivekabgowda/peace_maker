"""Performance analytics — the pure metrics core (Sprint 7).

Given a list of closed trades (:class:`TradeStat`), compute the standard trading
performance figures — win rate, profit factor, expectancy, payoff ratio, max
drawdown, and a daily-return Sharpe. No I/O; identical whether fed live journal
rows or a fixture, so every number is unit-tested against hand-worked cases.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class TradeStat:
    """The analytics view of one closed trade."""

    net_pnl: float
    r_multiple: float
    entry_ts: datetime
    exit_ts: datetime
    strategy_key: str | None
    symbol: str
    holding_seconds: int

    @property
    def is_win(self) -> bool:
        return self.net_pnl > 0

    @property
    def exit_day(self) -> date:
        return self.exit_ts.date()


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _stdev(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mu = _mean(xs)
    var = sum((x - mu) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


@dataclass(frozen=True, slots=True)
class DrawdownResult:
    max_drawdown: float  # currency, positive number
    max_drawdown_pct: float  # relative to the running peak equity


def equity_curve(trades: list[TradeStat], starting_equity: float) -> list[float]:
    """Cumulative equity after each trade (chronological by exit)."""
    ordered = sorted(trades, key=lambda t: t.exit_ts)
    equity = starting_equity
    curve = [round(equity, 2)]
    for t in ordered:
        equity += t.net_pnl
        curve.append(round(equity, 2))
    return curve


def max_drawdown(trades: list[TradeStat], starting_equity: float) -> DrawdownResult:
    curve = equity_curve(trades, starting_equity)
    peak = curve[0]
    max_dd = 0.0
    max_dd_pct = 0.0
    for equity in curve:
        peak = max(peak, equity)
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            max_dd_pct = (dd / peak * 100.0) if peak > 0 else 0.0
    return DrawdownResult(max_drawdown=round(max_dd, 2), max_drawdown_pct=round(max_dd_pct, 4))


def daily_pnl(trades: list[TradeStat]) -> dict[date, float]:
    out: dict[date, float] = {}
    for t in trades:
        out[t.exit_day] = out.get(t.exit_day, 0.0) + t.net_pnl
    return dict(sorted(out.items()))


def sharpe_ratio(trades: list[TradeStat], starting_equity: float, *, periods: int = 252) -> float:
    """Annualized Sharpe from daily returns (0 if <2 trading days or no vol)."""
    days = daily_pnl(trades)
    if len(days) < 2 or starting_equity <= 0:
        return 0.0
    returns = [pnl / starting_equity for pnl in days.values()]
    sd = _stdev(returns)
    if sd == 0:
        return 0.0
    return round(_mean(returns) / sd * math.sqrt(periods), 4)


@dataclass(frozen=True, slots=True)
class PerformanceMetrics:
    total_trades: int
    wins: int
    losses: int
    breakeven: int
    win_rate: float
    gross_profit: float
    gross_loss: float
    net_pnl: float
    profit_factor: float
    expectancy: float
    expectancy_r: float
    avg_win: float
    avg_loss: float
    payoff_ratio: float
    best_trade: float
    worst_trade: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float
    avg_holding_seconds: float
    return_pct: float
    starting_equity: float
    ending_equity: float
    equity_curve: list[float] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def compute(cls, trades: list[TradeStat], starting_equity: float) -> PerformanceMetrics:
        total = len(trades)
        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl < 0]
        breakeven = total - len(wins) - len(losses)
        gross_profit = sum(t.net_pnl for t in wins)
        gross_loss = -sum(t.net_pnl for t in losses)  # positive magnitude
        net = sum(t.net_pnl for t in trades)
        pnls = [t.net_pnl for t in trades]
        rs = [t.r_multiple for t in trades]
        dd = max_drawdown(trades, starting_equity)
        curve = equity_curve(trades, starting_equity)
        return cls(
            total_trades=total,
            wins=len(wins),
            losses=len(losses),
            breakeven=breakeven,
            win_rate=round(len(wins) / total, 4) if total else 0.0,
            gross_profit=round(gross_profit, 2),
            gross_loss=round(gross_loss, 2),
            net_pnl=round(net, 2),
            profit_factor=round(gross_profit / gross_loss, 4) if gross_loss > 0 else 0.0,
            expectancy=round(_mean(pnls), 4),
            expectancy_r=round(_mean(rs), 4),
            avg_win=round(_mean([t.net_pnl for t in wins]), 2),
            avg_loss=round(_mean([t.net_pnl for t in losses]), 2),
            payoff_ratio=(
                round(_mean([t.net_pnl for t in wins]) / abs(_mean([t.net_pnl for t in losses])), 4)
                if losses and _mean([t.net_pnl for t in losses]) != 0
                else 0.0
            ),
            best_trade=round(max(pnls), 2) if pnls else 0.0,
            worst_trade=round(min(pnls), 2) if pnls else 0.0,
            max_drawdown=dd.max_drawdown,
            max_drawdown_pct=dd.max_drawdown_pct,
            sharpe=sharpe_ratio(trades, starting_equity),
            avg_holding_seconds=round(_mean([float(t.holding_seconds) for t in trades]), 1),
            return_pct=round(net / starting_equity * 100.0, 4) if starting_equity else 0.0,
            starting_equity=round(starting_equity, 2),
            ending_equity=round(starting_equity + net, 2),
            equity_curve=curve,
        )


def by_strategy(trades: list[TradeStat], starting_equity: float) -> dict[str, dict[str, object]]:
    """Per-strategy performance breakdown (equity is attributed pro-rata is not
    meaningful, so each strategy's metrics use the same starting equity as a
    common base for return_pct comparability)."""
    groups: dict[str, list[TradeStat]] = {}
    for t in trades:
        groups.setdefault(t.strategy_key or "unknown", []).append(t)
    return {
        key: PerformanceMetrics.compute(group, starting_equity).as_dict()
        for key, group in sorted(groups.items())
    }
