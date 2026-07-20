"""Shared FastAPI dependencies: DB session, current user, and RBAC guards.

These wire the request layer to the application/infrastructure layers without
letting routers know about persistence details (dependency inversion).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import AuthenticationError, AuthorizationError
from app.core.security import TokenError, decode_token
from app.modules.users.models import User, UserRole
from app.modules.users.repository import UserRepository

_bearer = HTTPBearer(auto_error=False, description="JWT access token")

DbSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    """Resolve and return the authenticated user from a bearer access token."""
    if credentials is None:
        raise AuthenticationError("Missing authentication credentials.")
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
    except TokenError as exc:
        raise AuthenticationError(str(exc)) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise AuthenticationError("Invalid token subject.")

    user = await UserRepository(session).get_by_id(user_id)
    if user is None or user.status != "active":
        raise AuthenticationError("User not found or inactive.")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*roles: UserRole) -> object:
    """Return a dependency that enforces the user has one of ``roles``."""

    async def _guard(user: CurrentUser) -> User:
        if user.role not in roles:
            raise AuthorizationError()
        return user

    return Depends(_guard)


RequireAdmin = require_role(UserRole.ADMIN)
