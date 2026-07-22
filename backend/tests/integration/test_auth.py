"""Integration tests for the authentication flow (cookie-based refresh)."""

from __future__ import annotations

import httpx
import pytest
from app.modules.auth.cookies import REFRESH_COOKIE

pytestmark = pytest.mark.integration

_CREDS = {"email": "trader@example.com", "password": "s3cure-passw0rd"}


async def _register(client: httpx.AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_register_returns_access_and_sets_refresh_cookie(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == _CREDS["email"]
    assert body["tokens"]["access_token"]
    # Refresh token is NOT in the body — it is an httpOnly cookie.
    assert "refresh_token" not in body["tokens"]
    assert REFRESH_COOKIE in resp.cookies


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
    assert REFRESH_COOKIE in ok.cookies

    bad = await client.post(
        "/api/v1/auth/login", json={"email": _CREDS["email"], "password": "wrong"}
    )
    assert bad.status_code == 401


async def test_protected_route_requires_token(client: httpx.AsyncClient) -> None:
    unauth = await client.get("/api/v1/me")
    assert unauth.status_code == 401

    token = (await _register(client))["tokens"]["access_token"]
    ok = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert ok.status_code == 200
    assert ok.json()["email"] == _CREDS["email"]


async def test_refresh_via_cookie_rotates_and_revokes(client: httpx.AsyncClient) -> None:
    await _register(client)  # sets the refresh cookie on the client jar
    old_cookie = client.cookies.get(REFRESH_COOKIE)

    rotated = await client.post("/api/v1/auth/refresh")
    assert rotated.status_code == 200
    assert rotated.json()["access_token"]

    # Replaying the OLD refresh value must fail (rotation revoked it).
    reused = await client.post("/api/v1/auth/refresh", cookies={REFRESH_COOKIE: old_cookie})
    assert reused.status_code == 401


async def test_logout_clears_cookie_and_revokes(client: httpx.AsyncClient) -> None:
    await _register(client)
    out = await client.post("/api/v1/auth/logout")
    assert out.status_code == 204
    # Cookie cleared → refresh no longer possible.
    after = await client.post("/api/v1/auth/refresh")
    assert after.status_code == 401


async def test_refresh_without_cookie_fails(client: httpx.AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


async def test_profile_update(client: httpx.AsyncClient) -> None:
    token = (await _register(client))["tokens"]["access_token"]
    resp = await client.patch(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "Rajesh", "trading_capital": "500000.00"},
    )
    assert resp.status_code == 200
    assert resp.json()["profile"]["display_name"] == "Rajesh"


async def test_profile_defaults_preferences(client: httpx.AsyncClient) -> None:
    """A fresh account reads back the full default preference set."""
    token = (await _register(client))["tokens"]["access_token"]
    resp = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    prefs = resp.json()["profile"]["preferences"]
    assert prefs["default_risk_pct"] == 1.0
    assert prefs["preferred_timeframe"] == "5m"
    assert prefs["notify_trade"] is True
    assert prefs["theme"] == "dark"
    assert prefs["accent"] == "#1f6feb"


async def test_profile_preferences_round_trip(client: httpx.AsyncClient) -> None:
    token = (await _register(client))["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    prefs = {
        "default_risk_pct": 2.5,
        "daily_loss_limit_pct": 8.0,
        "max_open_trades": 3,
        "preferred_timeframe": "15m",
        "notify_email": True,
        "notify_trade": False,
        "notify_browser": True,
        "theme": "dark",
        "accent": "#e3b341",
    }
    resp = await client.patch("/api/v1/me/profile", headers=headers, json={"preferences": prefs})
    assert resp.status_code == 200, resp.text
    stored = resp.json()["profile"]["preferences"]
    assert stored == prefs

    # Persisted: a fresh read returns the same values.
    again = await client.get("/api/v1/me", headers=headers)
    assert again.json()["profile"]["preferences"] == prefs


async def test_profile_preferences_validation(client: httpx.AsyncClient) -> None:
    token = (await _register(client))["tokens"]["access_token"]
    resp = await client.patch(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"preferences": {"default_risk_pct": 999, "preferred_timeframe": "5m"}},
    )
    assert resp.status_code == 422


async def test_change_password_success_and_revokes_sessions(client: httpx.AsyncClient) -> None:
    token = (await _register(client))["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={"current_password": _CREDS["password"], "new_password": "new-s3cure-passw0rd"},
    )
    assert resp.status_code == 204
    # Session invalidated: the old refresh cookie no longer works.
    after = await client.post("/api/v1/auth/refresh")
    assert after.status_code == 401

    # The new password authenticates; the old one does not.
    new_login = await client.post(
        "/api/v1/auth/login",
        json={"email": _CREDS["email"], "password": "new-s3cure-passw0rd"},
    )
    assert new_login.status_code == 200
    old_login = await client.post("/api/v1/auth/login", json=_CREDS)
    assert old_login.status_code == 401


async def test_change_password_wrong_current(client: httpx.AsyncClient) -> None:
    token = (await _register(client))["tokens"]["access_token"]
    resp = await client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "not-the-password", "new_password": "another-s3cure-1"},
    )
    assert resp.status_code == 401


async def test_logout_all_revokes_every_session(client: httpx.AsyncClient) -> None:
    token = (await _register(client))["tokens"]["access_token"]
    out = await client.post("/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {token}"})
    assert out.status_code == 204
    after = await client.post("/api/v1/auth/refresh")
    assert after.status_code == 401
