"""News provider abstraction and registry."""

from collections.abc import Callable

from app.modules.news.providers.base import NewsProvider, RawArticle
from app.modules.news.providers.simulated import SimulatedNewsProvider

_REGISTRY: dict[str, Callable[[], NewsProvider]] = {
    "simulated": SimulatedNewsProvider,
    # Future: "moneycontrol", "economic_times", "reuters", "rss", "telegram" ...
}


def create_news_provider(name: str) -> NewsProvider:
    try:
        return _REGISTRY[name]()
    except KeyError as exc:
        raise ValueError(f"Unknown news provider '{name}'") from exc


def available_news_providers() -> list[str]:
    return sorted(_REGISTRY)


__all__ = [
    "NewsProvider",
    "RawArticle",
    "SimulatedNewsProvider",
    "available_news_providers",
    "create_news_provider",
]
