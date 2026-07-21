"""Trade simulator conventions + result metric math."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.backtesting.models import BacktestResult, Trade, TradeOutcome
from app.modules.backtesting.simulator import simulate_trade
from app.modules.strategy.base import Bar, Direction, StrategySignal

TS = datetime(2026, 1, 5, tzinfo=UTC)


def _bar(i: int, o: float, h: float, low: float, c: float) -> Bar:
    return Bar(ts=TS + timedelta(days=i), open=o, high=h, low=low, close=c, volume=1000)


def _long(entry: float = 100.0, stop: float = 98.0, target: float = 104.0) -> StrategySignal:
    return StrategySignal(
        strategy_key="t",
        symbol="X",
        direction=Direction.LONG,
        entry=entry,
        stop=stop,
        targets=(target,),
        confidence=0.6,
        rationale=("r",),
        expected_holding="swing",
    )


def test_target_hit_is_a_win_with_positive_r() -> None:
    sig = _long()
    future = [_bar(1, 100, 101, 99, 100), _bar(2, 100, 105, 100, 104)]  # target 104 hit on bar 2
    trade = simulate_trade(sig, _bar(0, 100, 100, 100, 100), future)
    assert trade.outcome is TradeOutcome.WIN
    assert trade.exit == 104.0
    assert trade.r_multiple == 2.0  # (104-100)/(100-98)
    assert trade.holding_bars == 2


def test_stop_hit_is_a_loss_with_negative_r() -> None:
    sig = _long()
    future = [_bar(1, 100, 100.5, 97.5, 98)]  # low 97.5 breaches stop 98
    trade = simulate_trade(sig, _bar(0, 100, 100, 100, 100), future)
    assert trade.outcome is TradeOutcome.LOSS
    assert trade.r_multiple == -1.0


def test_ambiguous_bar_assumes_stop_first() -> None:
    sig = _long()
    future = [_bar(1, 100, 105, 97, 101)]  # spans both stop (98) and target (104)
    trade = simulate_trade(sig, _bar(0, 100, 100, 100, 100), future)
    assert trade.outcome is TradeOutcome.LOSS  # pessimistic: stop first
    assert trade.exit == 98.0


def test_time_stop_closes_at_last_bar() -> None:
    sig = _long()
    future = [_bar(i, 100, 101, 99, 100) for i in range(1, 4)]  # never hits stop/target
    trade = simulate_trade(sig, _bar(0, 100, 100, 100, 100), future, max_holding_bars=3)
    assert trade.outcome is TradeOutcome.TIMEOUT
    assert trade.holding_bars == 3


def test_short_r_multiple_sign() -> None:
    sig = StrategySignal(
        strategy_key="t",
        symbol="X",
        direction=Direction.SHORT,
        entry=100.0,
        stop=102.0,
        targets=(96.0,),
        confidence=0.6,
        rationale=("r",),
        expected_holding="swing",
    )
    future = [_bar(1, 100, 100, 95, 96)]  # low 95 hits short target 96
    trade = simulate_trade(sig, _bar(0, 100, 100, 100, 100), future)
    assert trade.outcome is TradeOutcome.WIN
    assert trade.r_multiple == 2.0  # (100-96)/(102-100)


def _trade(r_entry: float, r_exit: float, direction: Direction = Direction.LONG) -> Trade:
    return Trade(
        symbol="X",
        strategy_key="t",
        direction=direction,
        entry_ts=TS,
        entry=100.0,
        stop=98.0,
        target=104.0,
        exit_ts=TS + timedelta(days=1),
        exit=r_exit,
        holding_bars=3,
        outcome=TradeOutcome.WIN if r_exit > 100 else TradeOutcome.LOSS,
    )


def test_result_metrics() -> None:
    # 3 trades: +2R, +2R, -1R  → win_rate 2/3, PF 4/1, expectancy 1R
    res = BacktestResult(strategy_key="t")
    res.trades = [_trade(100, 104), _trade(100, 104), _trade(100, 98)]
    assert res.total == 3
    assert res.wins == 2
    assert round(res.win_rate, 3) == 0.667
    assert res.profit_factor == 4.0
    assert round(res.expectancy_r, 3) == 1.0
    assert res.false_positive_rate == round(1 / 3, 4) or abs(res.false_positive_rate - 1 / 3) < 1e-6
    assert res.max_drawdown_r == 1.0  # peak 4R, ends 3R
    assert res.equity_curve() == [2.0, 4.0, 3.0]


def test_to_stats_projects_into_live_container() -> None:
    res = BacktestResult(strategy_key="t")
    res.trades = [_trade(100, 104) for _ in range(20)] + [_trade(100, 98) for _ in range(20)]
    stats = res.to_stats()
    assert stats.trades == 40
    assert stats.is_proven  # >= 30 samples
    assert 0 < stats.win_rate < 1
