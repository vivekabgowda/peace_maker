"""Identity ORM models: ``User`` and ``UserProfile``.

Maps to the ``identity`` domain in the database schema (docs/03). Kept free of
business logic — persistence shape only.
"""

from __future__ import annotations

import enum
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin


class UserRole(enum.StrEnum):
    """Role-based access control roles."""

    USER = "user"
    ADMIN = "admin"


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    PENDING = "pending"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default=UserRole.USER.value, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=UserStatus.ACTIVE.value, nullable=False)
    mfa_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)

    profile: Mapped[UserProfile] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    trading_capital: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), nullable=False
    )
    experience_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)

    user: Mapped[User] = relationship(back_populates="profile")
