"""Zerodha Kite Connect OAuth login flow (Sprint 6).

Kite's login is a redirect flow:

1. Redirect the user to the hosted Kite login URL (``login_url()``).
2. Kite authenticates the user and redirects back to our ``redirect_url`` with a
   short-lived ``request_token``.
3. We exchange ``request_token`` + ``api_secret`` (via a SHA-256 checksum, computed
   inside the SDK's ``generate_session``) for a per-day ``access_token``.

There is **no refresh token** in Kite Connect — the access token is valid for the
trading day and is re-minted by repeating this flow (typically once each morning).
The resulting session is stored **encrypted** via the token store.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.modules.broker.ports import KiteHttpPort
from app.modules.broker.token_store import BrokerSession, TokenStore, kite_token_expiry

logger = get_logger("broker.auth")


class ZerodhaAuth:
    """Drives the Kite login flow and persists the encrypted session."""

    BROKER = "zerodha"

    def __init__(self, http: KiteHttpPort, api_secret: str, store: TokenStore) -> None:
        self._http = http
        self._api_secret = api_secret
        self._store = store

    def login_url(self) -> str:
        """The URL to redirect the user to for Kite login."""
        return self._http.login_url()

    async def complete_login(self, request_token: str) -> BrokerSession:
        """Exchange a ``request_token`` for an access token and store it encrypted."""
        if not request_token:
            raise ValueError("request_token is required")
        data = self._http.generate_session(request_token, self._api_secret)
        access_token = data.get("access_token")
        if not access_token:
            raise ValueError("Kite did not return an access_token")
        self._http.set_access_token(access_token)
        session = BrokerSession(
            broker=self.BROKER,
            access_token=access_token,
            public_token=data.get("public_token"),
            kite_user_id=data.get("user_id"),
            expires_at=kite_token_expiry(),
        )
        await self._store.save(session)
        logger.info("zerodha_login_complete", kite_user=session.kite_user_id)
        return session

    async def current_session(self) -> BrokerSession | None:
        """Load the stored session if present and still valid; else None."""
        session = await self._store.load(self.BROKER)
        if session is None or not session.is_valid:
            return None
        return session

    async def logout(self) -> None:
        await self._store.clear(self.BROKER)
