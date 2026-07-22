"""Admin dashboard REST endpoints — all guarded by the admin role (RBAC).

Read-only operational views (system health, users, logs, audit) plus two
privileged mutations (change a user's role, edit the committee configuration),
both of which are recorded in the audit trail.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.core.dependencies import DbSession, RequireAdmin
from app.modules.admin.service import AdminService
from app.modules.users.models import User

router = APIRouter(prefix="/admin", tags=["admin"])

# ``RequireAdmin`` is already a ``Depends(...)`` marker enforcing the admin role.
AdminUser = Annotated[User, RequireAdmin]


class RoleUpdate(BaseModel):
    role: str = Field(min_length=1, max_length=16)


class AgentConfig(BaseModel):
    role: str
    enabled: bool = True
    weight: float = Field(ge=0.0, le=5.0)


class Thresholds(BaseModel):
    strong: float = Field(gt=0.0, lt=1.0)
    act: float = Field(gt=0.0, lt=1.0)


class CommitteeConfigUpdate(BaseModel):
    agents: list[AgentConfig]
    thresholds: Thresholds


@router.get("/system", summary="System health across all subsystems")
async def system(_admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await AdminService(session).system_health()


@router.get("/users", summary="List all users with roles and status")
async def users(_admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return {"users": await AdminService(session).users()}


@router.get("/permissions", summary="Role → permission matrix")
async def permissions(_admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return AdminService(session).permissions()


@router.patch("/users/{user_id}/role", summary="Change a user's role")
async def update_user_role(
    user_id: str, payload: RoleUpdate, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    result = await AdminService(session).update_user_role(
        user_id=user_id, new_role=payload.role, actor=admin
    )
    await session.commit()
    return result


@router.get("/committee/config", summary="Current AI committee configuration")
async def committee_config(_admin: AdminUser, session: DbSession) -> dict[str, Any]:
    return await AdminService(session).committee_config()


@router.put("/committee/config", summary="Update the AI committee configuration")
async def update_committee_config(
    payload: CommitteeConfigUpdate, admin: AdminUser, session: DbSession
) -> dict[str, Any]:
    result = await AdminService(session).update_committee_config(
        payload=payload.model_dump(), actor=admin
    )
    await session.commit()
    return result


@router.get("/logs", summary="Recent application logs (ring buffer)")
async def logs(
    _admin: AdminUser,
    session: DbSession,
    level: Annotated[str, Query(pattern="^(debug|info|warning|error|critical)$")] = "info",
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict[str, Any]:
    return {"logs": AdminService(session).logs(min_level=level, limit=limit)}


@router.get("/audit", summary="Privileged-action audit trail")
async def audit(
    _admin: AdminUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> dict[str, Any]:
    return {"audit": await AdminService(session).audit_trail(limit=limit)}
