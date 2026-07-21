"""Strategy library — importing this package registers every strategy plugin.

The scanner imports :mod:`app.modules.strategy.library` once at startup; each
submodule uses ``@register()`` so the global registry is fully populated as a
side effect. Adding a strategy = adding a module here, nothing else.
"""

from __future__ import annotations

from app.modules.strategy.library import (
    breakout,
    gap,
    momentum,
    trend,
    volatility,
)

__all__ = ["breakout", "gap", "momentum", "trend", "volatility"]
