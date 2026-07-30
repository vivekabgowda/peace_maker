"""Persistence access for News Intelligence (Sprint 11 pt.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.news.orm import NewsArticle
from app.modules.news_intelligence.assessment import NewsAssessment, NewsItem
from app.modules.news_intelligence.orm import NewsAssessmentRow


class NewsIntelligenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_items(
        self, symbol: str, *, since_hours: float = 96.0, scan_limit: int = 500
    ) -> list[NewsItem]:
        """Recent articles mentioning ``symbol`` as provider-agnostic NewsItems.

        The article's *provider* is the source key the reliability engine scores
        (e.g. "nse" → 100), so canonical provider names drive trust. Matching is
        done in Python against the CSV symbol list to avoid brittle LIKE matches.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=since_hours)
        stmt = (
            select(NewsArticle)
            .where(NewsArticle.published_at >= cutoff)
            .order_by(NewsArticle.published_at.desc())
            .limit(scan_limit)
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        target = symbol.upper()
        items: list[NewsItem] = []
        for r in rows:
            symbols = {s.strip().upper() for s in (r.symbols or "").split(",") if s.strip()}
            if target not in symbols:
                continue
            items.append(
                NewsItem(
                    headline=r.headline,
                    source=r.provider,
                    published_at=r.published_at,
                    body=r.body,
                    url=r.url,
                    symbols=tuple(symbols),
                )
            )
        return items

    async def save_assessment(self, assessment: NewsAssessment) -> NewsAssessmentRow:
        row = NewsAssessmentRow(
            symbol=assessment.symbol,
            news_score=assessment.news_score,
            sentiment=assessment.sentiment.value,
            confidence=Decimal(str(round(assessment.confidence, 4))),
            source_reliability=assessment.source_reliability,
            verification_status=assessment.verification_status.value,
            impact_horizon=assessment.impact_horizon.value,
            impact_timing=assessment.impact_timing.value,
            dominant_session=(
                assessment.dominant_session.value if assessment.dominant_session else None
            ),
            article_count=assessment.article_count,
            payload=assessment.as_dict(),
            generated_at=assessment.generated_at or datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def latest_row(self, symbol: str) -> NewsAssessmentRow | None:
        stmt = (
            select(NewsAssessmentRow)
            .where(NewsAssessmentRow.symbol == symbol)
            .order_by(NewsAssessmentRow.generated_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalars().first()

    async def history_rows(self, symbol: str, *, limit: int = 50) -> list[NewsAssessmentRow]:
        stmt = (
            select(NewsAssessmentRow)
            .where(NewsAssessmentRow.symbol == symbol)
            .order_by(NewsAssessmentRow.generated_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())
