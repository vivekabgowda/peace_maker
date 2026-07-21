"""Alpha Engine REST endpoints (read-only, advisory).

Exposes the current market regime, the strategy library, and the ranked
Opportunity Book. Advisory only — nothing here places orders.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.modules.scanner.service import AlphaService

router = APIRouter(prefix="/alpha", tags=["alpha-engine"])


@router.get("/regime", summary="Current market regime")
async def regime(_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return await AlphaService(session).regime()


@router.get("/strategies", summary="Registered strategy library + stats")
async def strategies(_user: CurrentUser, session: DbSession) -> dict[str, list[dict[str, Any]]]:
    return {"data": AlphaService(session).strategies()}


@router.get("/opportunities", summary="Ranked opportunity book (Top-N)")
async def opportunities(
    _user: CurrentUser,
    session: DbSession,
    fno: Annotated[bool, Query()] = False,
    top: Annotated[int, Query(ge=1, le=50)] = 20,
) -> dict[str, Any]:
    return await AlphaService(session).scan(fno_only=fno, top_n=top)
