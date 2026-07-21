"""Trade simulation — turn a signal + future bars into a closed :class:`Trade`.

Conventions (documented so results are reproducible and honest):
- **No look-ahead.** Entry is the signal bar's close; exits are evaluated only on
  *subsequent* bars.
- **Stop-first.** If a single bar's range spans both the stop and the target, the
  stop is assumed hit first (the conservative, pessimistic assumption).
- **Time-stop.** If neither level is touched within ``max_holding_bars``, the
  trade is closed at that bar's close (outcome TIMEOUT).
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.backtesting.models import Trade, TradeOutcome
from app.modules.strategy.base import Bar, Direction, StrategySignal


def simulate_trade(
    signal: StrategySignal,
    entry_bar: Bar,
    future_bars: Sequence[Bar],
    *,
    max_holding_bars: int = 20,
) -> Trade:
    """Simulate one trade from ``signal`` using the bars that follow entry."""
    entry = signal.entry
    stop = signal.stop
    target = signal.targets[0] if signal.targets else entry
    long = signal.direction is Direction.LONG

    horizon = list(future_bars[:max_holding_bars])
    for i, bar in enumerate(horizon, start=1):
        hit_stop = bar.low <= stop if long else bar.high >= stop
        hit_target = bar.high >= target if long else bar.low <= target
        if hit_stop and hit_target:
            # Ambiguous bar → assume the stop resolved first.
            return _close(signal, entry_bar, bar, stop, i, target)
        if hit_stop:
            return _close(signal, entry_bar, bar, stop, i, target)
        if hit_target:
            return _close(signal, entry_bar, bar, target, i, target)

    # Time-stop: close at the last available bar's close.
    if horizon:
        last = horizon[-1]
        return _close(signal, entry_bar, last, last.close, len(horizon), target, timed=True)
    # No future bars — degenerate flat trade.
    return _close(signal, entry_bar, entry_bar, entry, 0, target, timed=True)


def _close(
    signal: StrategySignal,
    entry_bar: Bar,
    exit_bar: Bar,
    exit_price: float,
    holding_bars: int,
    target: float,
    *,
    timed: bool = False,
) -> Trade:
    long = signal.direction is Direction.LONG
    raw = (exit_price - signal.entry) if long else (signal.entry - exit_price)
    if timed:
        outcome = TradeOutcome.TIMEOUT
    elif raw > 0:
        outcome = TradeOutcome.WIN
    elif raw < 0:
        outcome = TradeOutcome.LOSS
    else:
        outcome = TradeOutcome.BREAKEVEN
    return Trade(
        symbol=signal.symbol,
        strategy_key=signal.strategy_key,
        direction=signal.direction,
        entry_ts=entry_bar.ts,
        entry=signal.entry,
        stop=signal.stop,
        target=target,
        exit_ts=exit_bar.ts,
        exit=exit_price,
        holding_bars=holding_bars,
        outcome=outcome,
    )
