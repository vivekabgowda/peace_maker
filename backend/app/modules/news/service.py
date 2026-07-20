"""News service: ingest (fetch → normalize → dedupe → persist → emit) and read."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.core.logging import get_logger
from app.modules.market_data import metrics
from app.modules.news.normalize import normalize
from app.modules.news.orm import NewsArticle
from app.modules.news.providers.base import NewsProvider
from app.shared.events import NewsReceived, event_bus
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger("news_service")


class NewsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def ingest(self, provider: NewsProvider) -> int:
        """Fetch, normalize, dedupe, persist, and broadcast. Returns #new."""
        raw = await provider.fetch()
        new_count = 0
        for article in raw:
            norm = normalize(article.headline, article.body, article.source)
            exists = await self._session.get(NewsArticle, norm.id)
            if exists is not None:
                continue  # dedupe
            self._session.add(
                NewsArticle(
                    id=norm.id,
                    provider=provider.name,
                    headline=norm.headline,
                    body=article.body,
                    url=article.url,
                    category=norm.category,
                    sentiment=Decimal(str(norm.sentiment)),
                    impact=Decimal(str(norm.impact)),
                    symbols=",".join(norm.symbols),
                    sectors=",".join(norm.sectors),
                    published_at=article.published_at,
                )
            )
            new_count += 1
            await event_bus.publish(
                NewsReceived(
                    source="news_service",
                    article_id=norm.id,
                    headline=norm.headline,
                    category=norm.category,
                    sentiment=norm.sentiment,
                    impact=norm.impact,
                    symbols=norm.symbols,
                    sectors=norm.sectors,
                )
            )
        await self._session.flush()
        metrics.NEWS_INGESTED.labels(provider=provider.name).inc(new_count)
        return new_count

    async def list_recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(limit)
        rows = list((await self._session.execute(stmt)).scalars())
        return [
            {
                "id": r.id,
                "headline": r.headline,
                "category": r.category,
                "sentiment": float(r.sentiment),
                "impact": float(r.impact),
                "symbols": r.symbols.split(",") if r.symbols else [],
                "sectors": r.sectors.split(",") if r.sectors else [],
                "url": r.url,
                "published_at": r.published_at.isoformat(),
            }
            for r in rows
        ]
