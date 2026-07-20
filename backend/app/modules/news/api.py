"""News REST endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from app.core.dependencies import CurrentUser, DbSession
from app.modules.news.service import NewsService
from fastapi import APIRouter, Query

router = APIRouter(prefix="/news", tags=["news"])


@router.get("", summary="Recent normalized news")
async def recent_news(
    _user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, list[dict[str, Any]]]:
    return {"data": await NewsService(session).list_recent(limit=limit)}
