"""News ORM model."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.core.database import Base, TimestampMixin
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class NewsArticle(Base, TimestampMixin):
    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # content hash
    provider: Mapped[str] = mapped_column(String(40), nullable=False)
    headline: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    sentiment: Mapped[Decimal] = mapped_column(default=Decimal("0"), nullable=False)
    impact: Mapped[Decimal] = mapped_column(default=Decimal("0"), nullable=False)
    symbols: Mapped[str] = mapped_column(String(500), default="", nullable=False)  # CSV
    sectors: Mapped[str] = mapped_column(String(500), default="", nullable=False)  # CSV
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
