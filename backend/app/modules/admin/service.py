"""Admin service — aggregates real operational data for the Admin dashboard.

Every value served here is real: system health from live subsystem checks, users
from the identity table, committee config from persisted operator overrides
(applied by the committee at deliberation time), logs from the in-process ring
buffer, and the audit trail from the audit table. No mock data.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationAppError
from app.core.logging import recent_logs
from app.modules.admin.permissions import ROLE_PERMISSIONS, default_committee_config
from app.modules.admin.repository import AdminRepository
from app.modules.health.diagnostics import gather_diagnostics
from app.modules.users.models import User, UserRole
from app.shared.events.bus import event_bus
from app.websocket.gateway import manager as ws_manager

_VALID_ROLES = {r.value for r in UserRole}


class AdminService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = AdminRepository(session)

    # -- System health ------------------------------------------------------
    async def system_health(self) -> dict[str, Any]:
        report = await gather_diagnostics()
        raw_services = report.get("services", [])
        services: list[Any] = list(raw_services) if isinstance(raw_services, list) else []

        # WebSocket gateway: in-process, so it is up whenever the API is; the
        # meaningful signal is the live client count.
        clients = ws_manager.client_count
        services.append(
            {
                "name": "websocket",
                "kind": "realtime gateway",
                "healthy": True,
                "detail": f"{clients} client(s) connected",
                "latency_ms": None,
                "meta": {"clients": clients},
            }
        )

        # Queue / event bus health from real bus stats.
        stats = event_bus.stats
        queue_healthy = stats.dead_letters == 0
        services.append(
            {
                "name": "event_queue",
                "kind": "in-process event bus",
                "healthy": queue_healthy,
                "detail": (
                    f"{stats.subscribers} subscriber(s), {stats.published} published"
                    + (f", {stats.dead_letters} dead-letter(s)" if stats.dead_letters else "")
                ),
                "latency_ms": None,
                "meta": {
                    "subscribers": stats.subscribers,
                    "published": stats.published,
                    "dead_letters": stats.dead_letters,
                },
            }
        )

        overall = report.get("status", "healthy")
        if not queue_healthy:
            overall = "degraded"

        return {**report, "status": overall, "services": services}

    # -- Users & permissions ------------------------------------------------
    async def users(self) -> list[dict[str, Any]]:
        rows = await self._repo.list_users()
        return [_user_dict(u) for u in rows]

    def permissions(self) -> dict[str, Any]:
        return {
            "roles": [
                {"role": role, "permissions": perms} for role, perms in ROLE_PERMISSIONS.items()
            ]
        }

    async def update_user_role(self, *, user_id: str, new_role: str, actor: User) -> dict[str, Any]:
        if new_role not in _VALID_ROLES:
            raise ValidationAppError(f"Unknown role {new_role!r}.")
        if str(actor.id) == str(user_id):
            raise ValidationAppError("You cannot change your own role.")
        user = await self._repo.get_user(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        previous = user.role
        if previous == new_role:
            return _user_dict(user)
        user.role = new_role
        await self._session.flush()
        await self._repo.add_audit(
            actor_id=str(actor.id),
            actor_email=actor.email,
            action="user.role_changed",
            target=user.email,
            detail={"from": previous, "to": new_role},
        )
        return _user_dict(user)

    # -- Committee config ---------------------------------------------------
    async def committee_config(self) -> dict[str, Any]:
        stored = await self._repo.get_committee_config()
        return _merge_committee_config(stored)

    async def update_committee_config(
        self, *, payload: dict[str, Any], actor: User
    ) -> dict[str, Any]:
        normalized = _validate_committee_config(payload)
        await self._repo.set_committee_config(normalized)
        await self._repo.add_audit(
            actor_id=str(actor.id),
            actor_email=actor.email,
            action="committee.config_updated",
            target="committee",
            detail=normalized,
        )
        return _merge_committee_config(normalized)

    # -- Logs & audit -------------------------------------------------------
    def logs(self, *, min_level: str = "info", limit: int = 100) -> list[dict[str, Any]]:
        return recent_logs(min_level=min_level, limit=limit)

    async def audit_trail(self, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = await self._repo.list_audit(limit=limit)
        return [
            {
                "id": r.id,
                "actor_email": r.actor_email,
                "action": r.action,
                "target": r.target,
                "detail": r.detail,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]


def _user_dict(u: User) -> dict[str, Any]:
    return {
        "id": str(u.id),
        "email": u.email,
        "role": u.role,
        "status": u.status,
        "mfa_enabled": u.mfa_enabled,
        "created_at": u.created_at.isoformat(),
        "display_name": u.profile.display_name if u.profile else None,
    }


def _merge_committee_config(stored: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay stored overrides on the live defaults so the document is complete."""
    base = default_committee_config()
    customized = bool(stored)
    if not stored:
        return {**base, "customized": customized}

    stored_by_role = {e.get("role"): e for e in (stored.get("agents") or []) if isinstance(e, dict)}
    for agent in base["agents"]:
        override = stored_by_role.get(agent["role"])
        if override:
            if "enabled" in override:
                agent["enabled"] = bool(override["enabled"])
            if isinstance(override.get("weight"), int | float):
                agent["weight"] = round(float(override["weight"]), 3)

    thresholds = stored.get("thresholds") or {}
    for key in ("strong", "act"):
        if isinstance(thresholds.get(key), int | float):
            base["thresholds"][key] = float(thresholds[key])

    return {**base, "customized": customized}


def _validate_committee_config(payload: dict[str, Any]) -> dict[str, Any]:
    agents_in = payload.get("agents")
    if not isinstance(agents_in, list) or not agents_in:
        raise ValidationAppError("agents must be a non-empty list.")

    valid_roles = {a["role"] for a in default_committee_config()["agents"]}
    agents_out: list[dict[str, Any]] = []
    any_enabled = False
    for entry in agents_in:
        role = entry.get("role")
        if role not in valid_roles:
            raise ValidationAppError(f"Unknown agent role {role!r}.")
        weight = entry.get("weight", 1.0)
        if not isinstance(weight, int | float) or not (0.0 <= float(weight) <= 5.0):
            raise ValidationAppError("Each agent weight must be between 0 and 5.")
        enabled = bool(entry.get("enabled", True))
        any_enabled = any_enabled or enabled
        agents_out.append({"role": role, "enabled": enabled, "weight": round(float(weight), 3)})

    if not any_enabled:
        raise ValidationAppError("At least one agent must remain enabled.")

    thresholds = payload.get("thresholds") or {}
    strong = thresholds.get("strong", 0.6)
    act = thresholds.get("act", 0.35)
    for name, value in (("strong", strong), ("act", act)):
        if not isinstance(value, int | float) or not (0.0 < float(value) < 1.0):
            raise ValidationAppError(f"Threshold {name} must be between 0 and 1 (exclusive).")
    if not float(act) < float(strong):
        raise ValidationAppError("The 'act' threshold must be below the 'strong' threshold.")

    return {
        "agents": agents_out,
        "thresholds": {"strong": float(strong), "act": float(act)},
    }
