"""Refresh-token cookie helpers (R1 security).

The refresh token is delivered as an httpOnly, Secure, SameSite cookie so it is
never readable by JavaScript (XSS-safe). The access token stays in memory on the
client. ``Secure`` is enabled outside local/test so cookies still work over HTTP
during development and integration tests.
"""

from __future__ import annotations

from fastapi import Response

from app.core.config import get_settings

REFRESH_COOKIE = "bkn_refresh"
_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.env in ("staging", "production"),
        samesite="lax",
        max_age=settings.refresh_token_expire_days * 24 * 3600,
        path=_COOKIE_PATH,
    )


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE, path=_COOKIE_PATH)
