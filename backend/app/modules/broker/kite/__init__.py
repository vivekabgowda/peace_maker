"""Real Kite Connect SDK adapters — imported lazily, never at package load.

Importing this subpackage does NOT import ``kiteconnect``; the SDK is imported
only when :func:`build_kite_http` / :func:`build_ticker_factory` are called, and a
clear :class:`ProviderError` is raised if the optional dependency is missing. This
keeps the platform installable and fully testable (via fake ports) without the SDK
or any network access to Zerodha.
"""

from __future__ import annotations

from app.modules.broker.kite.adapters import build_kite_http, build_ticker

__all__ = ["build_kite_http", "build_ticker"]
