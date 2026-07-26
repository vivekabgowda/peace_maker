"""NewsIntelligenceService — load stored news → assess → persist → read back."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import async_session_factory
from app.modules.news.orm import NewsArticle
from app.modules.news_intelligence.service import NewsIntelligenceService

pytestmark = pytest.mark.integration


def _article(aid: str, provider: str, headline: str, symbol: str) -> NewsArticle:
    return NewsArticle(
        id=aid,
        provider=provider,
        headline=headline,
        body=headline,
        url=f"https://x/{aid}",
        category="general",
        sentiment=Decimal("0"),
        impact=Decimal("0"),
        symbols=symbol,
        sectors="",
        published_at=datetime.now(UTC),
    )


async def test_assess_scores_persists_and_reads_back() -> None:
    async with async_session_factory() as session:
        session.add_all(
            [
                _article("n1", "nse", "ACME Q1 profit beats estimates, jumps 20%", "ACME"),
                _article(
                    "n2", "economic times", "ACME posts strong quarter, profit surges", "ACME"
                ),
                _article("n3", "twitter", "ACME to the moon buy now", "ACME"),
            ]
        )
        await session.flush()

        svc = NewsIntelligenceService(session)
        assessment = await svc.assess("ACME")
        await session.commit()

        # twitter dropped; two trusted articles scored positive and verified.
        assert assessment.article_count == 2
        assert assessment.news_score > 0
        assert assessment.verification_status.value == "verified"

        # Persisted and readable through the same service (the reusable API).
        latest = await svc.latest("ACME")
        assert latest is not None
        assert latest["news_score"] == assessment.news_score
        hist = await svc.history("ACME")
        assert len(hist) == 1 and hist[0]["article_count"] == 2


async def test_latest_or_assess_computes_when_absent() -> None:
    async with async_session_factory() as session:
        session.add(_article("m1", "bse", "ZZZ declares dividend of Rs 5", "ZZZ"))
        await session.flush()
        payload = await NewsIntelligenceService(session).latest_or_assess("ZZZ")
        assert payload["symbol"] == "ZZZ"
        assert payload["article_count"] == 1


async def test_no_trusted_news_returns_empty_assessment() -> None:
    async with async_session_factory() as session:
        session.add(_article("s1", "twitter", "QQQ mooning", "QQQ"))
        await session.flush()
        assessment = await NewsIntelligenceService(session).assess("QQQ")
        assert assessment.article_count == 0
        assert assessment.news_score == 0
