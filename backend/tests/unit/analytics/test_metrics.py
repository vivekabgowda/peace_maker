"""Unit tests for the pure analytics metrics (hand-worked cases)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.modules.analytics.metrics import (
    PerformanceMetrics,
    TradeStat,
    by_strategy,
    daily_pnl,
    equity_curve,
    max_drawdown,
    sharpe_ratio,
)

BASE = datetime(2026, 1, 5, 10, 0, tzinfo=UTC)  # a Monday


def _trade(
    net: float, r: float, *, day_offset: int = 0, strategy: str = "orb", symbol: str = "TCS"
) -> TradeStat:
    exit_ts = BASE + timedelta(days=day_offset, hours=1)
    return TradeStat(
        net_pnl=net,
        r_multiple=r,
        entry_ts=BASE + timedelta(days=day_offset),
        exit_ts=exit_ts,
        strategy_key=strategy,
        symbol=symbol,
        holding_seconds=3600,
    )


def test_empty_is_all_zeros_no_div_by_zero() -> None:
    m = PerformanceMetrics.compute([], 100_000.0)
    assert m.total_trades == 0
    assert m.win_rate == 0.0
    assert m.profit_factor == 0.0
    assert m.net_pnl == 0.0
    assert m.max_drawdown == 0.0
    assert m.sharpe == 0.0
    assert m.equity_curve == [100_000.0]


def test_core_metrics_hand_worked() -> None:
    # 3 wins (+200,+300,+100), 2 losses (-100,-150).
    trades = [
        _trade(200, 2.0, day_offset=0),
        _trade(-100, -1.0, day_offset=1),
        _trade(300, 3.0, day_offset=2),
        _trade(-150, -1.5, day_offset=3),
        _trade(100, 1.0, day_offset=4),
    ]
    m = PerformanceMetrics.compute(trades, 100_000.0)
    assert m.total_trades == 5
    assert m.wins == 3 and m.losses == 2 and m.breakeven == 0
    assert m.win_rate == pytest.approx(0.6)
    assert m.gross_profit == pytest.approx(600.0)
    assert m.gross_loss == pytest.approx(250.0)
    assert m.net_pnl == pytest.approx(350.0)
    assert m.profit_factor == pytest.approx(2.4)
    assert m.expectancy == pytest.approx(70.0)
    assert m.expectancy_r == pytest.approx(0.7)
    assert m.avg_win == pytest.approx(200.0)
    assert m.avg_loss == pytest.approx(-125.0)
    assert m.payoff_ratio == pytest.approx(1.6)
    assert m.best_trade == 300.0 and m.worst_trade == -150.0
    assert m.return_pct == pytest.approx(0.35)
    assert m.ending_equity == pytest.approx(100_350.0)


def test_equity_curve_and_drawdown() -> None:
    # +100, -300, +50 -> curve 1000,1100,800,850. Peak 1100, trough 800 -> dd 300.
    trades = [
        _trade(100, 1, day_offset=0),
        _trade(-300, -3, day_offset=1),
        _trade(50, 0.5, day_offset=2),
    ]
    curve = equity_curve(trades, 1000.0)
    assert curve == [1000.0, 1100.0, 800.0, 850.0]
    dd = max_drawdown(trades, 1000.0)
    assert dd.max_drawdown == pytest.approx(300.0)
    assert dd.max_drawdown_pct == pytest.approx(300.0 / 1100.0 * 100.0, abs=1e-3)


def test_daily_pnl_groups_by_exit_day() -> None:
    trades = [
        _trade(100, 1, day_offset=0),
        _trade(50, 0.5, day_offset=0),
        _trade(-30, -0.3, day_offset=1),
    ]
    series = daily_pnl(trades)
    days = list(series.items())
    assert days[0][1] == pytest.approx(150.0)
    assert days[1][1] == pytest.approx(-30.0)


def test_sharpe_zero_without_two_days_or_vol() -> None:
    assert sharpe_ratio([_trade(100, 1)], 100_000.0) == 0.0
    # Two days, identical returns -> zero volatility -> Sharpe 0.
    flat = [_trade(100, 1, day_offset=0), _trade(100, 1, day_offset=1)]
    assert sharpe_ratio(flat, 100_000.0) == 0.0


def test_sharpe_positive_for_upward_variable_returns() -> None:
    trades = [
        _trade(100, 1, day_offset=0),
        _trade(300, 3, day_offset=1),
        _trade(50, 0.5, day_offset=2),
    ]
    assert sharpe_ratio(trades, 100_000.0) > 0.0


def test_by_strategy_breakdown() -> None:
    trades = [
        _trade(200, 2, strategy="orb"),
        _trade(-100, -1, strategy="orb", day_offset=1),
        _trade(300, 3, strategy="vwap", day_offset=2),
    ]
    out = by_strategy(trades, 100_000.0)
    assert set(out) == {"orb", "vwap"}
    assert out["orb"]["total_trades"] == 2
    assert out["vwap"]["net_pnl"] == pytest.approx(300.0)
