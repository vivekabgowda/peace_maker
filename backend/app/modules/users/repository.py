"""User repository — the only place that talks to the users/profiles tables."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.models import User, UserProfile


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: str | uuid.UUID) -> User | None:
        return await self._session.get(User, self._as_uuid(user_id))

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email.lower())
        return (await self._session.execute(stmt)).scalar_one_or_none()

    async def create(self, *, email: str, password_hash: str, display_name: str | None) -> User:
        user = User(email=email.lower(), password_hash=password_hash)
        user.profile = UserProfile(display_name=display_name)
        self._session.add(user)
        await self._session.flush()
        return user

    async def update_profile(self, user: User, **fields: object) -> User:
        if user.profile is None:
            user.profile = UserProfile()
        for key, value in fields.items():
            if value is not None:
                setattr(user.profile, key, value)
        await self._session.flush()
        return user

    @staticmethod
    def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
