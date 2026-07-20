"""News normalization: dedup id, category, sentiment, impact, entity mapping.

Pure, deterministic, dependency-free — a lightweight lexicon/keyword approach
suitable as a baseline. A later sprint can swap the sentiment scorer for an LLM
behind this same interface without changing callers.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

# Known universe for entity mapping (kept in sync with the instrument master).
_SYMBOLS = {
    "RELIANCE",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "TCS",
    "INFY",
    "TATAMOTORS",
    "ITC",
    "NIFTY",
    "BANKNIFTY",
    "SENSEX",
}
_SECTOR_KEYWORDS = {
    "Banking": ["bank", "rbi", "repo", "nbfc", "lending", "deposit"],
    "IT": ["it ", "software", "tech", "infosys", "tcs", "wipro"],
    "Energy": ["oil", "crude", "energy", "gas", "reliance", "power"],
    "Auto": ["auto", "vehicle", "car", "ev", "motors"],
    "FMCG": ["fmcg", "consumer", "itc", "hindustan unilever"],
}
_SYMBOL_SECTOR = {
    "HDFCBANK": "Banking",
    "ICICIBANK": "Banking",
    "SBIN": "Banking",
    "TCS": "IT",
    "INFY": "IT",
    "RELIANCE": "Energy",
    "TATAMOTORS": "Auto",
    "ITC": "FMCG",
}

_POSITIVE = {
    "beats",
    "strong",
    "record",
    "surge",
    "gain",
    "wins",
    "raises",
    "buyback",
    "dividend",
    "growth",
    "profit",
    "upgrade",
    "rally",
    "high",
    "buyers",
}
_NEGATIVE = {
    "falls",
    "fall",
    "downgrade",
    "probe",
    "concerns",
    "weak",
    "pressure",
    "loss",
    "decline",
    "cut",
    "miss",
    "slump",
    "fraud",
    "penalty",
}
_CATEGORY_RULES = [
    ("earnings", ["results", "quarterly", "profit", "estimates", "guidance"]),
    ("policy", ["rbi", "repo", "sebi", "regulatory", "probe", "policy"]),
    ("corporate_action", ["dividend", "buyback", "merger", "order", "acquisition"]),
    ("macro", ["crude", "oil", "fii", "global", "inflation", "gdp"]),
]
_HIGH_IMPACT = {"rbi", "repo", "downgrade", "probe", "buyback", "results", "fraud", "guidance"}


@dataclass(frozen=True)
class NormalizedArticle:
    id: str
    headline: str
    category: str
    sentiment: float  # [-1, 1]
    impact: float  # [0, 1]
    symbols: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)


def content_id(headline: str, source: str) -> str:
    """Stable dedup id from normalized headline + source."""
    norm = re.sub(r"\s+", " ", headline.strip().lower())
    return hashlib.sha256(f"{source}:{norm}".encode()).hexdigest()[:32]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z]+", text.lower())


def score_sentiment(text: str) -> float:
    tokens = _tokens(text)
    if not tokens:
        return 0.0
    pos = sum(1 for t in tokens if t in _POSITIVE)
    neg = sum(1 for t in tokens if t in _NEGATIVE)
    if pos + neg == 0:
        return 0.0
    return round((pos - neg) / (pos + neg), 3)


def score_impact(text: str) -> float:
    lowered = text.lower()
    hits = sum(1 for kw in _HIGH_IMPACT if kw in lowered)
    return round(min(1.0, 0.3 + 0.2 * hits), 3)


def categorize(text: str) -> str:
    lowered = text.lower()
    for category, keywords in _CATEGORY_RULES:
        if any(kw in lowered for kw in keywords):
            return category
    return "general"


def map_symbols(text: str) -> list[str]:
    upper = text.upper()
    return sorted({s for s in _SYMBOLS if re.search(rf"\b{s}\b", upper)})


def map_sectors(text: str, symbols: list[str]) -> list[str]:
    lowered = text.lower()
    found = {sector for sector, kws in _SECTOR_KEYWORDS.items() if any(k in lowered for k in kws)}
    found.update(_SYMBOL_SECTOR[s] for s in symbols if s in _SYMBOL_SECTOR)
    return sorted(found)


def normalize(headline: str, body: str | None, source: str) -> NormalizedArticle:
    """Turn a raw article into an enriched, deduplicable record."""
    text = f"{headline} {body or ''}"
    symbols = map_symbols(text)
    return NormalizedArticle(
        id=content_id(headline, source),
        headline=headline,
        category=categorize(text),
        sentiment=score_sentiment(text),
        impact=score_impact(text),
        symbols=symbols,
        sectors=map_sectors(text, symbols),
    )
