"""Backtest service — run the harness over stored candles and report metrics.

Loads historical candles from the market-data store, backtests one or every
enabled strategy on its primary timeframe, and (optionally) writes the earned
stats back into the live registry.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.backtesting.engine import BacktestConfig, Backtester
from app.modules.backtesting.models import BacktestResult
from app.modules.backtesting.stats import apply_to_registry
from app.modules.market_data.orm import Candle
from app.modules.market_data.repository import MarketDataRepository
from app.modules.strategy.base import Bar
from app.modules.strategy.registry import registry

logger = get_logger("backtest_service")


class BacktestService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MarketDataRepository(session)
        self._settings = get_settings()

    async def run(
        self,
        *,
        strategy_key: str | None = None,
        history: int = 400,
        apply_stats: bool = False,
    ) -> dict[str, Any]:
        instruments = await self._repo.list_instruments()
        benchmark_bars = await self._bars(
            _find_id(instruments, self._settings.alpha_benchmark), "1d", history
        )

        strategies = [registry.get(strategy_key)] if strategy_key else registry.enabled()
        backtester = Backtester(BacktestConfig())
        results: list[BacktestResult] = []
        for strat in strategies:
            tf = strat.primary_timeframe
            series_by_symbol: dict[str, list[Bar]] = {}
            for inst in instruments:
                if inst.symbol == self._settings.alpha_benchmark:
                    continue
                bars = await self._bars(inst.id, tf, history)
                if bars:
                    series_by_symbol[inst.symbol] = bars
            result = backtester.run(strat, series_by_symbol, benchmark=benchmark_bars)
            results.append(result)

        updated = apply_to_registry(results) if apply_stats else []
        logger.info(
            "backtest_run",
            strategies=len(results),
            trades=sum(r.total for r in results),
            applied=bool(apply_stats),
        )
        return {
            "results": [r.summary() for r in results],
            "stats_applied": updated,
        }

    async def _bars(self, instrument_id: int | None, timeframe: str, history: int) -> list[Bar]:
        if instrument_id is None:
            return []
        candles = await self._repo.recent_candles(instrument_id, timeframe, history)
        return [_to_bar(c) for c in candles]


def _to_bar(c: Candle) -> Bar:
    return Bar(
        ts=c.ts,
        open=float(c.open),
        high=float(c.high),
        low=float(c.low),
        close=float(c.close),
        volume=int(c.volume),
    )


def _find_id(instruments: list[Any], symbol: str) -> int | None:
    for inst in instruments:
        if inst.symbol == symbol:
            return int(inst.id)
    return None
