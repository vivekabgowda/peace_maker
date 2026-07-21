"""Broker service — orchestrates the Kite login flow, token status, and backfill.

Depends only on the SDK-agnostic ports, so it is fully testable with fakes. The
HTTP port and market provider are injected (the API supplies real ones and tests
override them), keeping the Kite SDK out of the import path in CI.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.modules.broker import metrics
from app.modules.broker.auth import ZerodhaAuth
from app.modules.broker.historical import HistoricalDataService
from app.modules.broker.ports import KiteHttpPort
from app.modules.broker.token_store import Cipher, DbTokenStore
from app.modules.market_data.providers.base import MarketProvider
from app.modules.market_data.repository import MarketDataRepository

logger = get_logger("broker.service")

# Process-stable dev key so encryption works without configuration in dev/test.
# Production MUST set BKN_BROKER_ENC_KEY (a persisted key) or tokens become
# unreadable across restarts.
_DEV_KEY: str = Fernet.generate_key().decode()


def _enc_key(settings: Settings) -> str:
    if settings.broker_enc_key:
        return settings.broker_enc_key
    logger.warning("broker_enc_key_unset_using_ephemeral_dev_key")
    return _DEV_KEY


class BrokerService:
    def __init__(self, db: AsyncSession, http: KiteHttpPort) -> None:
        self._settings = get_settings()
        self._db = db
        self._cipher = Cipher(_enc_key(self._settings))
        self._store = DbTokenStore(db, self._cipher)
        self._auth = ZerodhaAuth(http, self._settings.zerodha_api_secret, self._store)
        self._repo = MarketDataRepository(db)

    # -- Auth ---------------------------------------------------------------
    def login_url(self) -> str:
        return self._auth.login_url()

    async def complete_login(self, request_token: str) -> dict[str, Any]:
        session = await self._auth.complete_login(request_token)
        await self._db.commit()
        metrics.BROKER_TOKEN_VALID.labels(broker="zerodha").set(1)
        return {
            "broker": session.broker,
            "kite_user_id": session.kite_user_id,
            "expires_at": session.expires_at.isoformat(),
            "valid": session.is_valid,
        }

    async def status(self) -> dict[str, Any]:
        session = await self._auth.current_session()
        valid = bool(session and session.is_valid)
        metrics.BROKER_TOKEN_VALID.labels(broker="zerodha").set(1 if valid else 0)
        return {
            "provider": self._settings.market_provider,
            "broker": "zerodha",
            "token_present": session is not None,
            "token_valid": valid,
            "kite_user_id": session.kite_user_id if session else None,
            "expires_at": session.expires_at.isoformat() if session else None,
        }

    async def logout(self) -> None:
        await self._auth.logout()
        await self._db.commit()

    # -- Historical ---------------------------------------------------------
    async def backfill(
        self,
        provider: MarketProvider,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> dict[str, Any]:
        result = await HistoricalDataService(provider, self._repo).backfill(
            symbol, timeframe, start, end
        )
        await self._db.commit()
        return {
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "candles": result.candles,
            "chunks": result.chunks,
        }
