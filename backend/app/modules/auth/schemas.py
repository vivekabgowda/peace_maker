"""Authentication API schemas (Pydantic v2 DTOs)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field

from app.modules.users.schemas import UserRead


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenPair(BaseModel):
    """Internal: the service issues both tokens; the router puts the refresh
    token in an httpOnly cookie and returns only the access token to the client."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - not a secret; OAuth token type
    expires_in: int  # access-token lifetime in seconds


class AccessTokenResponse(BaseModel):
    """Client-facing token response — access token only (refresh is a cookie)."""

    access_token: str
    token_type: str = "bearer"  # noqa: S105 - not a secret; OAuth token type
    expires_in: int


class RegisterResponse(BaseModel):
    user: UserRead
    tokens: AccessTokenResponse


class WsTicketResponse(BaseModel):
    ticket: str
    expires_in: int = 30
