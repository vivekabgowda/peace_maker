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


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105 - not a secret; OAuth token type
    expires_in: int  # access-token lifetime in seconds


class RegisterResponse(BaseModel):
    user: UserRead
    tokens: TokenPair
