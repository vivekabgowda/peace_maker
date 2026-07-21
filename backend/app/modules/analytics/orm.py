"""Analytics persistence — stored performance reports (Sprint 7).

Daily and weekly reports are generated automatically (by the feed's report
scheduler) and persisted here so they are retrievable via the API without
recomputation and serve as an audit trail of performance over time.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class PerformanceReport(Base, TimestampMixin):
    __tablename__ = "performance_reports"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # daily | weekly
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Full structured metrics payload (PerformanceMetrics + breakdowns).
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    # Human-readable rendered report (markdown).
    rendered: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        # One report per (kind, period_start) — regeneration replaces it.
        UniqueConstraint("kind", "period_start", name="uq_performance_reports_kind_period"),
        Index("ix_performance_reports_kind_end", "kind", "period_end"),
    )
