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


# Broker providers live in app.modules.broker and register lazily to avoid a
# market_data → broker import cycle at module load (and to keep the Kite SDK out
# of the import path unless a broker provider is actually requested).
_BROKER_PROVIDERS = frozenset({"zerodha", "paper"})


def _ensure_registered(name: str) -> None:
    if name in _REGISTRY or name not in _BROKER_PROVIDERS:
        return
    from app.modules.broker.factory import register_broker_providers

    register_broker_providers()


def create_provider(name: str) -> MarketProvider:
    _ensure_registered(name)
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown market provider '{name}'. Available: {available_providers()}"
        ) from exc
    return factory()
