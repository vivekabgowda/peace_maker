"""The News agent consumes the standardized NewsAssessment (Sprint 11).

Reliability + verification flow into the agent's *confidence*, so the CIO weights
trustworthy news more — while news still only influences (weight 0.7) rather than
overriding the technical read.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from app.modules.committee.agents.news import NewsAnalyst
from app.modules.committee.base import AgentRole, Stance
from app.modules.news_intelligence import NewsIntelligenceEngine, NewsItem

from tests.unit.committee.factories import make_brief

_NOW = datetime(2026, 7, 24, 5, 0, tzinfo=UTC)  # Fri 10:30 IST


def _assess(*items: NewsItem):  # type: ignore[no-untyped-def]
    return NewsIntelligenceEngine(now=_NOW).assess("LEADER", list(items))


def _item(headline: str, source: str) -> NewsItem:
    return NewsItem(headline=headline, source=source, published_at=_NOW - timedelta(minutes=5))


def test_agent_uses_assessment_and_supports_on_positive_verified_news() -> None:
    assessment = _assess(
        _item("Q1 net profit beats estimates, revenue jumps 18%", "NSE"),
        _item("Company posts strong quarter, profit surges", "Economic Times"),
    )
    brief = replace(make_brief(), news_assessment=assessment)
    report = NewsAnalyst().review(brief)

    assert report.role is AgentRole.NEWS
    assert report.stance in (Stance.SUPPORT, Stance.STRONG_SUPPORT)
    assert report.confidence > 0.5  # verified + official sources → high confidence
    assert report.metrics["news_score"] > 0
    assert report.metrics["source_reliability"] >= 90
    assert any(f.citation.startswith("earnings_beat") for f in report.findings)


def test_agent_flags_single_source_critical_news_as_lower_confidence() -> None:
    assessment = _assess(_item("SEBI passes order against LEADER promoter", "Economic Times"))
    brief = replace(make_brief(), news_assessment=assessment)
    report = NewsAnalyst().review(brief)
    # Long trade + negative pending news → concern/oppose, and a visible risk note.
    assert report.stance in (Stance.CONCERN, Stance.OPPOSE, Stance.NEUTRAL)
    assert any("news_risk" == f.citation for f in report.findings)


def test_agent_falls_back_to_legacy_without_assessment() -> None:
    brief = make_brief()  # no news_assessment attached
    report = NewsAnalyst().review(brief)
    assert report.role is AgentRole.NEWS  # legacy path still produces a valid report
