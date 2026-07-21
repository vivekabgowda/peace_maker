"""Health and readiness endpoints.

- ``/health/live``  — liveness: the process is up (no dependencies checked).
- ``/health/ready`` — readiness: database and Redis are reachable.
- ``/health/diagnostics`` — full system diagnostics (all subsystems), powering
  the frontend diagnostics page (Sprint 8).
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.redis import ping_redis
from app.modules.health.diagnostics import gather_diagnostics

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


@router.get("/diagnostics", summary="Full system diagnostics (all subsystems)")
async def diagnostics(response: Response) -> dict[str, Any]:
    """Aggregate live status of the database, Redis, market feed, and event
    stream. Unauthenticated (operational health only, no secrets) so the
    diagnostics page works on a fresh machine before login. Returns 503 when a
    core dependency is down."""
    report = await gather_diagnostics()
    if report.get("status") != "healthy":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return report
