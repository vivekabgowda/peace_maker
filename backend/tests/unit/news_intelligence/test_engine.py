"""News Intelligence engine — end-to-end assessment behavior."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.news_intelligence import (
    NewsIntelligenceEngine,
    NewsItem,
    Sentiment,
    VerificationStatus,
)

_NOW = datetime(2026, 7, 24, 5, 0, tzinfo=UTC)  # Fri 10:30 IST, market open


def _item(headline: str, source: str, mins_ago: int = 10) -> NewsItem:
    from datetime import timedelta

    return NewsItem(
        headline=headline, source=source, published_at=_NOW - timedelta(minutes=mins_ago)
    )


def _engine() -> NewsIntelligenceEngine:
    return NewsIntelligenceEngine(now=_NOW)


def test_empty_when_no_trusted_news() -> None:
    a = _engine().assess("XYZ", [_item("pump this stock now!!", "telegram")])
    assert a.article_count == 0
    assert a.news_score == 0
    assert a.sentiment is Sentiment.NEUTRAL


def test_untrusted_sources_are_dropped() -> None:
    a = _engine().assess(
        "ABC",
        [
            _item("ABC Q1 profit beats estimates, jumps 20%", "NSE"),
            _item("ABC to the moon", "twitter"),
        ],
    )
    assert a.article_count == 1  # only the NSE item counted


def test_positive_corroborated_earnings_scores_positive_and_verified() -> None:
    a = _engine().assess(
        "ABC",
        [
            _item("ABC Q1 profit beats estimates, revenue jumps 15%", "NSE"),
            _item("ABC posts strong quarter, profit surges", "Economic Times"),
        ],
    )
    assert a.news_score > 0
    assert a.sentiment in (Sentiment.POSITIVE, Sentiment.STRONG_POSITIVE)
    # Two independent sources incl. an official one → verified.
    assert a.verification_status is VerificationStatus.VERIFIED
    assert a.source_reliability >= 90
    assert a.primary_reasons  # explainable
    assert a.impact_timing.value == "immediate"  # published during market


def test_single_source_critical_event_is_pending() -> None:
    a = _engine().assess(
        "ABC",
        [_item("SEBI passes order against ABC promoter", "Economic Times")],
    )
    assert a.verification_status is VerificationStatus.PENDING
    assert a.news_score < 0
    assert any("corroborat" in r.lower() or "pending" in r.lower() for r in a.risk_factors)


def test_reliability_weighting_prefers_official_over_blog() -> None:
    strong_official = _engine().assess("ABC", [_item("ABC profit beats, jumps 20%", "NSE")])
    weak_blog = _engine().assess("ABC", [_item("ABC profit beats, jumps 20%", "some finance blog")])
    assert abs(strong_official.news_score) >= abs(weak_blog.news_score)


def test_assessment_is_json_serializable_for_consumers() -> None:
    import json

    a = _engine().assess("ABC", [_item("ABC declares dividend of Rs 5", "BSE")])
    json.dumps(a.as_dict())  # must not raise — Scanner/Journal/Analytics consume this
