"""Market-session awareness — publication window + impact timing."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.news_intelligence.sessions import (
    impact_timing,
    publication_session,
    session_weight,
)
from app.modules.news_intelligence.taxonomy import (
    EventType,
    ImpactTiming,
    PublicationSession,
)

# UTC = IST - 5:30. NSE session is 09:15-15:30 IST.
_FRI = "2026-07-24"  # a trading Friday
_SAT = "2026-07-25"  # weekend


def _utc(day: str, hh: int, mm: int) -> datetime:
    return datetime.fromisoformat(f"{day}T{hh:02d}:{mm:02d}:00+00:00").astimezone(UTC)


def test_publication_session_windows() -> None:
    assert publication_session(_utc(_FRI, 3, 0)) is PublicationSession.PRE_MARKET  # 08:30 IST
    assert publication_session(_utc(_FRI, 5, 0)) is PublicationSession.DURING_MARKET  # 10:30 IST
    assert publication_session(_utc(_FRI, 13, 0)) is PublicationSession.AFTER_MARKET  # 18:30 IST
    assert publication_session(_utc(_SAT, 5, 0)) is PublicationSession.WEEKEND


def test_intraday_news_reacts_immediately_vs_after_hours_next_session() -> None:
    during = publication_session(_utc(_FRI, 5, 0))
    after = publication_session(_utc(_FRI, 13, 0))
    assert impact_timing(EventType.EARNINGS_BEAT, during) is ImpactTiming.IMMEDIATE
    assert impact_timing(EventType.EARNINGS_BEAT, after) is ImpactTiming.NEXT_SESSION


def test_structural_events_are_multiday_regardless_of_clock() -> None:
    during = publication_session(_utc(_FRI, 5, 0))
    assert impact_timing(EventType.ACQUISITION, during) in (
        ImpactTiming.MULTI_DAY,
        ImpactTiming.LONG_TERM,
    )


def test_session_weight_discounts_out_of_hours() -> None:
    assert session_weight(PublicationSession.DURING_MARKET) == 1.0
    assert session_weight(PublicationSession.WEEKEND) < session_weight(
        PublicationSession.AFTER_MARKET
    )
