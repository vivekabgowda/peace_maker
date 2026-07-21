"""Refresh-token reuse detection → session-family revocation (R1 #27)."""

from __future__ import annotations

import httpx
import pytest
from app.modules.auth.cookies import REFRESH_COOKIE

pytestmark = pytest.mark.integration

_CREDS = {"email": "reuse@example.com", "password": "s3cure-passw0rd"}


async def test_reused_refresh_token_revokes_whole_family(client: httpx.AsyncClient) -> None:
    reg = await client.post("/api/v1/auth/register", json=_CREDS)
    original = reg.cookies[REFRESH_COOKIE]
    client.cookies.clear()  # drive cookies explicitly to avoid jar ambiguity

    # Rotate once — issues a new refresh cookie, revokes the original.
    rotated = await client.post("/api/v1/auth/refresh", cookies={REFRESH_COOKIE: original})
    assert rotated.status_code == 200
    new_cookie = rotated.cookies[REFRESH_COOKIE]
    client.cookies.clear()
    assert new_cookie != original

    # Attacker replays the ORIGINAL (already-rotated) token → reuse detected.
    reuse = await client.post("/api/v1/auth/refresh", cookies={REFRESH_COOKIE: original})
    assert reuse.status_code == 401
    client.cookies.clear()

    # Family revocation: even the *legitimate* new token is now dead.
    after = await client.post("/api/v1/auth/refresh", cookies={REFRESH_COOKIE: new_cookie})
    assert after.status_code == 401
