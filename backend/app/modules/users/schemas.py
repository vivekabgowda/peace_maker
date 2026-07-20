"""User/profile API schemas (Pydantic v2 DTOs)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None = None
    trading_capital: Decimal = Decimal("0")
    experience_level: str | None = None
    timezone: str = "Asia/Kolkata"


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    trading_capital: Decimal | None = Field(default=None, ge=0)
    experience_level: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: str
    status: str
    mfa_enabled: bool
    created_at: datetime
    profile: ProfileRead | None = None
