"""Event classifier — headline → event type + polarity."""

from __future__ import annotations

import pytest
from app.modules.news_intelligence.classifier import classify
from app.modules.news_intelligence.taxonomy import EventType


@pytest.mark.parametrize(
    ("headline", "event", "positive"),
    [
        ("Q1 net profit beats estimates, revenue jumps 12%", EventType.EARNINGS_BEAT, True),
        ("Infosys Q2 profit misses estimates, revenue falls", EventType.EARNINGS_MISS, False),
        ("TCS raises FY24 guidance after strong quarter", EventType.GUIDANCE_UPGRADE, True),
        ("Wipro cuts full-year guidance on weak demand", EventType.GUIDANCE_DOWNGRADE, False),
        ("Board approves share buyback of Rs 1000 crore", EventType.BUYBACK, True),
        ("SEBI passes order banning promoter from securities market", EventType.SEBI_ORDER, False),
        ("RBI keeps repo rate unchanged in policy review", EventType.RBI_ANNOUNCEMENT, None),
        ("Company to acquire rival for Rs 5000 crore", EventType.ACQUISITION, True),
        ("Promoter sells 4% stake, reduces holding", EventType.PROMOTER_SELLING, False),
        ("Promoter buys additional shares, raises stake", EventType.PROMOTER_BUYING, True),
        ("CRISIL downgrades company's credit rating", EventType.CREDIT_RATING_DOWNGRADE, False),
        ("Firm bags Rs 650 crore order from government", EventType.LARGE_ORDER_WIN, True),
        ("CFO resigns with immediate effect", EventType.CFO_CHANGE, False),
        ("NCLT admits insolvency plea against the company", EventType.LITIGATION, False),
        ("Company declares interim dividend of Rs 5 per share", EventType.DIVIDEND, True),
        ("Some routine corporate housekeeping update", EventType.GENERAL, None),
    ],
)
def test_classify_events(headline: str, event: EventType, positive: bool | None) -> None:
    c = classify(headline)
    assert c.event is event
    if positive is True:
        assert c.polarity > 0, c
    elif positive is False:
        assert c.polarity < 0, c


def test_classification_reports_matched_phrase() -> None:
    assert classify("SEBI passes order banning promoter").matched  # non-empty citation
