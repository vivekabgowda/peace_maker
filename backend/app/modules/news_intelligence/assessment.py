"""News Intelligence — the standardized assessment contract (Sprint 11).

``NewsAssessment`` is the *single* object every consumer speaks: the CIO weights
it, the Scanner renders it, the Journal snapshots it at entry/exit, and Analytics
aggregates it. Nothing downstream re-processes raw articles — they read this. The
input ``NewsItem`` is provider-agnostic, so any plugin adapter (NSE, BSE, RBI,
SEBI, a future premium API) feeds the same engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.modules.news_intelligence.taxonomy import (
    EventType,
    ImpactHorizon,
    ImpactTiming,
    PublicationSession,
    Sentiment,
    VerificationStatus,
    profile_for,
)


@dataclass(frozen=True, slots=True)
class NewsItem:
    """One provider-agnostic article fed into the engine."""

    headline: str
    source: str
    published_at: datetime
    body: str | None = None
    url: str | None = None
    symbols: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EventAssessment:
    """One classified, timed, reliability-weighted event — fully explainable."""

    event: EventType
    headline: str
    source: str
    reliability: int
    polarity: float  # -1..1
    session: PublicationSession
    impact_timing: ImpactTiming
    published_at: datetime

    def as_dict(self) -> dict[str, object]:
        prof = profile_for(self.event)
        return {
            "event": self.event.value,
            "event_label": prof.label,
            "severity": prof.severity.value,
            "headline": self.headline,
            "source": self.source,
            "reliability": self.reliability,
            "polarity": round(self.polarity, 3),
            "session": self.session.value,
            "impact_timing": self.impact_timing.value,
            "published_at": self.published_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class NewsAssessment:
    """The institutional research summary the whole platform consumes."""

    symbol: str
    news_score: int  # -100..+100
    sentiment: Sentiment
    confidence: float  # 0..1
    source_reliability: int  # 0..100 aggregate
    verification_status: VerificationStatus
    impact_horizon: ImpactHorizon
    impact_timing: ImpactTiming
    dominant_session: PublicationSession | None
    primary_reasons: tuple[str, ...]
    risk_factors: tuple[str, ...]
    headlines: tuple[str, ...]
    events: tuple[EventAssessment, ...]
    article_count: int
    generated_at: datetime | None = None
    meta: dict[str, float] = field(default_factory=dict)

    @property
    def signed_unit(self) -> float:
        """News score as a signed unit in [-1, 1] for the committee/CIO vote."""
        return self.news_score / 100.0

    def as_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "news_score": self.news_score,
            "sentiment": self.sentiment.value,
            "confidence": round(self.confidence, 4),
            "confidence_pct": round(self.confidence * 100),
            "source_reliability": self.source_reliability,
            "verification_status": self.verification_status.value,
            "impact_horizon": self.impact_horizon.value,
            "impact_horizon_label": self.impact_horizon.label,
            "impact_timing": self.impact_timing.value,
            "impact_timing_label": self.impact_timing.label,
            "dominant_session": self.dominant_session.value if self.dominant_session else None,
            "primary_reasons": list(self.primary_reasons),
            "risk_factors": list(self.risk_factors),
            "headlines": list(self.headlines),
            "events": [e.as_dict() for e in self.events],
            "article_count": self.article_count,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "meta": {k: round(v, 4) for k, v in self.meta.items()},
        }

    @classmethod
    def empty(cls, symbol: str) -> NewsAssessment:
        """A neutral assessment for a name with no material, trusted news flow."""
        return cls(
            symbol=symbol,
            news_score=0,
            sentiment=Sentiment.NEUTRAL,
            confidence=0.2,
            source_reliability=0,
            verification_status=VerificationStatus.SINGLE_SOURCE,
            impact_horizon=ImpactHorizon.SWING,
            impact_timing=ImpactTiming.MULTI_DAY,
            dominant_session=None,
            primary_reasons=("No material news flow from trusted sources.",),
            risk_factors=(),
            headlines=(),
            events=(),
            article_count=0,
        )
