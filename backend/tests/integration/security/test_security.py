"""R1 security tests: WS tickets, login lockout, rate limiting."""

from __future__ import annotations

import httpx
import pytest
from app.core.rate_limit import LoginGuard, TokenBucket
from app.modules.auth.tickets import consume_ticket, issue_ticket

pytestmark = pytest.mark.integration

_CREDS = {"email": "sec@example.com", "password": "s3cure-passw0rd"}


async def _token(client: httpx.AsyncClient) -> str:
    resp = await client.post("/api/v1/auth/register", json=_CREDS)
    assert resp.status_code == 201
    return resp.json()["tokens"]["access_token"]


async def test_ws_ticket_is_single_use() -> None:
    ticket = await issue_ticket("user-123")
    assert await consume_ticket(ticket) == "user-123"
    # Second use is rejected (single-use).
    assert await consume_ticket(ticket) is None
    assert await consume_ticket("nonexistent") is None


async def test_ws_ticket_endpoint_requires_auth(client: httpx.AsyncClient) -> None:
    unauth = await client.post("/api/v1/auth/ws-ticket")
    assert unauth.status_code == 401

    token = await _token(client)
    resp = await client.post("/api/v1/auth/ws-ticket", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    ticket = resp.json()["ticket"]
    assert await consume_ticket(ticket)  # valid, single-use


async def test_login_lockout_after_repeated_failures(client: httpx.AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=_CREDS)
    # 5 wrong-password attempts trip the progressive account lockout.
    for _ in range(5):
        await client.post(
            "/api/v1/auth/login", json={"email": _CREDS["email"], "password": "wrong"}
        )
    locked = await client.post("/api/v1/auth/login", json=_CREDS)
    assert locked.status_code == 401
    assert "locked" in locked.json()["error"]["message"].lower()


async def test_login_guard_unit() -> None:
    guard = LoginGuard(max_failures=3, base_lock_seconds=60)
    locked, _ = await guard.is_locked("a@b.com", "1.2.3.4")
    assert not locked
    for _ in range(3):
        await guard.record_failure("a@b.com", "1.2.3.4")
    locked, retry = await guard.is_locked("a@b.com", "1.2.3.4")
    assert locked and retry > 0
    await guard.record_success("a@b.com")
    locked, _ = await guard.is_locked("a@b.com", "1.2.3.4")
    assert not locked


async def test_token_bucket_limits() -> None:
    bucket = TokenBucket(limit=3, window_seconds=60, prefix="test")
    results = [await bucket.allow("k") for _ in range(5)]
    assert results == [True, True, True, False, False]
