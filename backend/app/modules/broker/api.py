"""Broker REST endpoints (Sprint 6).

Auth + market-data + historical only. There is **no order endpoint** — live order
placement is out of scope by design.

The Kite HTTP port and market provider are resolved via FastAPI dependencies so
tests can override them with fakes (keeping the Kite SDK out of CI).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.core.dependencies import CurrentUser, DbSession
from app.modules.broker.factory import register_broker_providers
from app.modules.broker.ports import KiteHttpPort
from app.modules.broker.service import BrokerService
from app.modules.market_data.providers import available_providers, create_provider
from app.modules.market_data.providers.base import MarketProvider, ProviderError

# Make "zerodha" and "paper" discoverable via /providers as soon as the API loads.
# These are factory references — the Kite SDK is still only imported when a zerodha
# provider is actually instantiated.
register_broker_providers()

router = APIRouter(prefix="/broker", tags=["broker"])


def get_kite_http() -> KiteHttpPort:
    """Build the real Kite HTTP adapter (overridden in tests). Lazily imports SDK."""
    from app.modules.broker.kite import build_kite_http

    return build_kite_http(get_settings().zerodha_api_key)


def get_market_provider() -> MarketProvider:
    """Resolve the configured market provider (overridden in tests)."""
    return create_provider(get_settings().market_provider)


KiteHttp = Annotated[KiteHttpPort, Depends(get_kite_http)]
Provider = Annotated[MarketProvider, Depends(get_market_provider)]


@router.get("/providers", summary="Available market/broker providers")
async def providers(_user: CurrentUser) -> dict[str, list[str]]:
    return {"providers": available_providers()}


@router.get("/status", summary="Broker connection & token status")
async def broker_status(_user: CurrentUser, session: DbSession, http: KiteHttp) -> dict[str, Any]:
    return await BrokerService(session, http).status()


@router.get("/zerodha/login-url", summary="Zerodha Kite login URL")
async def login_url(_user: CurrentUser, session: DbSession, http: KiteHttp) -> dict[str, str]:
    return {"login_url": BrokerService(session, http).login_url()}


@router.get("/zerodha/callback", summary="Zerodha OAuth callback (request_token → access_token)")
async def zerodha_callback(
    _user: CurrentUser,
    session: DbSession,
    http: KiteHttp,
    request_token: Annotated[str, Query()],
) -> dict[str, Any]:
    try:
        return await BrokerService(session, http).complete_login(request_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/logout", summary="Clear the stored broker token")
async def logout(_user: CurrentUser, session: DbSession, http: KiteHttp) -> dict[str, bool]:
    await BrokerService(session, http).logout()
    return {"ok": True}


@router.post("/historical/backfill", summary="Download & store historical candles")
async def backfill(
    _user: CurrentUser,
    session: DbSession,
    http: KiteHttp,
    provider: Provider,
    symbol: Annotated[str, Query()],
    timeframe: Annotated[str, Query()],
    start: Annotated[datetime, Query()],
    end: Annotated[datetime, Query()],
) -> dict[str, Any]:
    try:
        return await BrokerService(session, http).backfill(provider, symbol, timeframe, start, end)
    except (ValueError, ProviderError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
