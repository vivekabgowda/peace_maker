"""News Intelligence — source reliability engine (Sprint 11).

Every source is scored 0-100 and bucketed into a trust tier. Unknown sources are
*rejected* (score ``None``) rather than trusted by default — the platform must
never act on an unverifiable rumour. The CIO weights news by this reliability, so
an official NSE filing dominates a financial blog.

Matching is by normalized-substring against a curated registry, so a source
string like "NSE Corporate Announcements" or "nseindia.com" both resolve to the
NSE entry. Extending trust is data-only: add a row to ``_REGISTRY``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class SourceTier(IntEnum):
    """Trust tiers per the Sprint 11 source hierarchy (lower = more trusted)."""

    TIER_1 = 1  # official: exchanges, filings, regulators
    TIER_2 = 2  # press releases, major financial press, govt notifications
    TIER_3 = 3  # global macro / secondary reporting
    UNTRUSTED = 9  # social media / blogs — never sufficient on their own


@dataclass(frozen=True, slots=True)
class SourceProfile:
    key: str  # canonical id
    display: str
    tier: SourceTier
    reliability: int  # 0-100
    aliases: tuple[str, ...]  # normalized substrings that resolve here


# Curated registry. Reliability scores mirror the spec's institutional ranking.
_REGISTRY: tuple[SourceProfile, ...] = (
    # --- Tier 1 (official / highest priority) ---
    SourceProfile(
        "nse",
        "NSE Corporate Announcements",
        SourceTier.TIER_1,
        100,
        ("nse", "national stock exchange", "nseindia"),
    ),
    SourceProfile(
        "bse",
        "BSE Corporate Announcements",
        SourceTier.TIER_1,
        100,
        ("bse", "bombay stock exchange", "bseindia"),
    ),
    SourceProfile("sebi", "SEBI", SourceTier.TIER_1, 100, ("sebi",)),
    SourceProfile("rbi", "RBI", SourceTier.TIER_1, 100, ("rbi", "reserve bank")),
    SourceProfile(
        "company_filing",
        "Company Filing",
        SourceTier.TIER_1,
        98,
        ("filing", "regulatory filing", "exchange filing", "disclosure"),
    ),
    SourceProfile(
        "results",
        "Quarterly Results / Annual Report",
        SourceTier.TIER_1,
        98,
        ("quarterly result", "annual report", "results filing", "financial result"),
    ),
    SourceProfile(
        "investor_presentation",
        "Investor Presentation",
        SourceTier.TIER_1,
        95,
        ("investor presentation", "investor deck", "earnings call"),
    ),
    SourceProfile(
        "corporate_action",
        "Corporate Action",
        SourceTier.TIER_1,
        96,
        ("corporate action", "record date", "ex-date"),
    ),
    # --- Tier 2 (press releases, major financial press, govt) ---
    SourceProfile(
        "press_release",
        "Company Press Release",
        SourceTier.TIER_2,
        88,
        ("press release", "company statement", "official statement"),
    ),
    SourceProfile(
        "govt",
        "Government Notification",
        SourceTier.TIER_2,
        90,
        ("ministry", "government of india", "gazette", "pib", "notification"),
    ),
    SourceProfile(
        "et",
        "Economic Times",
        SourceTier.TIER_2,
        90,
        ("economic times", "economictimes", "et markets"),
    ),
    SourceProfile("bs", "Business Standard", SourceTier.TIER_2, 89, ("business standard",)),
    SourceProfile("mint", "Livemint", SourceTier.TIER_2, 88, ("mint", "livemint")),
    SourceProfile("moneycontrol", "Moneycontrol", SourceTier.TIER_2, 85, ("moneycontrol",)),
    SourceProfile(
        "bql",
        "Bloomberg / Reuters",
        SourceTier.TIER_2,
        90,
        ("bloomberg", "reuters", "bqprime", "bq prime"),
    ),
    # --- Tier 3 (global macro / secondary) ---
    SourceProfile(
        "global_macro",
        "Global Macro Wire",
        SourceTier.TIER_3,
        75,
        ("fed", "federal reserve", "ecb", "imf", "opec", "crude", "us cpi"),
    ),
    SourceProfile("wire", "Secondary Wire", SourceTier.TIER_3, 65, ("ians", "pti", "ani")),
    # --- Explicitly untrusted (rejected on their own) ---
    SourceProfile(
        "blog",
        "Financial Blog",
        SourceTier.UNTRUSTED,
        60,
        ("blog", "blogspot", "wordpress", "medium.com", "substack"),
    ),
    SourceProfile(
        "social",
        "Social Media",
        SourceTier.UNTRUSTED,
        0,
        ("twitter", "x.com", "telegram", "whatsapp", "reddit", "youtube", "facebook"),
    ),
)


def _normalize(source: str) -> str:
    return " ".join(source.lower().split())


def resolve(source: str) -> SourceProfile | None:
    """Return the registry profile for a raw source string, or ``None`` if unknown."""
    norm = _normalize(source)
    if not norm:
        return None
    # Rank candidates by trust first (an official regulator name outranks a generic
    # "press release"), then by longest matching alias for specificity.
    best: SourceProfile | None = None
    best_key: tuple[int, int] | None = None
    for profile in _REGISTRY:
        matched = [a for a in profile.aliases if a in norm]
        if not matched:
            continue
        key = (int(profile.tier), -max(len(a) for a in matched))
        if best_key is None or key < best_key:
            best, best_key = profile, key
    return best


def reliability_for(source: str) -> int | None:
    """Reliability 0-100, or ``None`` when the source is unknown/rejected.

    Untrusted-tier sources return their nominal score but callers must treat them
    as insufficient on their own (see :func:`is_acceptable`). Unknown sources
    return ``None`` — the engine drops them entirely.
    """
    profile = resolve(source)
    return profile.reliability if profile else None


def tier_for(source: str) -> SourceTier | None:
    profile = resolve(source)
    return profile.tier if profile else None


def is_acceptable(source: str) -> bool:
    """Whether a source may contribute to a score at all.

    Unknown sources and zero-reliability social feeds are rejected outright;
    everything else contributes (weighted by reliability).
    """
    profile = resolve(source)
    return profile is not None and profile.reliability > 0
