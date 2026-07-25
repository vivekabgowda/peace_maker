"""News Intelligence — deterministic event classifier (Sprint 11).

Maps a headline (+ optional body) to an :class:`EventType` and a text-refined
polarity, using an ordered rule table of keyword patterns. Deterministic and
side-effect-free so it is fully unit-testable and explainable — the matched
phrase is returned as the citation. The ``Agent`` design note in the committee
applies here too: this rule engine can later be swapped for an LLM classifier
behind the same interface without touching the engine or its consumers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.modules.news_intelligence.taxonomy import EventType, profile_for


@dataclass(frozen=True, slots=True)
class Classification:
    event: EventType
    polarity: float  # -1..1, text-refined from the event prior
    matched: str  # the phrase that fired the rule (explainability)


# Ordered: the first matching rule wins, so specific patterns precede generic
# ones. Each rule is (compiled pattern, event, optional polarity override).
_RULES: list[tuple[re.Pattern[str], EventType, float | None]] = [
    (re.compile(r"\b(profit|pat|net income|revenue|earnings|q[1-4]|quarter)\w*\b.*\b(beat|surpass|exceed|top|above|jump|surg|ros|rise|grew|grow)\w*"), EventType.EARNINGS_BEAT, None),  # noqa: E501
    (re.compile(r"\b(profit|pat|net income|revenue|earnings|q[1-4]|quarter)\w*\b.*\b(miss|below|fell|fall|drop|declin|slump|plunge|disappoint)\w*"), EventType.EARNINGS_MISS, None),  # noqa: E501
    (re.compile(r"\b(raise[sd]?|hike[sd]?|upgrade[sd]?)\b.*\bguidance\b|\bguidance\b.*\b(raise|hike|upgrade|rais)"), EventType.GUIDANCE_UPGRADE, None),  # noqa: E501
    (re.compile(r"\b(cut|lower|slash|downgrade)[sd]?\b.*\bguidance\b|\bguidance\b.*\b(cut|lower|slash|downgrade)"), EventType.GUIDANCE_DOWNGRADE, None),  # noqa: E501
    (re.compile(r"\bbuy ?back\b|\bshare repurchase\b"), EventType.BUYBACK, None),
    (re.compile(r"\bbonus (issue|share)\b"), EventType.BONUS_ISSUE, None),
    (re.compile(r"\bstock split\b|\bsub-?division of shares\b"), EventType.STOCK_SPLIT, None),
    (re.compile(r"\brights issue\b"), EventType.RIGHTS_ISSUE, None),
    (re.compile(r"\b(interim |final )?dividend\b"), EventType.DIVIDEND, None),
    (re.compile(r"\b(acquire[sd]?|acquisition|to buy|takeover|stake in)\b"), EventType.ACQUISITION, None),  # noqa: E501
    (re.compile(r"\bmerger\b|\bto merge\b|\bamalgamation\b"), EventType.MERGER, None),
    (re.compile(r"\bsebi\b.*\b(order|ban|penalt|show cause|bars?)\b"), EventType.SEBI_ORDER, None),
    (re.compile(r"\brbi\b.*\b(repo|policy|rate|announce|circular|guideline)\b"), EventType.RBI_ANNOUNCEMENT, None),  # noqa: E501
    (re.compile(r"\b(regulat\w+|probe|investigat\w+|penalt\w+|show cause|raid)\b"), EventType.REGULATORY_ACTION, None),  # noqa: E501
    (re.compile(r"\b(cfo|finance (head|chief))\b.*\b(resign|step\s?down|quit|appoint|exit|depart)\w*"), EventType.CFO_CHANGE, None),  # noqa: E501
    (re.compile(r"\b(ceo|managing director|\bmd\b)\b.*\b(resign|step\s?down|quit|appoint|exit|depart)\w*"), EventType.CEO_CHANGE, None),  # noqa: E501
    (re.compile(r"\b(rating|outlook)\b.*\b(upgrade|raised|improved)\b|\bupgrade[sd]?\b.*\brating\b"), EventType.CREDIT_RATING_UPGRADE, None),  # noqa: E501
    (re.compile(r"\b(rating|outlook)\b.*\b(downgrade|cut|lowered)\b|\bdowngrade[sd]?\b.*\brating\b"), EventType.CREDIT_RATING_DOWNGRADE, None),  # noqa: E501
    (re.compile(r"\bpromoter\b.*\b(buy|acquir|increas\w* stake|infus|rais\w* stake)\w*"), EventType.PROMOTER_BUYING, None),  # noqa: E501
    (re.compile(r"\bpromoter\b.*\b(sell|sold|sale|pledg|offload|reduc\w* stake|stake sale)\w*"), EventType.PROMOTER_SELLING, None),  # noqa: E501
    (re.compile(r"\bblock deal\b"), EventType.BLOCK_DEAL, None),
    (re.compile(r"\bbulk deal\b"), EventType.BULK_DEAL, None),
    (re.compile(r"\b(order win|bags? .*order|wins? .*(order|contract|tender)|awarded .*(contract|order))\b"), EventType.LARGE_ORDER_WIN, None),  # noqa: E501
    (re.compile(r"\b(government|govt|psu)\b.*\btender\b"), EventType.GOVERNMENT_TENDER, None),
    (re.compile(r"\b(lawsuit|litigation|court|tribunal|nclt|insolvency|arbitration)\b"), EventType.LITIGATION, None),  # noqa: E501
    (re.compile(r"\bsector\b|\bindustry\b|\bpeers\b"), EventType.SECTOR_NEWS, None),
]

# Sentiment modifiers that nudge polarity within an event class.
_POSITIVE = re.compile(r"\b(surge|jump|soar|rally|record|strong|robust|beat|win|wins|expand|approval|approved|upgrade|raise[sd]?)\b")  # noqa: E501
_NEGATIVE = re.compile(r"\b(plunge|slump|crash|weak|miss|loss|fraud|default|downgrade|ban|penalt|probe|cut|resign|delay|recall|halt)\b")  # noqa: E501


def classify(headline: str, body: str | None = None) -> Classification:
    """Classify one article. Falls back to ``GENERAL`` with text-only polarity."""
    text = f"{headline} {body or ''}".lower()
    for pattern, event, override in _RULES:
        if pattern.search(text):
            base = profile_for(event).polarity if override is None else override
            return Classification(event=event, polarity=_refine(base, text), matched=pattern.pattern[:48])  # noqa: E501
    # No specific event — score purely on sentiment words.
    return Classification(event=EventType.GENERAL, polarity=_refine(0.0, text), matched="general")


def _refine(base: float, text: str) -> float:
    """Blend the event prior with headline sentiment words, clamped to [-1, 1]."""
    nudge = 0.0
    if _POSITIVE.search(text):
        nudge += 0.2
    if _NEGATIVE.search(text):
        nudge -= 0.25
    # When the prior is neutral, sentiment words drive the sign outright.
    value = base + nudge if base != 0.0 else nudge * 1.5
    return max(-1.0, min(1.0, value))
