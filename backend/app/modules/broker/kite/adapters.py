"""Thin wrappers around the ``kiteconnect`` SDK (Sprint 6).

Each builder lazily imports the SDK and raises a helpful :class:`ProviderError` if
it is not installed (`pip install .[zerodha]`). The wrappers expose exactly the
:class:`KiteHttpPort` / :class:`KiteTickerPort` surface — **no order methods are
wrapped or exposed.**
"""

from __future__ import annotations

from typing import Any

from app.modules.broker.ports import KiteHttpPort, KiteTickerPort
from app.modules.market_data.providers.base import ProviderError


def _import_sdk() -> Any:
    try:
        import kiteconnect
    except ImportError as exc:  # pragma: no cover - exercised only without the SDK
        raise ProviderError(
            "The Zerodha SDK is not installed. Install it with: pip install '.[zerodha]' "
            "(package: kiteconnect)."
        ) from exc
    return kiteconnect


def build_kite_http(api_key: str) -> KiteHttpPort:
    """Build a :class:`KiteHttpPort` backed by ``KiteConnect`` (no order methods)."""
    sdk = _import_sdk()
    kc = sdk.KiteConnect(api_key=api_key)

    class _Http:
        def login_url(self) -> str:
            return str(kc.login_url())

        def generate_session(self, request_token: str, api_secret: str) -> dict[str, Any]:
            return dict(kc.generate_session(request_token, api_secret=api_secret))

        def set_access_token(self, access_token: str) -> None:
            kc.set_access_token(access_token)

        def profile(self) -> dict[str, Any]:
            return dict(kc.profile())

        def instruments(self, exchange: str | None = None) -> list[dict[str, Any]]:
            return list(kc.instruments(exchange) if exchange else kc.instruments())

        def historical_data(
            self,
            instrument_token: int,
            from_date: Any,
            to_date: Any,
            interval: str,
            continuous: bool = False,
        ) -> list[dict[str, Any]]:
            return list(
                kc.historical_data(instrument_token, from_date, to_date, interval, continuous)
            )

        def quote(self, instruments: list[str]) -> dict[str, Any]:
            return dict(kc.quote(instruments))

    return _Http()


def build_ticker(api_key: str, access_token: str) -> KiteTickerPort:
    """Build a fresh :class:`KiteTickerPort` (KiteTicker) for (api_key, token).

    The SDK's own reconnect is disabled — the platform drives reconnect with its
    own bounded exponential backoff (see ``ZerodhaProvider``).
    """
    sdk = _import_sdk()
    ticker: KiteTickerPort = sdk.KiteTicker(api_key, access_token, reconnect=False)
    return ticker
