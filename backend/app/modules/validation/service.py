"""Validation service — cost-aware, statistically-honest strategy evaluation.

Runs the backtester over the strategy library on stored candles, applies
realistic Indian costs + slippage, evaluates each strategy out-of-sample, and
corrects for multiple testing across the library. Persists a ``ValidationRun``.

This is the operational answer to the CIO due-diligence report: it does not
assert an edge — it measures whether one survives costs and scrutiny.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.modules.backtesting.service import BacktestService
from app.modules.paper_trading.costs import IndianCostModel, Segment, SlippageModel
from app.modules.validation.monte_carlo import monte_carlo
from app.modules.validation.multiple_testing import benjamini_hochberg
from app.modules.validation.orm import ValidationRun
from app.modules.validation.walk_forward import net_r_series, roundtrip_cost_bps, walk_forward

logger = get_logger("validation_service")


def _segment(value: str) -> Segment:
    try:
        return Segment(value)
    except ValueError:
        return Segment.EQUITY_INTRADAY


class ValidationService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    async def run(
        self,
        *,
        history: int = 400,
        folds: int = 4,
        notional: float | None = None,
        segment: str | None = None,
    ) -> dict[str, Any]:
        settings = self._settings
        seg = _segment(segment or settings.paper_default_segment)
        ref_notional = notional if notional is not None else settings.validation_reference_notional

        roundtrip_bps = roundtrip_cost_bps(
            cost_model=IndianCostModel(),
            slippage=SlippageModel(base_spread_bps=settings.paper_slippage_bps * 2),
            notional=ref_notional,
            segment=seg,
        )

        results = await BacktestService(self._session).run_results(history=history)
        n_strats = len(results)

        strategies: list[dict[str, Any]] = []
        pvalues: list[tuple[str, float]] = []
        for res in results:
            wf = walk_forward(
                res.trades, roundtrip_bps=roundtrip_bps, folds=folds, n_trials=n_strats
            )
            # p-value for "true net Sharpe <= 0" ≈ 1 - PSR (probability SR > 0).
            sharpe_doc = wf["sharpe"]
            psr = (
                float(sharpe_doc.get("psr", 0.0))
                if res.trades and isinstance(sharpe_doc, dict)
                else 0.0
            )
            p = max(0.0, min(1.0, 1.0 - psr))
            pvalues.append((res.strategy_key, p))
            strategies.append(
                {
                    "strategy": res.strategy_key,
                    "trades": res.total,
                    "is_proven": res.total >= 30,
                    "walk_forward": wf,
                    "p_value": round(p, 6),
                }
            )

        corrected = {r.label: r for r in benjamini_hochberg(pvalues, alpha=0.05)}
        for s in strategies:
            c = corrected.get(s["strategy"])
            s["significant_after_correction"] = bool(c.reject) if c else False
            s["q_value"] = round(c.adjusted, 6) if c else 1.0

        survivors = [s["strategy"] for s in strategies if s["significant_after_correction"]]
        results_doc = {
            "roundtrip_cost_bps": round(roundtrip_bps, 4),
            "segment": seg.value,
            "reference_notional": ref_notional,
            "strategies_evaluated": n_strats,
            "survivors": survivors,
            "strategies": strategies,
        }
        params = {"history": history, "folds": folds}

        run = ValidationRun(kind="walk_forward", params=params, results=results_doc)
        self._session.add(run)
        await self._session.flush()

        logger.info(
            "validation_run",
            strategies=n_strats,
            survivors=len(survivors),
            roundtrip_bps=round(roundtrip_bps, 2),
        )
        return {"id": run.id, "created_at": run.created_at.isoformat(), **results_doc}

    async def monte_carlo(
        self,
        *,
        strategy_key: str,
        history: int = 400,
        simulations: int = 2000,
        method: str = "resample",
    ) -> dict[str, Any]:
        """Monte Carlo the net-of-cost trade sequence of one strategy."""
        settings = self._settings
        seg = _segment(settings.paper_default_segment)
        roundtrip_bps = roundtrip_cost_bps(
            cost_model=IndianCostModel(),
            slippage=SlippageModel(base_spread_bps=settings.paper_slippage_bps * 2),
            notional=settings.validation_reference_notional,
            segment=seg,
        )
        results = await BacktestService(self._session).run_results(
            strategy_key=strategy_key, history=history
        )
        trades = results[0].trades if results else []
        net = net_r_series(trades, roundtrip_bps=roundtrip_bps)
        sim = monte_carlo(net, simulations=simulations, method=method)
        return {
            "strategy": strategy_key,
            "roundtrip_cost_bps": round(roundtrip_bps, 4),
            "units": "R (per-trade risk multiples), net of costs",
            **sim.as_dict(),
        }

    async def list_runs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        stmt = select(ValidationRun).order_by(ValidationRun.created_at.desc()).limit(limit)
        rows = (await self._session.scalars(stmt)).all()
        return [
            {
                "id": r.id,
                "kind": r.kind,
                "created_at": r.created_at.isoformat(),
                "strategies_evaluated": r.results.get("strategies_evaluated"),
                "survivors": r.results.get("survivors", []),
            }
            for r in rows
        ]

    async def get_run(self, run_id: int) -> dict[str, Any] | None:
        row = await self._session.get(ValidationRun, run_id)
        if row is None:
            return None
        return {
            "id": row.id,
            "kind": row.kind,
            "created_at": row.created_at.isoformat(),
            "params": row.params,
            **row.results,
        }
