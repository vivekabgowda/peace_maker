"""Backtesting REST endpoints (read-only; optionally updates live stats)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.modules.backtesting.service import BacktestService

router = APIRouter(prefix="/backtest", tags=["backtesting"])


@router.get("/run", summary="Backtest one or all strategies over stored candles")
async def run(
    _user: CurrentUser,
    session: DbSession,
    strategy: Annotated[str | None, Query()] = None,
    history: Annotated[int, Query(ge=60, le=2000)] = 400,
    apply_stats: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    return await BacktestService(session).run(
        strategy_key=strategy, history=history, apply_stats=apply_stats
    )
