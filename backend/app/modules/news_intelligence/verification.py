"""News Intelligence — multi-source verification (Sprint 11).

Critical events (SEBI orders, M&A, rating actions, earnings) must be corroborated
by more than one *independent* source before they carry full weight. When they
cannot be, the event is marked ``PENDING`` rather than assumed correct — the
platform never front-runs a single unverified rumour.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.news_intelligence.reliability import SourceTier, resolve
from app.modules.news_intelligence.taxonomy import VerificationStatus


def verify(sources: Sequence[str], *, critical: bool) -> VerificationStatus:
    """Determine the corroboration status of one event given its sources.

    ``sources`` are the raw source strings of every article mapped to the event.
    Independence is approximated by distinct registry keys (two ET articles are
    one source; NSE + ET are two).
    """
    profiles = [p for s in sources if (p := resolve(s)) is not None]
    accepted = [p for p in profiles if p.reliability > 0]
    if not accepted:
        return VerificationStatus.REJECTED

    independent = {p.key for p in accepted}
    has_official = any(p.tier <= SourceTier.TIER_2 for p in accepted)

    if len(independent) >= 2 and has_official:
        return VerificationStatus.VERIFIED
    if len(independent) >= 2:
        return VerificationStatus.CORROBORATED
    # A single source: fine for routine events, but a critical event stays PENDING.
    return VerificationStatus.PENDING if critical else VerificationStatus.SINGLE_SOURCE


def confidence_multiplier(status: VerificationStatus) -> float:
    """How much an event's contribution is scaled by its verification state."""
    return {
        VerificationStatus.VERIFIED: 1.0,
        VerificationStatus.CORROBORATED: 0.9,
        VerificationStatus.SINGLE_SOURCE: 0.75,
        VerificationStatus.PENDING: 0.4,
        VerificationStatus.REJECTED: 0.0,
    }[status]
