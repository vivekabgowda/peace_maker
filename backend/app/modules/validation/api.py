"""Validation REST endpoints (Sprint 14).

Read endpoints are available to any authenticated user; triggering a run is
admin-only (it backtests the whole library and can be expensive). Advisory —
nothing here trades.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status

from app.core.dependencies import CurrentUser, DbSession, RequireAdmin
from app.modules.users.models import User
from app.modules.validation.service import ValidationService

router = APIRouter(prefix="/validation", tags=["validation"])

AdminUser = Annotated[User, RequireAdmin]


@router.post("/run", summary="Run a cost-aware, out-of-sample validation over the library")
async def run_validation(
    _admin: AdminUser,
    session: DbSession,
    history: Annotated[int, Query(ge=50, le=5000)] = 400,
    folds: Annotated[int, Query(ge=2, le=12)] = 4,
) -> dict[str, Any]:
    result = await ValidationService(session).run(history=history, folds=folds)
    await session.commit()
    return result


@router.post("/monte-carlo", summary="Monte Carlo the net-of-cost trade sequence of a strategy")
async def monte_carlo_run(
    _admin: AdminUser,
    session: DbSession,
    strategy: Annotated[str, Query(min_length=1, max_length=64)],
    history: Annotated[int, Query(ge=50, le=5000)] = 400,
    simulations: Annotated[int, Query(ge=100, le=20000)] = 2000,
    method: Annotated[str, Query(pattern="^(resample|shuffle)$")] = "resample",
) -> dict[str, Any]:
    return await ValidationService(session).monte_carlo(
        strategy_key=strategy, history=history, simulations=simulations, method=method
    )


@router.get("/runs", summary="List recent validation runs")
async def list_runs(
    _user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    return {"runs": await ValidationService(session).list_runs(limit=limit)}


@router.get("/runs/{run_id}", summary="Get one validation run")
async def get_run(_user: CurrentUser, session: DbSession, run_id: int) -> dict[str, Any]:
    run = await ValidationService(session).get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Validation run not found"
        )
    return run
