"""Alpha service — wires the repository-backed context builder to the scanner.

Thin async facade the API depends on. Applies the configured strategy allow-list
to the registry, assembles the universe, runs a scan, and returns the serialized
Opportunity Book. Keeps all orchestration in :class:`AlphaScanner` (pure).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.market_data.repository import MarketDataRepository
from app.modules.scanner.context import ContextBuilder
from app.modules.scanner.engine import AlphaScanner
from app.modules.strategy.registry import registry

logger = get_logger("alpha_service")


class AlphaService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MarketDataRepository(session)
        self._settings = get_settings()
        self._scanner = AlphaScanner()

    def _apply_enabled(self) -> None:
        enabled = self._settings.alpha_enabled_strategies
        if enabled:  # empty list ⇒ leave library defaults (all enabled)
            registry.set_enabled_keys(enabled)

    def strategies(self) -> list[dict[str, Any]]:
        """List every registered strategy with its metadata and enabled flag."""
        self._apply_enabled()
        return [
            {
                "key": s.key,
                "name": s.name,
                "description": s.description,
                "enabled": registry.is_enabled(s.key),
                "primary_timeframe": s.primary_timeframe,
                "expected_holding": s.expected_holding,
                "compatible_regimes": sorted(r.value for r in s.compatible_regimes),
                "stats": {
                    "trades": s.stats.trades,
                    "win_rate": round(s.stats.win_rate, 4),
                    "profit_factor": round(s.stats.profit_factor, 4),
                    "is_proven": s.stats.is_proven,
                },
            }
            for s in registry.all()
        ]

    async def scan(self, *, fno_only: bool = False, top_n: int = 20) -> dict[str, Any]:
        """Run a full universe scan and return the serialized opportunity book."""
        self._apply_enabled()
        built = await ContextBuilder(
            self._repo,
            benchmark=self._settings.alpha_benchmark,
        ).build(fno_only=fno_only)
        book = self._scanner.scan(
            built.index_series,
            built.contexts,
            regime_inputs=built.regime_inputs,
            top_n=top_n,
            median_turnover=built.median_turnover,
        )
        logger.info(
            "alpha_scan",
            universe=book.universe_size,
            no_trade=book.no_trade,
            candidates=len(book.opportunities),
        )
        return book.as_dict(top_n=top_n)

    async def regime(self) -> dict[str, Any]:
        """Return just the current market regime (cheap; index-only)."""
        built = await ContextBuilder(self._repo, benchmark=self._settings.alpha_benchmark).build()
        state = self._scanner.regime_of(built.index_series, built.regime_inputs)
        return {
            "primary": state.primary.value,
            "overlays": sorted(o.value for o in state.overlays),
            "confidence": state.confidence,
            "index_trend": state.index_trend.value,
            "is_hostile": state.is_hostile,
            "features": {k: round(v, 4) for k, v in state.features.items()},
        }
