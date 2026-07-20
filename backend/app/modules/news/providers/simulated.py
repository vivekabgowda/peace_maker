"""Simulated news provider — deterministic synthetic headlines for the pipeline."""

from __future__ import annotations

import random
from datetime import UTC, datetime

from app.modules.news.providers.base import NewsProvider, RawArticle

_TEMPLATES = [
    ("{sym} posts strong quarterly results, beats estimates", "Banking"),
    ("{sym} shares fall after analyst downgrade on margin concerns", "IT"),
    ("RBI keeps repo rate unchanged; banking stocks react", "Banking"),
    ("{sym} announces record dividend, board approves buyback", "Energy"),
    ("Global cues weak as crude oil prices surge", "Energy"),
    ("{sym} wins large order, management raises FY guidance", "Auto"),
    ("FIIs turn net buyers; Nifty eyes fresh highs", "Index"),
    ("{sym} faces regulatory probe, stock under pressure", "FMCG"),
]
_SYMBOLS = ["RELIANCE", "HDFCBANK", "TCS", "INFY", "ICICIBANK", "SBIN", "TATAMOTORS", "ITC"]


class SimulatedNewsProvider(NewsProvider):
    name = "simulated"

    def __init__(self, *, seed: int | None = None) -> None:
        self._rng = random.Random(seed)

    async def fetch(self) -> list[RawArticle]:
        out: list[RawArticle] = []
        for _ in range(self._rng.randint(2, 5)):
            template, _sector = self._rng.choice(_TEMPLATES)
            symbol = self._rng.choice(_SYMBOLS)
            headline = template.format(sym=symbol)
            out.append(
                RawArticle(
                    headline=headline,
                    body=f"{headline}. Market participants are watching closely.",
                    url=f"https://news.example.com/{abs(hash(headline)) % 10**8}",
                    source="simulated",
                    published_at=datetime.now(UTC),
                )
            )
        return out
