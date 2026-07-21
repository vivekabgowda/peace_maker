"""Trade-journal REST endpoints (Sprint 7, read + annotate)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.dependencies import CurrentUser, DbSession
from app.modules.journal.service import JournalService

router = APIRouter(prefix="/journal", tags=["journal"])


class AnnotateRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = None


@router.get("/entries", summary="List closed-trade journal entries")
async def list_entries(
    _user: CurrentUser,
    session: DbSession,
    strategy: Annotated[str | None, Query()] = None,
    symbol: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
) -> dict[str, Any]:
    entries = await JournalService(session).list_entries(
        strategy_key=strategy, symbol=symbol, limit=limit
    )
    return {"count": len(entries), "entries": [e.as_dict() for e in entries]}


@router.get("/entries/{entry_id}", summary="Get one journal entry")
async def get_entry(_user: CurrentUser, session: DbSession, entry_id: int) -> dict[str, Any]:
    record = await JournalService(session).get(entry_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    return record.as_dict()


@router.patch("/entries/{entry_id}", summary="Add notes / tags to a journal entry")
async def annotate_entry(
    _user: CurrentUser, session: DbSession, entry_id: int, body: AnnotateRequest
) -> dict[str, Any]:
    record = await JournalService(session).annotate(entry_id, notes=body.notes, tags=body.tags)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found")
    await session.commit()
    return record.as_dict()
