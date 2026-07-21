"""AI Investment Committee REST endpoints (read-only, advisory)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.modules.committee.agents import DEFAULT_AGENTS
from app.modules.committee.service import CommitteeService

router = APIRouter(prefix="/committee", tags=["ai-committee"])


@router.get("/agents", summary="The committee roster")
async def agents(_user: CurrentUser) -> dict[str, list[dict[str, str]]]:
    return {"data": [{"role": cls.role.value, "name": cls.__name__} for cls in DEFAULT_AGENTS]}


@router.get("/review", summary="Convene the committee on the top (or a named) opportunity")
async def review(
    _user: CurrentUser,
    session: DbSession,
    symbol: Annotated[str | None, Query()] = None,
    fno: Annotated[bool, Query()] = False,
) -> dict[str, Any]:
    return await CommitteeService(session).deliberate(symbol=symbol, fno_only=fno)
