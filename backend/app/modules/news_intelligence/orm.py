"""News Intelligence persistence (Sprint 11 pt.2).

An append-only history of per-symbol :class:`NewsAssessment` snapshots — the
training substrate the CIO/Scanner/Journal/Analytics read and that continuous
calibration will later score against realized price action. Key fields are
promoted to columns for querying; the full explainable payload (events, reasons,
risks, headlines) is stored as JSON so nothing is lost.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class NewsAssessmentRow(Base, TimestampMixin):
    __tablename__ = "news_assessments"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    news_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False, default="neutral")
    confidence: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False, default=0)
    source_reliability: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verification_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    impact_horizon: Mapped[str] = mapped_column(String(20), nullable=False, default="swing")
    impact_timing: Mapped[str] = mapped_column(String(20), nullable=False, default="multi_day")
    dominant_session: Mapped[str | None] = mapped_column(String(20), nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
