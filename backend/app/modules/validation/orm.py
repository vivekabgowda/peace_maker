"""Validation persistence (Sprint 14).

One append-only table storing the result of each validation run (cost-aware,
out-of-sample strategy evaluation with statistical significance). Read-mostly;
the payload is a JSON document mirroring the service output.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class ValidationRun(Base, TimestampMixin):
    __tablename__ = "validation_runs"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="walk_forward")
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
