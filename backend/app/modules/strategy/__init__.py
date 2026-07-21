"""Strategy plugin subsystem for the Alpha Engine (Sprint 3).

Importing :mod:`app.modules.strategy.library` registers every strategy plugin
into :data:`registry`. Consumers (the scanner) depend only on the framework
contracts here, never on individual strategies.
"""

from __future__ import annotations

from app.modules.strategy.base import (
    Bar,
    Direction,
    OptionContext,
    Series,
    Strategy,
    StrategyContext,
    StrategySignal,
    StrategyStats,
)
from app.modules.strategy.regime_types import MarketRegime
from app.modules.strategy.registry import StrategyRegistry, register, registry

__all__ = [
    "Bar",
    "Direction",
    "MarketRegime",
    "OptionContext",
    "Series",
    "Strategy",
    "StrategyContext",
    "StrategyRegistry",
    "StrategySignal",
    "StrategyStats",
    "register",
    "registry",
]
