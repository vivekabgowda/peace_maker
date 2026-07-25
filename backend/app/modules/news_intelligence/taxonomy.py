"""News Intelligence — event taxonomy and impact vocabulary (Sprint 11).

A single, shared vocabulary the whole platform speaks: the CIO, Scanner, Journal,
Analytics, and any future agent read these enums off the standardized
:class:`~app.modules.news_intelligence.assessment.NewsAssessment` rather than
re-deriving their own. Every event type carries an *explainable* prior — a
default polarity, severity, holding horizon, and whether it is critical enough to
demand multi-source verification — so scoring is never a black box.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Sentiment(StrEnum):
    """Human-facing sentiment label derived from the signed news score."""

    STRONG_POSITIVE = "strong_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    STRONG_NEGATIVE = "strong_negative"

    @classmethod
    def from_score(cls, score: float) -> Sentiment:
        """Map a signed score in [-1, 1] to a label."""
        if score >= 0.5:
            return cls.STRONG_POSITIVE
        if score >= 0.15:
            return cls.POSITIVE
        if score <= -0.5:
            return cls.STRONG_NEGATIVE
        if score <= -0.15:
            return cls.NEGATIVE
        return cls.NEUTRAL


class EventSeverity(StrEnum):
    """How market-moving an event class is, independent of direction."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def weight(self) -> float:
        return {
            EventSeverity.LOW: 0.4,
            EventSeverity.MEDIUM: 0.7,
            EventSeverity.HIGH: 1.0,
            EventSeverity.CRITICAL: 1.3,
        }[self]


class ImpactHorizon(StrEnum):
    """How long the *trade thesis* driven by the news is expected to last."""

    INTRADAY = "intraday"
    SWING = "swing"  # 3-10 trading days
    MEDIUM_TERM = "medium_term"  # weeks
    LONG_TERM = "long_term"  # months+

    @property
    def label(self) -> str:
        return {
            ImpactHorizon.INTRADAY: "Intraday",
            ImpactHorizon.SWING: "Swing (3-10 trading days)",
            ImpactHorizon.MEDIUM_TERM: "Medium-term (weeks)",
            ImpactHorizon.LONG_TERM: "Long-term (months+)",
        }[self]


class ImpactTiming(StrEnum):
    """*When* the price reaction is expected to begin, given publication time."""

    IMMEDIATE = "immediate"  # reacts in the current live session
    NEXT_SESSION = "next_session"  # gaps at the next open
    MULTI_DAY = "multi_day"  # digested over several sessions
    LONG_TERM = "long_term"  # structural, re-rates slowly

    @property
    def label(self) -> str:
        return {
            ImpactTiming.IMMEDIATE: "Immediate (this session)",
            ImpactTiming.NEXT_SESSION: "Next session",
            ImpactTiming.MULTI_DAY: "Multi-day",
            ImpactTiming.LONG_TERM: "Long-term",
        }[self]


class PublicationSession(StrEnum):
    """The market phase in which the news became public — timing changes impact."""

    PRE_MARKET = "pre_market"
    DURING_MARKET = "during_market"
    AFTER_MARKET = "after_market"
    WEEKEND = "weekend"
    HOLIDAY = "holiday"


class VerificationStatus(StrEnum):
    """Corroboration state of an event across independent sources."""

    VERIFIED = "verified"  # 2+ independent Tier-1/Tier-2 sources agree
    CORROBORATED = "corroborated"  # 2+ sources of any accepted tier
    SINGLE_SOURCE = "single_source"  # one accepted source
    PENDING = "pending"  # critical event, not yet corroborated
    REJECTED = "rejected"  # only untrusted/unknown sources


class EventType(StrEnum):
    """The classified corporate/market event behind a headline."""

    EARNINGS_BEAT = "earnings_beat"
    EARNINGS_MISS = "earnings_miss"
    GUIDANCE_UPGRADE = "guidance_upgrade"
    GUIDANCE_DOWNGRADE = "guidance_downgrade"
    DIVIDEND = "dividend"
    BUYBACK = "buyback"
    BONUS_ISSUE = "bonus_issue"
    STOCK_SPLIT = "stock_split"
    RIGHTS_ISSUE = "rights_issue"
    ACQUISITION = "acquisition"
    MERGER = "merger"
    REGULATORY_ACTION = "regulatory_action"
    SEBI_ORDER = "sebi_order"
    RBI_ANNOUNCEMENT = "rbi_announcement"
    CEO_CHANGE = "ceo_change"
    CFO_CHANGE = "cfo_change"
    CREDIT_RATING_UPGRADE = "credit_rating_upgrade"
    CREDIT_RATING_DOWNGRADE = "credit_rating_downgrade"
    BULK_DEAL = "bulk_deal"
    BLOCK_DEAL = "block_deal"
    PROMOTER_BUYING = "promoter_buying"
    PROMOTER_SELLING = "promoter_selling"
    GOVERNMENT_TENDER = "government_tender"
    LARGE_ORDER_WIN = "large_order_win"
    LITIGATION = "litigation"
    SECTOR_NEWS = "sector_news"
    GENERAL = "general"  # accepted source, no specific event recognized


@dataclass(frozen=True, slots=True)
class EventProfile:
    """The explainable prior for an event type."""

    polarity: float  # default directional bias in [-1, 1]
    severity: EventSeverity
    horizon: ImpactHorizon
    critical: bool  # requires multi-source verification before full weight
    label: str  # human-readable name


# Priors are deliberately conservative and auditable; the classifier and engine
# refine polarity from the article text, but these defaults make every event's
# baseline judgement explicit.
EVENT_PROFILES: dict[EventType, EventProfile] = {
    EventType.EARNINGS_BEAT: EventProfile(0.6, EventSeverity.HIGH, ImpactHorizon.SWING, True, "Earnings beat"),  # noqa: E501
    EventType.EARNINGS_MISS: EventProfile(-0.6, EventSeverity.HIGH, ImpactHorizon.SWING, True, "Earnings miss"),  # noqa: E501
    EventType.GUIDANCE_UPGRADE: EventProfile(0.55, EventSeverity.HIGH, ImpactHorizon.MEDIUM_TERM, True, "Guidance upgrade"),  # noqa: E501
    EventType.GUIDANCE_DOWNGRADE: EventProfile(-0.55, EventSeverity.HIGH, ImpactHorizon.MEDIUM_TERM, True, "Guidance downgrade"),  # noqa: E501
    EventType.DIVIDEND: EventProfile(0.2, EventSeverity.LOW, ImpactHorizon.SWING, False, "Dividend"),  # noqa: E501
    EventType.BUYBACK: EventProfile(0.4, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, False, "Buyback"),  # noqa: E501
    EventType.BONUS_ISSUE: EventProfile(0.25, EventSeverity.LOW, ImpactHorizon.SWING, False, "Bonus issue"),  # noqa: E501
    EventType.STOCK_SPLIT: EventProfile(0.1, EventSeverity.LOW, ImpactHorizon.SWING, False, "Stock split"),  # noqa: E501
    EventType.RIGHTS_ISSUE: EventProfile(-0.15, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, False, "Rights issue"),  # noqa: E501
    EventType.ACQUISITION: EventProfile(0.35, EventSeverity.HIGH, ImpactHorizon.LONG_TERM, True, "Acquisition"),  # noqa: E501
    EventType.MERGER: EventProfile(0.3, EventSeverity.HIGH, ImpactHorizon.LONG_TERM, True, "Merger"),  # noqa: E501
    EventType.REGULATORY_ACTION: EventProfile(-0.5, EventSeverity.HIGH, ImpactHorizon.MEDIUM_TERM, True, "Regulatory action"),  # noqa: E501
    EventType.SEBI_ORDER: EventProfile(-0.6, EventSeverity.CRITICAL, ImpactHorizon.MEDIUM_TERM, True, "SEBI order"),  # noqa: E501
    EventType.RBI_ANNOUNCEMENT: EventProfile(0.0, EventSeverity.HIGH, ImpactHorizon.MEDIUM_TERM, True, "RBI announcement"),  # noqa: E501
    EventType.CEO_CHANGE: EventProfile(-0.2, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, True, "CEO change"),  # noqa: E501
    EventType.CFO_CHANGE: EventProfile(-0.25, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, True, "CFO change"),  # noqa: E501
    EventType.CREDIT_RATING_UPGRADE: EventProfile(0.4, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, True, "Credit rating upgrade"),  # noqa: E501
    EventType.CREDIT_RATING_DOWNGRADE: EventProfile(-0.5, EventSeverity.HIGH, ImpactHorizon.MEDIUM_TERM, True, "Credit rating downgrade"),  # noqa: E501
    EventType.BULK_DEAL: EventProfile(0.0, EventSeverity.LOW, ImpactHorizon.INTRADAY, False, "Bulk deal"),  # noqa: E501
    EventType.BLOCK_DEAL: EventProfile(0.0, EventSeverity.MEDIUM, ImpactHorizon.SWING, False, "Block deal"),  # noqa: E501
    EventType.PROMOTER_BUYING: EventProfile(0.45, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, True, "Promoter buying"),  # noqa: E501
    EventType.PROMOTER_SELLING: EventProfile(-0.45, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, True, "Promoter selling"),  # noqa: E501
    EventType.GOVERNMENT_TENDER: EventProfile(0.35, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, False, "Government tender"),  # noqa: E501
    EventType.LARGE_ORDER_WIN: EventProfile(0.5, EventSeverity.HIGH, ImpactHorizon.SWING, True, "Large order win"),  # noqa: E501
    EventType.LITIGATION: EventProfile(-0.4, EventSeverity.MEDIUM, ImpactHorizon.MEDIUM_TERM, True, "Litigation"),  # noqa: E501
    EventType.SECTOR_NEWS: EventProfile(0.0, EventSeverity.LOW, ImpactHorizon.SWING, False, "Sector news"),  # noqa: E501
    EventType.GENERAL: EventProfile(0.0, EventSeverity.LOW, ImpactHorizon.SWING, False, "General news"),  # noqa: E501
}


def profile_for(event: EventType) -> EventProfile:
    return EVENT_PROFILES[event]
