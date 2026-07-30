"""Tier-1 official news providers (Sprint 11 pt.2).

Plugin adapters for the highest-trust sources — NSE/BSE corporate announcements
and RBI/SEBI notifications — over the same :class:`NewsProvider` interface. Each
declares its endpoint and a field map; a shared base fetches and normalizes into
:class:`RawArticle`s tagged with a canonical ``source`` the reliability engine
scores at Tier-1 (100). The HTTP transport is injectable so parsing is unit-tested
against fixtures with no network; wiring live endpoints/headers is an ops step.

Adding a new official source = a new subclass with an endpoint + field map. No
core change.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from app.core.logging import get_logger
from app.modules.news.providers.base import NewsProvider, RawArticle

logger = get_logger("news.official")


@runtime_checkable
class NewsTransport(Protocol):
    """Minimal async HTTP-JSON transport (injectable for tests)."""

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any: ...


class HttpxNewsTransport:
    """Default transport backed by httpx. Lazily imported so tests need no network."""

    def __init__(self, *, timeout: float = 10.0) -> None:
        self._timeout = timeout

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        import httpx

        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()


def _first(record: dict[str, Any], keys: Sequence[str]) -> str | None:
    for k in keys:
        v = record.get(k)
        if v:
            return str(v)
    return None


def _parse_dt(value: str | None) -> datetime:
    if not value:
        return datetime.now(UTC)
    for fmt in ("%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return datetime.now(UTC)


class OfficialNewsProvider(NewsProvider):
    """Base for endpoint-backed official providers. Subclasses set the class attrs."""

    name: str = "official"
    endpoint: str = ""
    list_key: str | None = None  # if the payload wraps records in a key
    headline_keys: Sequence[str] = ("headline", "subject", "desc", "title")
    body_keys: Sequence[str] = ("body", "attchmntText", "smText", "description", "moreLink")
    url_keys: Sequence[str] = ("url", "attchmntFile", "link")
    date_keys: Sequence[str] = ("an_dt", "date", "pubDate", "dt", "published_at")
    symbol_keys: Sequence[str] = ("symbol", "scrip", "sm_name")

    def __init__(self, transport: NewsTransport | None = None) -> None:
        self._transport = transport or HttpxNewsTransport()

    def _records(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [r for r in payload if isinstance(r, dict)]
        if isinstance(payload, dict):
            seq = payload.get(self.list_key) if self.list_key else payload.get("data")
            if isinstance(seq, list):
                return [r for r in seq if isinstance(r, dict)]
        return []

    def _to_article(self, record: dict[str, Any]) -> RawArticle | None:
        headline = _first(record, self.headline_keys)
        if not headline:
            return None
        symbol = _first(record, self.symbol_keys)
        headline = (
            f"{symbol}: {headline}"
            if symbol and symbol.upper() not in headline.upper()
            else headline
        )
        return RawArticle(
            headline=headline.strip(),
            body=_first(record, self.body_keys),
            url=_first(record, self.url_keys),
            source=self.name,
            published_at=_parse_dt(_first(record, self.date_keys)),
        )

    async def fetch(self) -> list[RawArticle]:
        if not self.endpoint:
            return []
        try:
            payload = await self._transport.get_json(self.endpoint)
        except Exception as exc:  # network/transport errors must not sink the feed
            logger.warning("official_news_fetch_failed", provider=self.name, error=str(exc))
            return []
        articles = [a for r in self._records(payload) if (a := self._to_article(r))]
        logger.info("official_news_fetched", provider=self.name, count=len(articles))
        return articles


class NSEAnnouncementsProvider(OfficialNewsProvider):
    name = "nse"
    endpoint = "https://www.nseindia.com/api/corporate-announcements?index=equities"
    headline_keys = ("subject", "desc", "attchmntText", "headline")
    body_keys = ("attchmntText", "smText", "desc")
    url_keys = ("attchmntFile", "url")
    date_keys = ("an_dt", "sort_date", "date")
    symbol_keys = ("symbol", "sm_name")


class BSEAnnouncementsProvider(OfficialNewsProvider):
    name = "bse"
    endpoint = "https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w"
    list_key = "Table"
    headline_keys = ("HEADLINE", "NEWSSUB", "MORE")
    body_keys = ("MORE", "HEADLINE")
    url_keys = ("ATTACHMENTNAME", "NSURL")
    date_keys = ("NEWS_DT", "DT_TM")
    symbol_keys = ("SCRIP_CD", "SLONGNAME")


class RBIProvider(OfficialNewsProvider):
    name = "rbi"
    endpoint = "https://website.rbi.org.in/en/web/rbi/press-releases?json=1"
    list_key = "items"
    headline_keys = ("title", "subject", "headline")
    body_keys = ("summary", "description", "body")
    url_keys = ("link", "url")
    date_keys = ("date", "pubDate", "published_at")
    symbol_keys = ()


class SEBIProvider(OfficialNewsProvider):
    name = "sebi"
    endpoint = "https://www.sebi.gov.in/sebiweb/other/OtherAction.do?doRss=yes&type=1"
    list_key = "items"
    headline_keys = ("title", "subject", "headline")
    body_keys = ("summary", "description", "body")
    url_keys = ("link", "url")
    date_keys = ("date", "pubDate", "published_at")
    symbol_keys = ()


OFFICIAL_PROVIDERS: dict[str, type[OfficialNewsProvider]] = {
    "nse": NSEAnnouncementsProvider,
    "bse": BSEAnnouncementsProvider,
    "rbi": RBIProvider,
    "sebi": SEBIProvider,
}
