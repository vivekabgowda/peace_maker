"""News Intelligence — the reusable analyst engine (Sprint 11).

`NewsIntelligenceEngine.assess()` is the one entry point the whole platform
calls. Given a symbol and a batch of provider-agnostic :class:`NewsItem`s it
performs the full institutional workflow — reject untrusted sources, classify and
time each event, verify critical events across independent sources, aggregate a
reliability- and recency-weighted score, and emit an explainable
:class:`NewsAssessment` with primary reasons and risk factors.

Pure and deterministic (a clock is injected), so it is trivially testable and can
run anywhere: CIO deliberation, Scanner enrichment, Journal snapshots, Analytics
back-fills, or a future standalone service.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.modules.news_intelligence import metrics
from app.modules.news_intelligence.assessment import (
    EventAssessment,
    NewsAssessment,
    NewsItem,
)
from app.modules.news_intelligence.classifier import classify
from app.modules.news_intelligence.reliability import is_acceptable, reliability_for
from app.modules.news_intelligence.sessions import (
    impact_timing,
    publication_session,
    session_weight,
)
from app.modules.news_intelligence.taxonomy import (
    EventType,
    ImpactHorizon,
    ImpactTiming,
    PublicationSession,
    Sentiment,
    VerificationStatus,
    profile_for,
)
from app.modules.news_intelligence.verification import confidence_multiplier, verify

# Half-life for recency weighting: a day-old headline counts ~half a fresh one.
_RECENCY_HALFLIFE_HOURS = 36.0
_HORIZON_RANK = {
    ImpactHorizon.INTRADAY: 0,
    ImpactHorizon.SWING: 1,
    ImpactHorizon.MEDIUM_TERM: 2,
    ImpactHorizon.LONG_TERM: 3,
}
_TIMING_RANK = {
    ImpactTiming.IMMEDIATE: 0,
    ImpactTiming.NEXT_SESSION: 1,
    ImpactTiming.MULTI_DAY: 2,
    ImpactTiming.LONG_TERM: 3,
}


class NewsIntelligenceEngine:
    """Stateless analyst. Inject a clock for deterministic tests."""

    def __init__(self, *, now: datetime | None = None, lookback_hours: float = 96.0) -> None:
        self._now = now
        self._lookback = timedelta(hours=lookback_hours)

    def _clock(self) -> datetime:
        return self._now or datetime.now(UTC)

    def assess(self, symbol: str, items: Sequence[NewsItem]) -> NewsAssessment:
        now = self._clock()
        horizon_cut = now - self._lookback
        # 1) Accept only trusted, in-window articles.
        usable = [
            it
            for it in items
            if is_acceptable(it.source) and it.published_at.astimezone(UTC) >= horizon_cut
        ]
        if not usable:
            metrics.ASSESSMENTS.labels(result="empty").inc()
            return NewsAssessment.empty(symbol)

        events: list[EventAssessment] = []
        weighted_polarity = 0.0
        weight_sum = 0.0
        reliabilities: list[int] = []
        by_event_sources: dict[EventType, list[str]] = {}

        for it in usable:
            rel = reliability_for(it.source) or 0
            cls = classify(it.headline, it.body)
            sess = publication_session(it.published_at)
            timing = impact_timing(cls.event, sess)
            events.append(
                EventAssessment(
                    event=cls.event,
                    headline=it.headline,
                    source=it.source,
                    reliability=rel,
                    polarity=cls.polarity,
                    session=sess,
                    impact_timing=timing,
                    published_at=it.published_at,
                )
            )
            reliabilities.append(rel)
            by_event_sources.setdefault(cls.event, []).append(it.source)

            prof = profile_for(cls.event)
            w = (
                (rel / 100.0)
                * prof.severity.weight
                * session_weight(sess)
                * _recency_weight(now, it.published_at)
            )
            weighted_polarity += cls.polarity * w
            weight_sum += w

        raw = weighted_polarity / weight_sum if weight_sum else 0.0

        # 2) Verify the single most material event and scale the score by it.
        lead = _lead_event(events)
        status = verify(
            by_event_sources.get(lead.event, [lead.source]),
            critical=profile_for(lead.event).critical,
        )
        raw *= confidence_multiplier(status)

        news_score = int(round(max(-1.0, min(1.0, raw)) * 100))
        agg_reliability = int(round(sum(reliabilities) / len(reliabilities)))
        horizon = max(
            (profile_for(e.event).horizon for e in events), key=lambda h: _HORIZON_RANK[h]
        )
        timing = min((e.impact_timing for e in events), key=lambda t: _TIMING_RANK[t])
        dominant_session = _dominant_session(events)
        confidence = _confidence(agg_reliability, status, len(usable), abs(raw))

        reasons, risks = _explain(events, status, news_score)
        headlines = tuple(
            e.headline for e in sorted(events, key=lambda e: -_event_weight(now, e))[:4]
        )

        metrics.ASSESSMENTS.labels(result="scored").inc()
        metrics.NEWS_SCORE.observe(news_score)
        return NewsAssessment(
            symbol=symbol,
            news_score=news_score,
            sentiment=Sentiment.from_score(raw),
            confidence=confidence,
            source_reliability=agg_reliability,
            verification_status=status,
            impact_horizon=horizon,
            impact_timing=timing,
            dominant_session=dominant_session,
            primary_reasons=reasons,
            risk_factors=risks,
            headlines=headlines,
            events=tuple(events),
            article_count=len(usable),
            generated_at=now,
            meta={"weighted_polarity": raw, "lead_event_weight": _event_weight(now, lead)},
        )


def _recency_weight(now: datetime, published_at: datetime) -> float:
    age_h = max(0.0, (now - published_at.astimezone(UTC)).total_seconds() / 3600.0)
    return float(0.5 ** (age_h / _RECENCY_HALFLIFE_HOURS))


def _event_weight(now: datetime, e: EventAssessment) -> float:
    return (
        (e.reliability / 100.0)
        * profile_for(e.event).severity.weight
        * session_weight(e.session)
        * _recency_weight(now, e.published_at)
    )


def _lead_event(events: list[EventAssessment]) -> EventAssessment:
    """The most material event: highest severity x reliability x |polarity|."""
    return max(
        events,
        key=lambda e: profile_for(e.event).severity.weight
        * (e.reliability / 100.0)
        * abs(e.polarity),
    )


def _dominant_session(events: list[EventAssessment]) -> PublicationSession | None:
    counts: dict[PublicationSession, float] = {}
    for e in events:
        counts[e.session] = counts.get(e.session, 0.0) + e.reliability
    return max(counts, key=lambda s: counts[s]) if counts else None


def _confidence(reliability: int, status: VerificationStatus, n: int, magnitude: float) -> float:
    base = 0.4 + 0.4 * (reliability / 100.0)  # source quality
    base *= confidence_multiplier(status)  # corroboration
    base += min(0.1, 0.03 * (n - 1))  # more corroborating articles
    base += 0.1 * magnitude  # a decisive signal is more confident
    return max(0.05, min(0.98, base))


def _explain(
    events: list[EventAssessment], status: VerificationStatus, score: int
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Turn the top events into institutional-analyst prose (no black box)."""
    reasons: list[str] = []
    risks: list[str] = []
    for e in sorted(events, key=lambda e: -profile_for(e.event).severity.weight)[:4]:
        prof = profile_for(e.event)
        if e.event is EventType.GENERAL:
            continue
        verb = "supports" if e.polarity > 0 else "weighs on" if e.polarity < 0 else "is neutral for"
        reasons.append(
            f"{prof.label} ({e.source}) {verb} the name — {e.impact_timing.label.lower()}."
        )
    if not reasons:
        reasons.append("General news flow with no single decisive corporate event.")

    if status is VerificationStatus.PENDING:
        risks.append("Lead event is not yet corroborated by a second independent source (pending).")
    if status is VerificationStatus.SINGLE_SOURCE:
        risks.append("Signal rests on a single source — confirmation would raise conviction.")
    neg = [e for e in events if e.polarity < -0.2]
    if neg and score > 0:
        risks.append("Conflicting negative headlines present despite a net-positive score.")
    weekend = [e for e in events if e.session.value in ("weekend", "holiday")]
    if weekend:
        risks.append("Key news broke out of hours; the open may gap and re-rate abruptly.")
    return tuple(reasons), tuple(risks)
