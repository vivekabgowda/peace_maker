"""Integration tests for the authentication flow (register/login/refresh/logout)."""

from __future__ import annotations

import httpx
import pytest

pytestmark = pytest.mark.integration

_CREDS = {"email": "trader@example.com", "password": "s3cure-passw0rd"}


async def _register(client: httpx.AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_register_returns_user_and_tokens(client: httpx.AsyncClient) -> None:
    body = await _register(client)
    assert body["user"]["email"] == _CREDS["email"]
    assert body["user"]["role"] == "user"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert body["tokens"]["token_type"] == "bearer"


async def test_duplicate_registration_conflicts(client: httpx.AsyncClient) -> None:
    await _register(client)
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


async def test_login_success_and_failure(client: httpx.AsyncClient) -> None:
    await _register(client)
    ok = await client.post("/api/v1/auth/login", json=_CREDS)
    assert ok.status_code == 200
    assert ok.json()["access_token"]

    bad = await client.post(
        "/api/v1/auth/login",
        json={"email": _CREDS["email"], "password": "wrong"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "authentication_error"


async def test_protected_route_requires_token(client: httpx.AsyncClient) -> None:
    unauth = await client.get("/api/v1/me")
    assert unauth.status_code == 401

    body = await _register(client)
    token = body["tokens"]["access_token"]
    ok = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == _CREDS["email"]


async def test_refresh_rotates_and_revokes_old_token(client: httpx.AsyncClient) -> None:
    body = await _register(client)
    old_refresh = body["tokens"]["refresh_token"]

    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert rotated.status_code == 200
    assert rotated.json()["access_token"]

    # The old refresh token must no longer work after rotation.
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reused.status_code == 401


async def test_logout_revokes_refresh_token(client: httpx.AsyncClient) -> None:
    body = await _register(client)
    refresh = body["tokens"]["refresh_token"]

    out = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh})
    assert out.status_code == 204

    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert after.status_code == 401


async def test_profile_update(client: httpx.AsyncClient) -> None:
    body = await _register(client)
    token = body["tokens"]["access_token"]
    resp = await client.patch(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Rajesh", "trading_capital": "500000.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["profile"]["display_name"] == "Rajesh"
