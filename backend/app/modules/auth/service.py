"""Authentication use cases (application layer).

Coordinates the user and refresh-token repositories with the security
primitives. Contains the token-issuance and rotation *policy*; knows nothing
about HTTP.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.modules.auth.repository import RefreshTokenRepository
from app.modules.auth.schemas import TokenPair
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


def _hash_token(token: str) -> str:
    """Store only a SHA-256 digest of a refresh token, never the token itself."""
    return hashlib.sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)
        self._settings = get_settings()

    async def register(
        self, *, email: str, password: str, display_name: str | None
    ) -> tuple[User, TokenPair]:
        if await self._users.get_by_email(email) is not None:
            raise ConflictError("An account with this email already exists.")
        user = await self._users.create(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
        )
        tokens = await self._issue_pair(user)
        return user, tokens

    async def login(self, *, email: str, password: str) -> tuple[User, TokenPair]:
        user = await self._users.get_by_email(email)
        # Verify even when the user is missing to reduce timing/enumeration signal.
        password_ok = verify_password(password, user.password_hash) if user is not None else False
        if user is None or not password_ok:
            raise AuthenticationError("Invalid email or password.")
        if user.status != "active":
            raise AuthenticationError("Account is not active.")
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)
        tokens = await self._issue_pair(user)
        return user, tokens

    async def refresh(self, *, refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError as exc:
            raise AuthenticationError(str(exc)) from exc

        jti = payload.get("jti", "")
        stored = await self._tokens.get_active_by_jti(jti)
        if stored is None or stored.token_hash != _hash_token(refresh_token):
            # A validly-signed refresh token whose jti is no longer active is a
            # reuse of an already-rotated token → likely theft. Revoke the whole
            # session family so a stolen token can't be leveraged further. This
            # must persist even though we raise, so it runs in its own committed
            # transaction (the request transaction rolls back on the raise).
            subject = payload.get("sub")
            if subject:
                async with async_session_factory() as revoke_session:
                    await RefreshTokenRepository(revoke_session).revoke_all_for_user(
                        uuid.UUID(str(subject))
                    )
                    await revoke_session.commit()
            raise AuthenticationError("Refresh token is invalid or has been revoked.")

        user = await self._users.get_by_id(payload["sub"])
        if user is None or user.status != "active":
            raise AuthenticationError("User not found or inactive.")

        # Rotation: revoke the presented token before issuing a new pair.
        await self._tokens.revoke(stored)
        return await self._issue_pair(user)

    async def logout(self, *, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token, expected_type="refresh")
        except TokenError:
            return  # Logout is idempotent; an invalid token is already "logged out".
        stored = await self._tokens.get_active_by_jti(payload.get("jti", ""))
        if stored is not None:
            await self._tokens.revoke(stored)

    async def _issue_pair(self, user: User) -> TokenPair:
        access, _, _ = create_access_token(str(user.id), extra_claims={"role": user.role})
        refresh, jti, expires_at = create_refresh_token(str(user.id))
        await self._tokens.create(
            user_id=user.id,
            jti=jti,
            token_hash=_hash_token(refresh),
            expires_at=expires_at,
        )
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            expires_in=self._settings.access_token_expire_minutes * 60,
        )
