"""Alpha Scanner engine (Sprint 3, Steps 3 & 5).

Orchestrates the pipeline over a universe of pre-built contexts:

    regime → (per instrument) enabled & compatible strategies → 11-factor score
    → explanation → Opportunity → rank → portfolio constraints → Top-N book

The engine is *pure orchestration* over provided data — no I/O — so the whole
Alpha Engine is unit-testable and identical in live scan and backtest. The
I/O-bound context assembly lives in :mod:`app.modules.scanner.context`.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

import app.modules.strategy.library  # noqa: F401  (ensures plugins are registered)
from app.core.logging import get_logger
from app.modules.ai_engine.scoring import PortfolioImpact, ScoringEngine
from app.modules.portfolio.awareness import Held, PortfolioManager
from app.modules.scanner.explain import build_explanation
from app.modules.scanner.opportunity import (
    Opportunity,
    OpportunityBook,
    rank_opportunities,
)
from app.modules.scanner.regime import RegimeEngine, RegimeState
from app.modules.strategy.base import Series, StrategyContext
from app.modules.strategy.registry import StrategyRegistry
from app.modules.strategy.registry import registry as default_registry

logger = get_logger("alpha_scanner")


@dataclass(frozen=True, slots=True)
class RegimeInputs:
    """Non-series inputs the regime engine needs (from the index/session)."""

    now: datetime | None = None
    prev_close: float | None = None
    day_open: float | None = None
    breadth: float | None = None
    global_risk_off: bool | None = None


class AlphaScanner:
    """The end-to-end scan orchestrator (pure over provided contexts)."""

    def __init__(
        self,
        *,
        registry: StrategyRegistry | None = None,
        scoring: ScoringEngine | None = None,
        regime_engine: RegimeEngine | None = None,
        portfolio: PortfolioManager | None = None,
    ) -> None:
        self._registry = registry or default_registry
        self._scoring = scoring or ScoringEngine()
        self._regime_engine = regime_engine or RegimeEngine()
        self._portfolio = portfolio or PortfolioManager()

    def scan(
        self,
        index_series: Series,
        contexts: list[StrategyContext],
        *,
        regime_inputs: RegimeInputs | None = None,
        held: list[Held] | None = None,
        top_n: int = 20,
        median_turnover: float | None = None,
    ) -> OpportunityBook:
        ri = regime_inputs or RegimeInputs()
        regime = self._regime_engine.detect(
            index_series,
            now=ri.now,
            prev_close=ri.prev_close,
            day_open=ri.day_open,
            breadth=ri.breadth,
            global_risk_off=ri.global_risk_off,
        )
        candidates = self._evaluate_universe(contexts, regime, median_turnover)

        book = rank_opportunities(
            candidates,
            regime,
            universe_size=len(contexts),
            scanned_strategies=len(self._registry.enabled()),
            generated_at=ri.now or datetime.now(UTC),
        )
        if book.no_trade:
            logger.info("scan_no_trade", reason=book.no_trade_reason, universe=len(contexts))
            return book

        # Portfolio awareness prunes correlated/over-concentrated ideas.
        pruned = self._portfolio.apply(book.opportunities, held=held or ())
        final = _reindex(pruned.accepted)
        logger.info(
            "scan_complete",
            universe=len(contexts),
            candidates=len(book.opportunities),
            accepted=len(final),
            regime=regime.primary.value,
        )
        return OpportunityBook(
            generated_at=book.generated_at,
            regime=regime,
            opportunities=tuple(final[:top_n]),
            universe_size=len(contexts),
            no_trade=len(final) == 0,
            no_trade_reason=None if final else "All candidates pruned by portfolio constraints.",
            rejected=book.rejected + len(pruned.dropped),
            scanned_strategies=book.scanned_strategies,
            warnings=book.warnings,
        )

    def regime_of(self, index_series: Series, inputs: RegimeInputs | None = None) -> RegimeState:
        ri = inputs or RegimeInputs()
        return self._regime_engine.detect(
            index_series,
            now=ri.now,
            prev_close=ri.prev_close,
            day_open=ri.day_open,
            breadth=ri.breadth,
            global_risk_off=ri.global_risk_off,
        )

    # -- Internals ----------------------------------------------------------
    def _evaluate_universe(
        self,
        contexts: list[StrategyContext],
        regime: RegimeState,
        median_turnover: float | None,
    ) -> list[Opportunity]:
        candidates: list[Opportunity] = []
        strategies = self._registry.enabled()
        for ctx in contexts:
            ctx_regime = _ctx_with_regime(ctx, regime)
            for strat in strategies:
                if not strat.is_compatible(regime.regimes):
                    continue
                try:
                    signal = strat.evaluate(ctx_regime)
                except Exception:  # a broken strategy must not sink the scan
                    logger.warning("strategy_error", strategy=strat.key, symbol=ctx.symbol)
                    continue
                if signal is None:
                    continue
                if ctx.sector:  # thread sector for portfolio concentration
                    signal = replace(signal, tags=(*signal.tags, f"sector:{ctx.sector}"))
                scorecard = self._scoring.score(
                    signal,
                    ctx_regime,
                    regime,
                    strategy_win_rate=strat.stats.win_rate if strat.stats.is_proven else None,
                    strategy_proven=strat.stats.is_proven,
                    portfolio=PortfolioImpact(),
                    median_turnover=median_turnover,
                )
                explanation = build_explanation(signal, ctx_regime, regime, scorecard, strat.name)
                candidates.append(
                    Opportunity(
                        symbol=ctx.symbol,
                        instrument_id=ctx.instrument_id,
                        strategy_key=strat.key,
                        strategy_name=strat.name,
                        signal=signal,
                        scorecard=scorecard,
                        explanation=explanation,
                    )
                )
        return candidates


def _ctx_with_regime(ctx: StrategyContext, regime: RegimeState) -> StrategyContext:
    """Inject the detected regime set + index trend into the context."""
    return replace(ctx, regimes=regime.regimes, index_trend=regime.index_trend)


def _reindex(opps: list[Opportunity]) -> list[Opportunity]:
    return [replace(o, rank=i + 1) for i, o in enumerate(opps)]
