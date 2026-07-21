"""Wire the broker providers into the market-data provider registry (Sprint 6).

Registered lazily (only when a broker provider is actually requested) so that
neither the API nor the feed process imports the Kite SDK unless ``zerodha`` is the
configured provider. ``paper`` is an explicit alias for the built-in simulator.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.modules.market_data.providers.base import MarketProvider, ProviderError
from app.modules.market_data.providers.registry import register_provider
from app.modules.market_data.providers.simulated import SimulatedMarketProvider


def build_zerodha_provider() -> MarketProvider:
    """Construct a live Zerodha market-data provider from settings (no token yet).

    The daily access token is attached later (after the login flow) via
    ``provider.set_access_token(...)`` — see the feed wiring and the setup guide.
    """
    from app.modules.broker.kite import build_kite_http, build_ticker
    from app.modules.broker.provider import ZerodhaProvider

    settings = get_settings()
    if not settings.zerodha_api_key:
        raise ProviderError("BKN_ZERODHA_API_KEY is not configured.")
    http = build_kite_http(settings.zerodha_api_key)
    return ZerodhaProvider(
        http,
        build_ticker,
        api_key=settings.zerodha_api_key,
        fno=set(settings.broker_watchlist),
    )


def register_broker_providers() -> None:
    """Idempotently register ``zerodha`` and ``paper`` in the provider registry."""
    register_provider("zerodha", build_zerodha_provider)
    register_provider("paper", SimulatedMarketProvider)
