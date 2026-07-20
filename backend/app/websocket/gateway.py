"""Dashboard WebSocket gateway.

Browsers open one authenticated multiplexed socket and subscribe to channels
(``indices``, ``quotes:{symbol}``, ``option_chain:{underlying}``, ``news`` …).
A single set of event-bus subscribers fans market events out to the connected
clients. For a single app process the in-process bus suffices; a multi-worker
deployment bridges via Redis pub/sub (documented in the architecture).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.security import TokenError, decode_token
from app.modules.market_data import metrics
from app.shared.events import (
    IndicatorCalculated,
    NewsReceived,
    OptionChainUpdated,
    QuoteUpdated,
    event_bus,
)
from app.websocket import channels

logger = get_logger("ws_gateway")
router = APIRouter()


class Connection:
    def __init__(self, ws: WebSocket) -> None:
        self.ws = ws
        self.channels: set[str] = set()
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)


class ConnectionManager:
    """Tracks connections and their channel subscriptions."""

    def __init__(self) -> None:
        self._connections: set[Connection] = set()

    async def connect(self, ws: WebSocket) -> Connection:
        await ws.accept()
        conn = Connection(ws)
        self._connections.add(conn)
        metrics.WS_CONNECTED_CLIENTS.set(len(self._connections))
        return conn

    def disconnect(self, conn: Connection) -> None:
        self._connections.discard(conn)
        metrics.WS_CONNECTED_CLIENTS.set(len(self._connections))

    async def broadcast(self, channel: str, event: str, data: Any) -> None:
        message = {
            "channel": channel,
            "event": event,
            "data": data,
            "ts": datetime.now(UTC).isoformat(),
        }
        for conn in list(self._connections):
            if channel not in conn.channels:
                continue
            try:
                conn.queue.put_nowait(message)
            except asyncio.QueueFull:
                metrics.WS_MESSAGES_DROPPED.inc()  # backpressure: drop for slow client

    @property
    def client_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


# -- Event-bus → WebSocket bridge (registered once at startup) --------------
async def _on_quote(event: QuoteUpdated) -> None:
    data = {"symbol": event.symbol, "ltp": str(event.ltp), "volume": event.volume, **event.payload}
    await manager.broadcast(channels.quote_channel(event.symbol), "quote", data)
    await manager.broadcast(channels.QUOTES_ALL, "quote", data)
    if event.symbol in channels.INDEX_SYMBOLS:
        await manager.broadcast(channels.INDICES, "quote", data)


async def _on_indicator(event: IndicatorCalculated) -> None:
    await manager.broadcast(
        channels.indicator_channel(event.symbol),
        "indicators",
        {"symbol": event.symbol, "timeframe": event.timeframe, "indicators": event.indicators},
    )


async def _on_option_chain(event: OptionChainUpdated) -> None:
    await manager.broadcast(
        channels.option_chain_channel(event.underlying),
        "option_chain",
        {"underlying": event.underlying, "pcr": event.pcr, "max_pain": event.max_pain},
    )


async def _on_news(event: NewsReceived) -> None:
    await manager.broadcast(
        channels.NEWS,
        "news",
        {
            "headline": event.headline,
            "sentiment": event.sentiment,
            "impact": event.impact,
            "symbols": event.symbols,
        },
    )


def register_ws_bridge() -> None:
    """Subscribe the gateway to the event bus. Idempotent-safe at startup."""
    event_bus.subscribe(QuoteUpdated, _on_quote)
    event_bus.subscribe(IndicatorCalculated, _on_indicator)
    event_bus.subscribe(OptionChainUpdated, _on_option_chain)
    event_bus.subscribe(NewsReceived, _on_news)


@router.websocket("/ws")
async def market_ws(ws: WebSocket) -> None:
    token = ws.query_params.get("token")
    try:
        if not token:
            raise TokenError("missing token")
        decode_token(token, expected_type="access")
    except TokenError:
        await ws.close(code=4401)
        return

    conn = await manager.connect(ws)
    sender = asyncio.create_task(_sender_loop(conn))
    try:
        while True:
            message = await ws.receive_json()
            action = message.get("action")
            chans = message.get("channels", [])
            if action == "subscribe":
                conn.channels.update(chans)
            elif action == "unsubscribe":
                conn.channels.difference_update(chans)
            elif action == "ping":
                await ws.send_json({"channel": "system", "event": "pong", "data": None})
    except WebSocketDisconnect:
        pass
    finally:
        sender.cancel()
        manager.disconnect(conn)


async def _sender_loop(conn: Connection) -> None:
    while True:
        message = await conn.queue.get()
        await conn.ws.send_json(message)
