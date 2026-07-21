"""News provider abstraction.

Concrete providers (Moneycontrol, Economic Times, Reuters, Bloomberg, generic
RSS, Telegram feeds) implement this port. Downstream code depends only on the
normalized :class:`RawArticle`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from pydantic import BaseModel


class RawArticle(BaseModel):
    headline: str
    body: str | None = None
    url: str | None = None
    source: str
    published_at: datetime


class NewsProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def fetch(self) -> list[RawArticle]:
        """Return the latest batch of raw articles from the source."""
