"""Backtesting subsystem (Sprint 5).

Replays the strategy plugins over historical bars to produce honest, per-strategy
performance metrics, then feeds them back into the live registry so scoring and
the AI committee weight proven strategies by their earned edge.
"""

from __future__ import annotations

from app.modules.backtesting.engine import BacktestConfig, Backtester
from app.modules.backtesting.models import BacktestResult, Trade, TradeOutcome
from app.modules.backtesting.simulator import simulate_trade
from app.modules.backtesting.stats import apply_to_registry

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "Backtester",
    "Trade",
    "TradeOutcome",
    "apply_to_registry",
    "simulate_trade",
]
