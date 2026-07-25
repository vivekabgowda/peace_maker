"""News Intelligence — the platform's single, reusable news-analysis service.

Consumers (CIO, Scanner, Journal, Analytics, future agents) import from here and
never re-implement news processing:

    from app.modules.news_intelligence import NewsIntelligenceEngine, NewsItem

    engine = NewsIntelligenceEngine()
    assessment = engine.assess("RELIANCE", items)   # -> NewsAssessment

The engine is deterministic (inject a clock), provider-agnostic (any adapter
yields ``NewsItem``s), and fully explainable (every score cites its events).
"""

from __future__ import annotations

from app.modules.news_intelligence.assessment import (
    EventAssessment,
    NewsAssessment,
    NewsItem,
)
from app.modules.news_intelligence.engine import NewsIntelligenceEngine
from app.modules.news_intelligence.reliability import (
    SourceTier,
    is_acceptable,
    reliability_for,
    tier_for,
)
from app.modules.news_intelligence.taxonomy import (
    EventSeverity,
    EventType,
    ImpactHorizon,
    ImpactTiming,
    PublicationSession,
    Sentiment,
    VerificationStatus,
)

__all__ = [
    "EventAssessment",
    "EventSeverity",
    "EventType",
    "ImpactHorizon",
    "ImpactTiming",
    "NewsAssessment",
    "NewsIntelligenceEngine",
    "NewsItem",
    "PublicationSession",
    "Sentiment",
    "SourceTier",
    "VerificationStatus",
    "is_acceptable",
    "reliability_for",
    "tier_for",
]
