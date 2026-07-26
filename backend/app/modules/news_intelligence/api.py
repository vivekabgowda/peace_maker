"""News Intelligence REST endpoints (Sprint 11 pt.2).

The single API the Scanner, Journal, and Analytics call for a symbol's news
research — never re-processing raw articles themselves.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.modules.news_intelligence.service import NewsIntelligenceService

router = APIRouter(prefix="/news-intelligence", tags=["news-intelligence"])


@router.get("/{symbol}", summary="Latest news assessment for a symbol")
async def latest_assessment(_user: CurrentUser, session: DbSession, symbol: str) -> dict[str, Any]:
    return await NewsIntelligenceService(session).latest_or_assess(symbol.upper())


@router.post("/{symbol}/assess", summary="Compute a fresh news assessment now")
async def assess(_user: CurrentUser, session: DbSession, symbol: str) -> dict[str, Any]:
    assessment = await NewsIntelligenceService(session).assess(symbol.upper())
    await session.commit()
    return assessment.as_dict()


@router.get("/{symbol}/history", summary="Historical assessments (for analytics)")
async def history(
    _user: CurrentUser,
    session: DbSession,
    symbol: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, list[dict[str, Any]]]:
    return {"data": await NewsIntelligenceService(session).history(symbol.upper(), limit=limit)}
