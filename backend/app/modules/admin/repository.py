"""Admin repository — the only place that talks to the admin tables."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.admin.orm import AuditLog, CommitteeConfig
from app.modules.users.models import User

_CONFIG_ID = 1


class AdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- Users --------------------------------------------------------------
    async def list_users(self) -> list[User]:
        stmt = select(User).order_by(User.created_at)
        return list((await self._session.scalars(stmt)).all())

    async def get_user(self, user_id: str | uuid.UUID) -> User | None:
        as_uuid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
        return await self._session.get(User, as_uuid)

    # -- Committee config ---------------------------------------------------
    async def get_committee_config(self) -> dict[str, Any] | None:
        row = await self._session.get(CommitteeConfig, _CONFIG_ID)
        return dict(row.config) if row and row.config else None

    async def set_committee_config(self, config: dict[str, Any]) -> None:
        row = await self._session.get(CommitteeConfig, _CONFIG_ID)
        if row is None:
            self._session.add(CommitteeConfig(id=_CONFIG_ID, config=config))
        else:
            row.config = config
        await self._session.flush()

    # -- Audit trail --------------------------------------------------------
    async def add_audit(
        self,
        *,
        actor_id: str | None,
        actor_email: str | None,
        action: str,
        target: str | None,
        detail: dict[str, Any],
    ) -> None:
        self._session.add(
            AuditLog(
                actor_id=actor_id,
                actor_email=actor_email,
                action=action,
                target=target,
                detail=detail,
            )
        )
        await self._session.flush()

    async def list_audit(self, limit: int = 100) -> list[AuditLog]:
        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        return list((await self._session.scalars(stmt)).all())
