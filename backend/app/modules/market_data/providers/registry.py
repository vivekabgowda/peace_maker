"""Provider registry — resolves a :class:`MarketProvider` by name.

The active provider is chosen by configuration (``BKN_MARKET_PROVIDER``), so no
application code imports a concrete provider. New brokers register here.
"""

from __future__ import annotations

from collections.abc import Callable

from app.modules.market_data.providers.base import MarketProvider
from app.modules.market_data.providers.simulated import SimulatedMarketProvider

_REGISTRY: dict[str, Callable[[], MarketProvider]] = {
    "simulated": SimulatedMarketProvider,
    # Future: "zerodha": ZerodhaProvider, "upstox": UpstoxProvider, ...
}


def register_provider(name: str, factory: Callable[[], MarketProvider]) -> None:
    _REGISTRY[name] = factory


def available_providers() -> list[str]:
    return sorted(_REGISTRY)


def create_provider(name: str) -> MarketProvider:
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown market provider '{name}'. Available: {available_providers()}"
        ) from exc
    return factory()
