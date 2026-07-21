"""Committee service — assembles a brief from a live scan and deliberates.

Reuses the Alpha Engine end to end: build contexts → scan → rank, then convene
the committee on the chosen opportunity (the book's top pick, or a requested
symbol). Advisory only.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.committee.base import CommitteeBrief, PortfolioState
from app.modules.committee.committee import InvestmentCommittee
from app.modules.market_data.repository import MarketDataRepository
from app.modules.scanner.context import ContextBuilder
from app.modules.scanner.engine import AlphaScanner
from app.modules.strategy.base import StrategyContext

logger = get_logger("committee_service")


class CommitteeService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = MarketDataRepository(session)
        self._settings = get_settings()
        self._scanner = AlphaScanner()
        self._committee = InvestmentCommittee()

    async def deliberate(
        self,
        *,
        symbol: str | None = None,
        fno_only: bool = False,
        portfolio: PortfolioState | None = None,
    ) -> dict[str, Any]:
        built = await ContextBuilder(self._repo, benchmark=self._settings.alpha_benchmark).build(
            fno_only=fno_only
        )
        regime = self._scanner.regime_of(built.index_series, built.regime_inputs)
        book = self._scanner.scan(
            built.index_series,
            built.contexts,
            regime_inputs=built.regime_inputs,
            median_turnover=built.median_turnover,
        )

        if book.no_trade or not book.opportunities:
            return {
                "convened": False,
                "reason": book.no_trade_reason or "No qualifying opportunity to review.",
                "regime": {
                    "primary": regime.primary.value,
                    "is_hostile": regime.is_hostile,
                },
            }

        opportunity = _select(book.opportunities, symbol)
        if opportunity is None:
            return {
                "convened": False,
                "reason": f"No active opportunity for {symbol!r} in the current book.",
            }

        ctx = _context_for(built.contexts, opportunity.symbol)
        if ctx is None:  # should not happen — the opportunity came from a context
            return {
                "convened": False,
                "reason": "Context unavailable for the selected opportunity.",
            }

        brief = CommitteeBrief(
            opportunity=opportunity,
            context=ctx,
            regime=regime,
            book=book,
            portfolio=portfolio or PortfolioState(),
        )
        deliberation = self._committee.deliberate(brief)
        return {"convened": True, **deliberation.as_dict()}


def _select(opportunities: tuple[Any, ...], symbol: str | None) -> Any | None:
    if symbol is None:
        return opportunities[0]
    for opp in opportunities:
        if opp.symbol.upper() == symbol.upper():
            return opp
    return None


def _context_for(contexts: list[StrategyContext], symbol: str) -> StrategyContext | None:
    for c in contexts:
        if c.symbol == symbol:
            return c
    return None
