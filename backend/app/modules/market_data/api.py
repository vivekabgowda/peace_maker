"""Market-data REST endpoints (read-only; live pushes go over WebSocket)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.modules.market_data.providers import available_providers
from app.modules.market_data.service import MarketDataService

router = APIRouter(prefix="/market", tags=["market-data"])


@router.get("/providers", summary="List available market-data providers")
async def providers(_user: CurrentUser) -> dict[str, list[str]]:
    return {"providers": available_providers()}


@router.get("/status", summary="Current market session status")
async def status(_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    svc = MarketDataService(session)
    return {
        "status": await svc.get_market_status(),
        "freshness_seconds": await svc.get_data_freshness(),
    }


@router.get("/instruments", summary="List instruments")
async def instruments(
    _user: CurrentUser,
    session: DbSession,
    fno: Annotated[bool, Query()] = False,
) -> dict[str, list[dict[str, Any]]]:
    svc = MarketDataService(session)
    return {"data": await svc.list_instruments(fno_only=fno)}


@router.get("/indices", summary="Index quotes (Nifty, Bank Nifty, Sensex, VIX)")
async def indices(_user: CurrentUser, session: DbSession) -> dict[str, list[dict[str, Any]]]:
    return {"data": await MarketDataService(session).get_indices()}


@router.get("/quotes", summary="All live quotes")
async def quotes(_user: CurrentUser, session: DbSession) -> dict[str, list[dict[str, Any]]]:
    return {"data": await MarketDataService(session).get_all_quotes()}


@router.get("/quote/{symbol}", summary="Latest quote for a symbol")
async def quote(symbol: str, _user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return {"data": await MarketDataService(session).get_quote(symbol)}


@router.get("/candles/{symbol}", summary="Historical candles for a symbol/timeframe")
async def candles(
    symbol: str,
    _user: CurrentUser,
    session: DbSession,
    tf: Annotated[str, Query()] = "5m",
    limit: Annotated[int, Query(ge=1, le=1000)] = 300,
) -> dict[str, Any]:
    return {"data": await MarketDataService(session).get_candles(symbol, tf, limit)}


@router.get("/indicators/{symbol}", summary="Latest indicator bundle")
async def indicators(
    symbol: str,
    _user: CurrentUser,
    session: DbSession,
    tf: Annotated[str, Query()] = "5m",
) -> dict[str, Any]:
    return {"data": await MarketDataService(session).get_indicators(symbol, tf)}


@router.get("/breadth", summary="Market breadth (advances/declines)")
async def breadth(_user: CurrentUser, session: DbSession) -> dict[str, Any]:
    svc = MarketDataService(session)
    return {"breadth": await svc.get_breadth(), "sectors": await svc.get_sector_strength()}


@router.get("/option-chain/{underlying}", summary="Option-chain summary")
async def option_chain(underlying: str, _user: CurrentUser, session: DbSession) -> dict[str, Any]:
    return {"data": await MarketDataService(session).get_option_summary(underlying)}
