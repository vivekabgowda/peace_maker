"""Admin persistence (Sprint 12).

Two ordinary relational tables:

- ``committee_config`` — a single JSON row holding the operator's overrides for
  the AI committee (per-agent enabled/weight, plus the CIO conviction
  thresholds). The committee reads this at deliberation time; an absent row
  means "use the built-in defaults".
- ``audit_log`` — an append-only trail of privileged admin actions (role
  changes, committee-config edits) for accountability.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class CommitteeConfig(Base, TimestampMixin):
    """Single-row committee configuration (id is pinned to 1)."""

    __tablename__ = "committee_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
