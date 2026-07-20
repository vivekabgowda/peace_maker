"""Current-user endpoints (``/me``) — a protected route demonstrating RBAC."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DbSession
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import ProfileUpdate, UserRead

router = APIRouter(tags=["users"])


@router.get("/me", response_model=UserRead, summary="Get the authenticated user")
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me/profile", response_model=UserRead, summary="Update your profile")
async def update_profile(payload: ProfileUpdate, user: CurrentUser, session: DbSession) -> UserRead:
    updated = await UserRepository(session).update_profile(
        user,
        display_name=payload.display_name,
        trading_capital=payload.trading_capital,
        experience_level=payload.experience_level,
        timezone=payload.timezone,
    )
    return UserRead.model_validate(updated)
