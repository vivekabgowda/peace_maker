"""Authentication endpoints: register, login, refresh, logout."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.dependencies import DbSession
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    TokenPair,
)
from app.modules.auth.service import AuthService
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account and return a token pair",
)
async def register(payload: RegisterRequest, session: DbSession) -> RegisterResponse:
    user, tokens = await AuthService(session).register(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    return RegisterResponse(user=UserRead.model_validate(user), tokens=tokens)


@router.post("/login", response_model=TokenPair, summary="Authenticate and get tokens")
async def login(payload: LoginRequest, session: DbSession) -> TokenPair:
    _user, tokens = await AuthService(session).login(email=payload.email, password=payload.password)
    return tokens


@router.post("/refresh", response_model=TokenPair, summary="Rotate the refresh token")
async def refresh(payload: RefreshRequest, session: DbSession) -> TokenPair:
    return await AuthService(session).refresh(refresh_token=payload.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke a refresh token (idempotent)",
)
async def logout(payload: LogoutRequest, session: DbSession) -> Response:
    await AuthService(session).logout(refresh_token=payload.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
