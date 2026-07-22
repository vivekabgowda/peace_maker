"""User/profile API schemas (Pydantic v2 DTOs)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class Preferences(BaseModel):
    """Trading / notification / appearance preferences persisted as JSON.

    Unknown keys are dropped so old rows survive schema changes.
    """

    model_config = ConfigDict(extra="ignore")

    # Trading
    default_risk_pct: float = Field(default=1.0, ge=0.05, le=20.0)
    daily_loss_limit_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    max_open_trades: int = Field(default=5, ge=1, le=100)
    preferred_timeframe: Literal["1m", "5m", "15m", "1h", "1d"] = "5m"

    # Notifications
    notify_email: bool = False
    notify_trade: bool = True
    notify_browser: bool = False

    # Appearance
    theme: Literal["dark", "light"] = "dark"
    accent: str = Field(default="#1f6feb", pattern=r"^#[0-9a-fA-F]{6}$")


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    display_name: str | None = None
    trading_capital: Decimal = Decimal("0")
    experience_level: str | None = None
    timezone: str = "Asia/Kolkata"
    preferences: Preferences = Field(default_factory=Preferences)

    @field_validator("preferences", mode="before")
    @classmethod
    def _coerce_preferences(cls, value: object) -> object:
        # Legacy rows store NULL/empty; fall back to defaults.
        return value or {}


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    trading_capital: Decimal | None = Field(default=None, ge=0)
    experience_level: str | None = Field(default=None, max_length=20)
    timezone: str | None = Field(default=None, max_length=64)
    preferences: Preferences | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: str
    status: str
    mfa_enabled: bool
    created_at: datetime
    profile: ProfileRead | None = None
