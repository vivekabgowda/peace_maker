"""Health and readiness endpoints.

- ``/health/live``  — liveness: the process is up (no dependencies checked).
- ``/health/ready`` — readiness: database and Redis are reachable.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.redis import ping_redis

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    checks: dict[str, bool]


async def _check_database() -> bool:
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@router.get("/live", response_model=LivenessResponse, summary="Liveness probe")
async def liveness() -> LivenessResponse:
    return LivenessResponse(version=get_settings().version)


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def readiness(response: Response) -> ReadinessResponse:
    checks = {"database": await _check_database(), "redis": await ping_redis()}
    ready = all(checks.values())
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="ready" if ready else "degraded", checks=checks)
