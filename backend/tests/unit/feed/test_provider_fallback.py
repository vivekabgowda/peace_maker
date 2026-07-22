"""The feed must degrade to the simulated provider, never crash, when a live
broker is selected without a valid daily token (Sprint 14)."""

from __future__ import annotations

import pytest
from app.core.config import get_settings
from app.feed import service as feed_service
from app.modules.market_data.providers.simulated import SimulatedMarketProvider


class _FakeZerodha:
    """Minimal live-provider stand-in exposing set_access_token."""

    name = "zerodha"
    is_connected = False

    def set_access_token(self, token: str) -> None:  # pragma: no cover - noop
        self._token = token


@pytest.fixture
def _zerodha_no_token(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings().model_copy(
        update={"market_provider": "zerodha", "broker_enc_key": ""}
    )
    monkeypatch.setattr(feed_service, "get_settings", lambda: settings)

    def fake_create(name: str) -> object:
        return (
            _FakeZerodha()
            if name == "zerodha"
            else SimulatedMarketProvider(seed=1, tick_interval=0.0)
        )

    monkeypatch.setattr(feed_service, "create_provider", fake_create)


async def test_feed_falls_back_to_simulated_without_token(_zerodha_no_token: None) -> None:
    feed = feed_service.FeedService(enforce_session=False)
    assert feed._provider.name == "zerodha"  # constructed as the live provider
    await feed._ensure_provider()
    # No valid token ⇒ swapped to simulated instead of crashing.
    assert feed._provider.name == "simulated"


async def test_injected_provider_is_never_swapped(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings().model_copy(update={"market_provider": "zerodha"})
    monkeypatch.setattr(feed_service, "get_settings", lambda: settings)
    injected = SimulatedMarketProvider(seed=2, tick_interval=0.0)
    feed = feed_service.FeedService(provider=injected, enforce_session=False)
    await feed._ensure_provider()
    assert feed._provider is injected  # explicit injection is respected
