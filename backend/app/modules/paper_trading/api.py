"""Paper-trading REST endpoints (Sprint 7).

Submit simulated orders, inspect open positions and the paper account, and close
positions manually. Fills price against the **live, read-only** quote cache; there
is no endpoint that reaches a broker's order API.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.core.dependencies import CurrentUser, DbSession
from app.modules.market_data import cache
from app.modules.paper_trading.models import OrderRequest, OrderSide, OrderType
from app.modules.paper_trading.service import PaperTradingService

router = APIRouter(prefix="/paper", tags=["paper-trading"])


class SubmitOrder(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    side: OrderSide
    quantity: int = Field(gt=0)
    order_type: OrderType = OrderType.MARKET
    limit_price: float | None = Field(default=None, gt=0)
    stop: float | None = Field(default=None, gt=0)
    target: float | None = Field(default=None, gt=0)
    strategy_key: str | None = Field(default=None, max_length=64)


async def _live_price(symbol: str) -> float | None:
    quote = await cache.get_quote(symbol)
    if not quote or quote.get("ltp") in (None, ""):
        return None
    try:
        return float(quote["ltp"])
    except (TypeError, ValueError):
        return None


async def _marks(symbols: list[str]) -> dict[str, float]:
    marks: dict[str, float] = {}
    for sym in set(symbols):
        price = await _live_price(sym)
        if price is not None:
            marks[sym] = price
    return marks


@router.get("/account", summary="Paper account snapshot (cash, equity, P&L)")
async def account(user: CurrentUser, session: DbSession) -> dict[str, Any]:
    svc = PaperTradingService(session)
    positions = await svc.list_positions(str(user.id))
    marks = await _marks([str(p["symbol"]) for p in positions])
    return await svc.account_snapshot(str(user.id), marks)


@router.get("/positions", summary="Open paper positions")
async def positions(user: CurrentUser, session: DbSession) -> dict[str, Any]:
    svc = PaperTradingService(session)
    open_positions = await svc.list_positions(str(user.id))
    marks = await _marks([str(p["symbol"]) for p in open_positions])
    priced = await svc.list_positions(str(user.id), prices=marks)
    return {"count": len(priced), "positions": priced}


@router.get("/orders", summary="Paper order history")
async def orders(user: CurrentUser, session: DbSession) -> dict[str, Any]:
    svc = PaperTradingService(session)
    rows = await svc.list_orders(str(user.id))
    return {"count": len(rows), "orders": rows}


@router.post("/orders", summary="Submit a paper order (simulated fill at live price)")
async def submit(user: CurrentUser, session: DbSession, body: SubmitOrder) -> dict[str, Any]:
    ref_price = await _live_price(body.symbol)
    if ref_price is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No live price for {body.symbol}; "
                "is the feed running and the symbol subscribed?"
            ),
        )
    request = OrderRequest(
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
        order_type=body.order_type,
        limit_price=body.limit_price,
        stop=body.stop,
        target=body.target,
        strategy_key=body.strategy_key,
        source="manual",
    )
    result = await PaperTradingService(session).submit_order(str(user.id), request, ref_price)
    await session.commit()
    if result.get("status") == "rejected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.get("reason"))
    return result


@router.post("/positions/{position_id}/close", summary="Close a paper position at the live price")
async def close(user: CurrentUser, session: DbSession, position_id: int) -> dict[str, Any]:
    svc = PaperTradingService(session)
    position = await svc.get_open_position(position_id)
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Open position not found")
    price = await _live_price(position.symbol)
    if price is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=f"No live price for {position.symbol}"
        )
    result = await svc.close_position(position_id, price)
    await session.commit()
    return result or {"status": "not_closed"}
