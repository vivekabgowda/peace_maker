"""Tier-1 official news provider adapters — parsing via injected transport."""

from __future__ import annotations

from typing import Any

import pytest
from app.modules.news.providers import available_news_providers, create_news_provider
from app.modules.news.providers.official import (
    BSEAnnouncementsProvider,
    NSEAnnouncementsProvider,
    RBIProvider,
)
from app.modules.news_intelligence import reliability_for


class _FakeTransport:
    def __init__(self, payload: Any) -> None:
        self._payload = payload
        self.calls: list[str] = []

    async def get_json(self, url: str, *, params: Any = None, headers: Any = None) -> Any:
        self.calls.append(url)
        return self._payload


async def test_nse_provider_parses_announcements_and_tags_source() -> None:
    payload = [
        {
            "symbol": "RELIANCE",
            "subject": "Board approves buyback",
            "an_dt": "24-Jul-2026 10:30:00",
        },
        {
            "symbol": "TCS",
            "subject": "Q1 results: profit beats estimates",
            "an_dt": "24-Jul-2026 18:30:00",
        },
    ]
    provider = NSEAnnouncementsProvider(_FakeTransport(payload))
    articles = await provider.fetch()
    assert len(articles) == 2
    assert all(a.source == "nse" for a in articles)
    assert "RELIANCE" in articles[0].headline
    # Source must be Tier-1 (100) in the reliability engine.
    assert reliability_for("nse") == 100


async def test_bse_provider_unwraps_table_key() -> None:
    payload = {
        "Table": [
            {"SLONGNAME": "INFY", "HEADLINE": "Dividend declared", "NEWS_DT": "2026-07-24 09:00:00"}
        ]
    }
    provider = BSEAnnouncementsProvider(_FakeTransport(payload))
    articles = await provider.fetch()
    assert len(articles) == 1
    assert articles[0].source == "bse"


async def test_provider_survives_transport_error() -> None:
    class _Boom:
        async def get_json(self, url: str, *, params: Any = None, headers: Any = None) -> Any:
            raise RuntimeError("network down")

    assert await RBIProvider(_Boom()).fetch() == []  # degrades to empty, never raises


async def test_records_ignores_malformed_payload() -> None:
    assert await NSEAnnouncementsProvider(_FakeTransport("not-json-list")).fetch() == []


@pytest.mark.parametrize("name", ["nse", "bse", "rbi", "sebi"])
def test_official_providers_are_registered(name: str) -> None:
    assert name in available_news_providers()
    assert create_news_provider(name).name == name
