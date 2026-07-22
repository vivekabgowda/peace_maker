"""Integration tests for the Admin dashboard endpoints (RBAC-guarded)."""

from __future__ import annotations

import httpx
import pytest
from app.core.database import async_session_factory
from app.modules.users.repository import UserRepository

pytestmark = pytest.mark.integration


async def _register(client: httpx.AsyncClient, email: str) -> str:
    resp = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "s3cure-passw0rd"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["user"]["id"]


async def _promote(user_id: str) -> None:
    async with async_session_factory() as session:
        user = await UserRepository(session).get_by_id(user_id)
        assert user is not None
        user.role = "admin"
        await session.commit()


async def _admin_headers(client: httpx.AsyncClient, email: str = "admin@example.com") -> dict:
    user_id = await _register(client, email)
    await _promote(user_id)
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "s3cure-passw0rd"}
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_admin_routes_require_admin_role(client: httpx.AsyncClient) -> None:
    # A freshly-registered (non-admin) user is forbidden.
    token = (
        await client.post(
            "/api/v1/auth/register", json={"email": "u@example.com", "password": "s3cure-passw0rd"}
        )
    ).json()["tokens"]["access_token"]
    resp = await client.get("/api/v1/admin/system", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_admin_routes_require_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/users")).status_code == 401


async def test_system_health(client: httpx.AsyncClient) -> None:
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/admin/system", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    names = {s["name"] for s in body["services"]}
    assert {"database", "redis", "websocket", "event_queue"} <= names
    assert body["status"] in {"healthy", "degraded"}


async def test_users_and_permissions(client: httpx.AsyncClient) -> None:
    headers = await _admin_headers(client)
    await _register(client, "trader@example.com")

    users = (await client.get("/api/v1/admin/users", headers=headers)).json()["users"]
    emails = {u["email"] for u in users}
    assert {"admin@example.com", "trader@example.com"} <= emails

    perms = (await client.get("/api/v1/admin/permissions", headers=headers)).json()
    roles = {r["role"]: r["permissions"] for r in perms["roles"]}
    assert "configure_committee" in roles["admin"]
    assert "configure_committee" not in roles["user"]


async def test_committee_config_roundtrip_and_audit(client: httpx.AsyncClient) -> None:
    headers = await _admin_headers(client)

    default = (await client.get("/api/v1/admin/committee/config", headers=headers)).json()
    assert default["customized"] is False
    assert len(default["agents"]) == 7

    # Disable one agent, bump another's weight, tighten thresholds.
    agents = [dict(a) for a in default["agents"]]
    agents[0]["enabled"] = False
    agents[1]["weight"] = 2.0
    payload = {"agents": agents, "thresholds": {"strong": 0.7, "act": 0.3}}
    put = await client.put("/api/v1/admin/committee/config", headers=headers, json=payload)
    assert put.status_code == 200, put.text
    saved = put.json()
    assert saved["customized"] is True
    assert saved["agents"][0]["enabled"] is False
    assert saved["agents"][1]["weight"] == 2.0
    assert saved["thresholds"] == {"strong": 0.7, "act": 0.3}

    # Persisted.
    again = (await client.get("/api/v1/admin/committee/config", headers=headers)).json()
    assert again["thresholds"]["strong"] == 0.7

    # Audit trail recorded the change.
    audit = (await client.get("/api/v1/admin/audit", headers=headers)).json()["audit"]
    assert any(a["action"] == "committee.config_updated" for a in audit)


async def test_committee_config_validation(client: httpx.AsyncClient) -> None:
    headers = await _admin_headers(client)
    default = (await client.get("/api/v1/admin/committee/config", headers=headers)).json()
    # act must be below strong.
    bad = {"agents": default["agents"], "thresholds": {"strong": 0.3, "act": 0.6}}
    resp = await client.put("/api/v1/admin/committee/config", headers=headers, json=bad)
    assert resp.status_code == 422

    # all agents disabled is rejected.
    agents = [{**a, "enabled": False} for a in default["agents"]]
    resp2 = await client.put(
        "/api/v1/admin/committee/config",
        headers=headers,
        json={"agents": agents, "thresholds": default["thresholds"]},
    )
    assert resp2.status_code == 422


async def test_update_user_role_and_self_guard(client: httpx.AsyncClient) -> None:
    headers = await _admin_headers(client)
    trader_id = await _register(client, "trader@example.com")

    promoted = await client.patch(
        f"/api/v1/admin/users/{trader_id}/role", headers=headers, json={"role": "admin"}
    )
    assert promoted.status_code == 200
    assert promoted.json()["role"] == "admin"

    # Admin cannot change their own role (self-lockout guard).
    me = (await client.get("/api/v1/me", headers=headers)).json()
    self_change = await client.patch(
        f"/api/v1/admin/users/{me['id']}/role", headers=headers, json={"role": "user"}
    )
    assert self_change.status_code == 422

    audit = (await client.get("/api/v1/admin/audit", headers=headers)).json()["audit"]
    assert any(a["action"] == "user.role_changed" for a in audit)


async def test_logs_endpoint(client: httpx.AsyncClient) -> None:
    headers = await _admin_headers(client)
    resp = await client.get("/api/v1/admin/logs?level=info&limit=50", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json()["logs"], list)
