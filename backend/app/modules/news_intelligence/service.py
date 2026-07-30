"""News Intelligence service — the one reusable API for the whole platform.

`assess(symbol)` loads stored news, runs the shared engine, persists a snapshot,
and returns the standardized :class:`NewsAssessment`. The CIO/Scanner call this to
enrich a brief; the Journal snapshots the returned assessment at entry/exit; the
API serves `latest`/`history` to the UI and Analytics. No consumer re-implements
news processing — they all go through here.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.news_intelligence.assessment import NewsAssessment
from app.modules.news_intelligence.engine import NewsIntelligenceEngine
from app.modules.news_intelligence.repository import NewsIntelligenceRepository

logger = get_logger("news_intelligence")


class NewsIntelligenceService:
    def __init__(
        self, session: AsyncSession, *, engine: NewsIntelligenceEngine | None = None
    ) -> None:
        self._session = session
        self._repo = NewsIntelligenceRepository(session)
        self._engine = engine or NewsIntelligenceEngine()

    async def assess(self, symbol: str, *, persist: bool = True) -> NewsAssessment:
        """Compute (and by default persist) a fresh assessment for ``symbol``."""
        items = await self._repo.load_items(symbol)
        assessment = self._engine.assess(symbol, items)
        if persist and assessment.article_count > 0:
            await self._repo.save_assessment(assessment)
        logger.info(
            "news_assessed",
            symbol=symbol,
            score=assessment.news_score,
            articles=assessment.article_count,
            verification=assessment.verification_status.value,
        )
        return assessment

    async def latest(self, symbol: str) -> dict[str, Any] | None:
        """Most recent stored assessment payload (for API/UI/Journal/Analytics)."""
        row = await self._repo.latest_row(symbol)
        return dict(row.payload) if row else None

    async def latest_or_assess(self, symbol: str) -> dict[str, Any]:
        """Stored snapshot if present, else compute one now."""
        latest = await self.latest(symbol)
        if latest is not None:
            return latest
        return (await self.assess(symbol)).as_dict()

    async def history(self, symbol: str, *, limit: int = 50) -> list[dict[str, Any]]:
        rows = await self._repo.history_rows(symbol, limit=limit)
        return [
            {
                "generated_at": r.generated_at.isoformat(),
                "news_score": r.news_score,
                "sentiment": r.sentiment,
                "confidence": float(r.confidence),
                "source_reliability": r.source_reliability,
                "verification_status": r.verification_status,
                "impact_horizon": r.impact_horizon,
                "article_count": r.article_count,
            }
            for r in rows
        ]
