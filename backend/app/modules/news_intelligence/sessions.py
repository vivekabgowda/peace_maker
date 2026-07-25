"""News Intelligence — market-session awareness (Sprint 11).

*When* news breaks changes how it moves price: the same earnings print at 10:30
(mid-session) versus 18:30 (after close) produces very different tape. This layer
classifies each event's publication window and estimates when the reaction
begins — reusing the shared NSE calendar rather than re-deriving trading hours.
"""

from __future__ import annotations

from datetime import datetime, time

from app.modules.news_intelligence.taxonomy import (
    EventType,
    ImpactTiming,
    PublicationSession,
    profile_for,
)
from app.shared.market_calendar import (
    IST,
    SessionPhase,
    close_time,
    is_holiday,
    is_weekend,
    open_time,
    session_phase,
)


def publication_session(ts: datetime) -> PublicationSession:
    """Classify the market phase in which a timestamp became public (IST)."""
    ist = ts.astimezone(IST)
    d = ist.date()
    if is_weekend(d):
        return PublicationSession.WEEKEND
    if is_holiday(d):
        return PublicationSession.HOLIDAY
    phase = session_phase(ts)
    if phase in (SessionPhase.OPEN, SessionPhase.CLOSING, SessionPhase.MUHURAT):
        return PublicationSession.DURING_MARKET
    t: time = ist.timetz().replace(tzinfo=None)
    if phase is SessionPhase.PRE_OPEN or t < open_time(d):
        return PublicationSession.PRE_MARKET
    if t >= close_time(d):
        return PublicationSession.AFTER_MARKET
    # A trading day, not open, not clearly pre/post (e.g. lunch-less gap) — treat
    # as pre-market so the reaction is attributed to the next tradable moment.
    return PublicationSession.PRE_MARKET


def impact_timing(event: EventType, session: PublicationSession) -> ImpactTiming:
    """Estimate *when* the price reaction begins, from event class + publish window.

    Structural, slow-re-rating events (M&A, ratings, guidance) are multi-day/long
    regardless of clock; time-sensitive prints react at the next tradable moment.
    """
    profile = profile_for(event)
    structural = {
        EventType.ACQUISITION,
        EventType.MERGER,
        EventType.GUIDANCE_UPGRADE,
        EventType.GUIDANCE_DOWNGRADE,
        EventType.CREDIT_RATING_UPGRADE,
        EventType.CREDIT_RATING_DOWNGRADE,
    }
    if event in structural:
        return ImpactTiming.LONG_TERM if profile.horizon.value == "long_term" else ImpactTiming.MULTI_DAY  # noqa: E501

    if session is PublicationSession.DURING_MARKET:
        return ImpactTiming.IMMEDIATE
    if session in (PublicationSession.PRE_MARKET, PublicationSession.AFTER_MARKET):
        return ImpactTiming.NEXT_SESSION
    # Weekend / holiday: digested over the coming sessions.
    return ImpactTiming.MULTI_DAY


def session_weight(session: PublicationSession) -> float:
    """CIO multiplier: identical news counts more when it can act promptly.

    Intraday-actionable news (published during the session) gets full weight;
    weekend/holiday news is discounted because it is diluted by the time the
    market reopens and other information accrues.
    """
    return {
        PublicationSession.DURING_MARKET: 1.0,
        PublicationSession.PRE_MARKET: 0.95,
        PublicationSession.AFTER_MARKET: 0.9,
        PublicationSession.WEEKEND: 0.7,
        PublicationSession.HOLIDAY: 0.7,
    }[session]
