"""Strategy registry — the plugin surface (enable/disable, discovery).

Strategies self-register via :func:`register` (a class decorator). The registry
is the single place the scanner asks "which strategies should run right now?".
Nothing is hardcoded in the scanner: enabling/disabling is data, not code edits.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator

from app.modules.strategy.base import Strategy


class StrategyRegistry:
    """Holds one singleton instance per strategy class and its enabled flag."""

    def __init__(self) -> None:
        self._strategies: dict[str, Strategy] = {}
        self._enabled: dict[str, bool] = {}

    def add(self, strategy: Strategy, *, enabled: bool = True) -> None:
        if strategy.key in self._strategies:
            raise ValueError(f"duplicate strategy key: {strategy.key!r}")
        self._strategies[strategy.key] = strategy
        self._enabled[strategy.key] = enabled

    def get(self, key: str) -> Strategy:
        return self._strategies[key]

    def enable(self, key: str) -> None:
        if key not in self._strategies:
            raise KeyError(key)
        self._enabled[key] = True

    def disable(self, key: str) -> None:
        if key not in self._strategies:
            raise KeyError(key)
        self._enabled[key] = False

    def is_enabled(self, key: str) -> bool:
        return self._enabled.get(key, False)

    def set_enabled_keys(self, keys: Iterable[str]) -> None:
        """Enable exactly ``keys`` (from config); disable everything else."""
        allow = set(keys)
        for key in self._strategies:
            self._enabled[key] = key in allow

    def all(self) -> list[Strategy]:
        return list(self._strategies.values())

    def enabled(self) -> list[Strategy]:
        return [s for k, s in self._strategies.items() if self._enabled.get(k)]

    def keys(self) -> list[str]:
        return list(self._strategies)

    def __len__(self) -> int:
        return len(self._strategies)

    def __iter__(self) -> Iterator[Strategy]:
        return iter(self._strategies.values())


#: The process-wide registry. Strategy modules register into this on import.
registry = StrategyRegistry()


def register(*, enabled: bool = True) -> Callable[[type[Strategy]], type[Strategy]]:
    """Class decorator: instantiate a :class:`Strategy` and add it to the registry.

    Usage::

        @register()
        class OpeningRangeBreakout(Strategy):
            key = "orb"
            ...
    """

    def _wrap(cls: type[Strategy]) -> type[Strategy]:
        registry.add(cls(), enabled=enabled)
        return cls

    return _wrap
