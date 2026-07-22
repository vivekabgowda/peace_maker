"""Authentication endpoints: register, login, refresh, logout, ws-ticket.

Security (R1): the refresh token is delivered/consumed via an httpOnly cookie
(never the JSON body), login is protected by rate limiting + progressive
lockout + IP reputation, and WebSocket auth uses short-lived single-use tickets
instead of a JWT in the URL.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.core.dependencies import CurrentUser, DbSession
from app.core.errors import AuthenticationError
from app.core.rate_limit import login_guard, login_rate_limit
from app.modules.auth.cookies import clear_refresh_cookie, set_refresh_cookie
from app.modules.auth.schemas import (
    AccessTokenResponse,
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
    WsTicketResponse,
)
from app.modules.auth.service import AuthService
from app.modules.auth.tickets import issue_ticket
from app.modules.users.schemas import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _access_response(tokens: object) -> AccessTokenResponse:
    return AccessTokenResponse(
        access_token=tokens.access_token,  # type: ignore[attr-defined]
        expires_in=tokens.expires_in,  # type: ignore[attr-defined]
    )


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account; refresh token set as httpOnly cookie",
)
async def register(
    payload: RegisterRequest, response: Response, session: DbSession
) -> RegisterResponse:
    user, tokens = await AuthService(session).register(
        email=payload.email, password=payload.password, display_name=payload.display_name
    )
    set_refresh_cookie(response, tokens.refresh_token)
    return RegisterResponse(user=UserRead.model_validate(user), tokens=_access_response(tokens))


@router.post("/login", response_model=AccessTokenResponse, summary="Authenticate")
async def login(
    payload: LoginRequest, request: Request, response: Response, session: DbSession
) -> AccessTokenResponse:
    ip = _client_ip(request)
    if not await login_rate_limit.allow(ip):
        raise AuthenticationError("Too many attempts. Please slow down.")
    locked, retry_after = await login_guard.is_locked(payload.email, ip)
    if locked:
        raise AuthenticationError(f"Account temporarily locked. Retry in {retry_after}s.")
    try:
        _user, tokens = await AuthService(session).login(
            email=payload.email, password=payload.password
        )
    except AuthenticationError:
        await login_guard.record_failure(payload.email, ip)
        raise
    await login_guard.record_success(payload.email)
    set_refresh_cookie(response, tokens.refresh_token)
    return _access_response(tokens)


@router.post("/refresh", response_model=AccessTokenResponse, summary="Rotate via cookie")
async def refresh(request: Request, response: Response, session: DbSession) -> AccessTokenResponse:
    from app.modules.auth.cookies import REFRESH_COOKIE

    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise AuthenticationError("Missing refresh cookie.")
    tokens = await AuthService(session).refresh(refresh_token=token)
    set_refresh_cookie(response, tokens.refresh_token)
    return _access_response(tokens)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke the refresh token and clear the cookie",
)
async def logout(request: Request, session: DbSession) -> Response:
    from app.modules.auth.cookies import REFRESH_COOKIE

    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        await AuthService(session).logout(refresh_token=token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Change your password; revokes all refresh tokens",
)
async def change_password(
    payload: ChangePasswordRequest, user: CurrentUser, session: DbSession
) -> Response:
    await AuthService(session).change_password(
        user=user,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Revoke every session for the current user and clear the cookie",
)
async def logout_all(user: CurrentUser, session: DbSession) -> Response:
    await AuthService(session).logout_all(user=user)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_refresh_cookie(response)
    return response


@router.post("/ws-ticket", response_model=WsTicketResponse, summary="Short-lived WS auth ticket")
async def ws_ticket(user: CurrentUser) -> WsTicketResponse:
    ticket = await issue_ticket(str(user.id))
    return WsTicketResponse(ticket=ticket)
