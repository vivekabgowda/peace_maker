"""Wire backtest results into the live strategy registry.

After a backtest run, calling :func:`apply_to_registry` replaces each strategy's
default (unproven) :class:`StrategyStats` with the earned numbers, so the live
scoring engine and the AI committee immediately weight proven strategies by their
real win rate and expectancy.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.modules.backtesting.models import BacktestResult
from app.modules.strategy.registry import StrategyRegistry
from app.modules.strategy.registry import registry as default_registry


def apply_to_registry(
    results: Iterable[BacktestResult], registry: StrategyRegistry | None = None
) -> list[str]:
    """Set each strategy's ``.stats`` from its backtest result. Returns updated keys."""
    reg = registry or default_registry
    updated: list[str] = []
    for result in results:
        if result.strategy_key not in reg.keys():
            continue
        reg.get(result.strategy_key).stats = result.to_stats()
        updated.append(result.strategy_key)
    return updated
