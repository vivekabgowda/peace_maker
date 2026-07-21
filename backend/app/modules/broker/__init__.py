"""Broker integration subsystem (Sprint 6 — Zerodha Kite Connect).

Live market data + OAuth auth + historical ingestion only. There is deliberately
**no order-placement path** anywhere in this module. The Kite SDK is optional and
imported lazily; the whole subsystem is testable via fake ports.
"""

from __future__ import annotations

from app.modules.broker.auth import ZerodhaAuth
from app.modules.broker.factory import build_zerodha_provider, register_broker_providers
from app.modules.broker.historical import BackfillResult, HistoricalDataService
from app.modules.broker.provider import ZerodhaProvider
from app.modules.broker.reconnect import BackoffPolicy, ReconnectState
from app.modules.broker.token_store import (
    BrokerSession,
    Cipher,
    DbTokenStore,
    MemoryTokenStore,
    kite_token_expiry,
)

__all__ = [
    "BackfillResult",
    "BackoffPolicy",
    "BrokerSession",
    "Cipher",
    "DbTokenStore",
    "HistoricalDataService",
    "MemoryTokenStore",
    "ReconnectState",
    "ZerodhaAuth",
    "ZerodhaProvider",
    "build_zerodha_provider",
    "kite_token_expiry",
    "register_broker_providers",
]
