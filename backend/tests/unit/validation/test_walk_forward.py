"""Tests for the cost-aware, out-of-sample walk-forward layer (Sprint 14)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.modules.backtesting.models import Trade, TradeOutcome
from app.modules.paper_trading.costs import IndianCostModel, Segment, SlippageModel
from app.modules.strategy.base import Direction
from app.modules.validation.walk_forward import (
    cost_in_r,
    net_r_series,
    roundtrip_cost_bps,
    walk_forward,
)

_T0 = datetime(2024, 1, 1, tzinfo=UTC)


def _trade(i: int, *, entry: float, stop: float, exit_: float) -> Trade:
    return Trade(
        symbol="ACME",
        strategy_key="demo",
        direction=Direction.LONG,
        entry_ts=_T0 + timedelta(days=i),
        entry=entry,
        stop=stop,
        target=entry + 2 * (entry - stop),
        exit_ts=_T0 + timedelta(days=i, hours=1),
        exit=exit_,
        holding_bars=5,
        outcome=TradeOutcome.WIN if exit_ > entry else TradeOutcome.LOSS,
    )


def test_roundtrip_cost_bps_positive() -> None:
    bps = roundtrip_cost_bps(
        cost_model=IndianCostModel(),
        slippage=SlippageModel(),
        notional=100_000.0,
        segment=Segment.EQUITY_INTRADAY,
    )
    assert bps > 0.0


def test_cost_in_r_scales_inversely_with_stop_distance() -> None:
    # Same entry, tighter stop (smaller risk_per_unit) => larger cost in R.
    wide = _trade(0, entry=100.0, stop=90.0, exit_=110.0)  # risk 10
    tight = _trade(0, entry=100.0, stop=99.0, exit_=110.0)  # risk 1
    assert cost_in_r(tight, roundtrip_bps=50.0) > cost_in_r(wide, roundtrip_bps=50.0)


def test_net_r_is_below_gross() -> None:
    trades = [_trade(i, entry=100.0, stop=95.0, exit_=105.0) for i in range(10)]
    net = net_r_series(trades, roundtrip_bps=30.0)
    assert all(n < t.r_multiple for n, t in zip(net, trades, strict=True))


def test_walk_forward_report_structure_and_cost_drag() -> None:
    # 20 winners of +1R gross; costs must produce a positive drag and net < gross.
    trades = [_trade(i, entry=100.0, stop=95.0, exit_=105.0) for i in range(20)]
    rep = walk_forward(trades, roundtrip_bps=40.0, folds=4)
    assert rep["n_trades"] == 20
    assert rep["gross_expectancy_r"] == pytest.approx(1.0, abs=1e-9)
    assert rep["net_expectancy_r"] < rep["gross_expectancy_r"]
    assert rep["cost_drag_r"] > 0
    assert len(rep["folds"]) == 4
    assert rep["oos_consistency"] == pytest.approx(1.0)  # every fold still positive


def test_walk_forward_flags_insignificant_when_mixed() -> None:
    trades = []
    for i in range(20):
        if i % 2 == 0:
            trades.append(_trade(i, entry=100.0, stop=95.0, exit_=105.0))  # +1R
        else:
            trades.append(_trade(i, entry=100.0, stop=95.0, exit_=95.0))  # -1R
    rep = walk_forward(trades, roundtrip_bps=30.0, folds=4)
    assert rep["verdict_significant"] is False
    assert rep["net_expectancy_r"] < 0  # costs push a coin-flip negative


def test_walk_forward_handles_few_trades() -> None:
    rep = walk_forward(
        [_trade(0, entry=100.0, stop=95.0, exit_=105.0)], roundtrip_bps=30.0, folds=4
    )
    assert rep["n_trades"] == 1
    assert rep["folds"] == []  # not enough to fold
