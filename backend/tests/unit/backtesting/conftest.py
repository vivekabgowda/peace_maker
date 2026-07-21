"""Isolate registry stats mutations to the backtesting tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.modules.strategy.base import StrategyStats
from app.modules.strategy.registry import registry


@pytest.fixture(autouse=True)
def _restore_registry_stats() -> Iterator[None]:
    """apply_to_registry mutates shared strategy .stats; reset after each test so
    other suites (alpha, committee) keep the default 'unproven' stats."""
    yield
    for strat in registry.all():
        strat.stats = StrategyStats()
