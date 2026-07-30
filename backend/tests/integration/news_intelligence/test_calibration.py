"""News calibration — did the news that preceded a trade predict the move?"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from app.core.database import async_session_factory
from app.modules.journal.orm import JournalEntry
from app.modules.news_intelligence.calibration import NewsCalibrationService
from app.modules.news_intelligence.orm import NewsAssessmentRow

pytestmark = pytest.mark.integration

_T0 = datetime(2026, 7, 20, 4, 0, tzinfo=UTC)


def _news(symbol: str, score: int, sentiment: str, when: datetime) -> NewsAssessmentRow:
    return NewsAssessmentRow(
        symbol=symbol,
        news_score=score,
        sentiment=sentiment,
        confidence=Decimal("0.7"),
        source_reliability=95,
        verification_status="verified",
        impact_horizon="swing",
        impact_timing="next_session",
        article_count=2,
        payload={},
        generated_at=when,
    )


def _trade(symbol: str, direction: str, r: str, outcome: str, entry: datetime) -> JournalEntry:
    return JournalEntry(
        symbol=symbol,
        direction=direction,
        quantity=10,
        entry_price=Decimal("100"),
        entry_ts=entry,
        exit_price=Decimal("110"),
        exit_ts=entry + timedelta(days=2),
        gross_pnl=Decimal("100"),
        net_pnl=Decimal("100"),
        r_multiple=Decimal(r),
        outcome=outcome,
        holding_seconds=172800,
    )


async def test_accuracy_scores_news_against_realized_move() -> None:
    async with async_session_factory() as session:
        session.add_all(
            [
                _news("ACME", 50, "strong_positive", _T0),
                _news("ZZZ", -40, "negative", _T0),
                _news("QQQ", 3, "neutral", _T0),  # below significance → ignored
            ]
        )
        session.add_all(
            [
                # positive news → long win (price up) → correct
                _trade("ACME", "long", "2.0", "win", _T0 + timedelta(hours=1)),
                # negative news → long loss (price down) → correct
                _trade("ZZZ", "long", "-1.0", "loss", _T0 + timedelta(hours=1)),
                # neutral news → ignored (below threshold)
                _trade("QQQ", "long", "1.0", "win", _T0 + timedelta(hours=1)),
            ]
        )
        await session.flush()

        stats = await NewsCalibrationService(session).accuracy()
        assert stats["trades_with_news"] == 2  # neutral QQQ excluded
        assert stats["accuracy"] == 1.0
        assert stats["avg_r_after_positive_news"] == 2.0
        assert stats["avg_r_after_negative_news"] == -1.0


async def test_journal_context_flags_supported_and_contradicted() -> None:
    async with async_session_factory() as session:
        session.add(_news("WIN", 50, "strong_positive", _T0))
        session.add(_news("BAD", 50, "strong_positive", _T0))
        # positive news, long win (price up) → supported
        good = _trade("WIN", "long", "2.0", "win", _T0 + timedelta(hours=1))
        # positive news, long loss (price down) → contradicted
        bad = _trade("BAD", "long", "-1.0", "loss", _T0 + timedelta(hours=1))
        session.add_all([good, bad])
        await session.flush()

        ctx = await NewsCalibrationService(session).journal_context()
        assert ctx[str(good.id)]["supported"] is True
        assert ctx[str(bad.id)]["supported"] is False
        assert ctx[str(good.id)]["news_score"] == 50


async def test_news_before_entry_only() -> None:
    async with async_session_factory() as session:
        # Assessment generated AFTER the trade entry must not be used.
        session.add(_news("LATE", 60, "strong_positive", _T0 + timedelta(days=1)))
        session.add(_trade("LATE", "long", "1.5", "win", _T0))
        await session.flush()
        stats = await NewsCalibrationService(session).accuracy()
        assert stats["trades_with_news"] == 0
