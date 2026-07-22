"""Integration tests for the validation API (RBAC + run/list/get)."""

from __future__ import annotations

import httpx
import pytest
from app.core.database import async_session_factory
from app.modules.users.repository import UserRepository

pytestmark = pytest.mark.integration

_CREDS = {"email": "quant@example.com", "password": "s3cure-passw0rd"}


async def _token(client: httpx.AsyncClient, *, admin: bool) -> str:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    user_id = resp.json()["user"]["id"]
    if admin:
        async with async_session_factory() as session:
            user = await UserRepository(session).get_by_id(user_id)
            assert user is not None
            user.role = "admin"
            await session.commit()
        login = await client.post("/api/v1/auth/login", json=_CREDS)
        return str(login.json()["access_token"])
    return str(resp.json()["tokens"]["access_token"])


async def test_run_requires_admin(client: httpx.AsyncClient) -> None:
    token = await _token(client, admin=False)
    resp = await client.post("/api/v1/validation/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


async def test_run_lists_and_gets(client: httpx.AsyncClient) -> None:
    token = await _token(client, admin=True)
    headers = {"Authorization": f"Bearer {token}"}

    # A run with no candles still produces a well-formed (empty) validation doc.
    run = await client.post("/api/v1/validation/run?history=100&folds=4", headers=headers)
    assert run.status_code == 200, run.text
    body = run.json()
    assert "roundtrip_cost_bps" in body and body["roundtrip_cost_bps"] > 0
    assert "strategies" in body and "survivors" in body
    run_id = body["id"]

    listed = await client.get("/api/v1/validation/runs", headers=headers)
    assert listed.status_code == 200
    assert any(r["id"] == run_id for r in listed.json()["runs"])

    got = await client.get(f"/api/v1/validation/runs/{run_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == run_id

    missing = await client.get("/api/v1/validation/runs/999999", headers=headers)
    assert missing.status_code == 404


async def test_runs_list_requires_auth(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/validation/runs")).status_code == 401
