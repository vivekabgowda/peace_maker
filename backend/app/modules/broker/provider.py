"""Zerodha Kite Connect market-data provider (Sprint 6).

Implements the platform's :class:`MarketProvider` port over the Kite REST + ticker
Protocols. It streams **live market data only** — there is deliberately **no order
path** anywhere in this class or module. Live orders are out of scope for this
sprint by design; the provider interface has no order method to call.

Responsibilities: connect the ticker with a stored access token, subscribe by
instrument token, normalize ticks/instruments/candles into domain models, push
quotes onto a thread-safe queue for ``stream()``, and reconnect with exponential
backoff on drops.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from datetime import datetime
from typing import Any

from app.core.logging import get_logger
from app.modules.broker import metrics
from app.modules.broker.mappers import (
    instrument_to_dto,
    kite_candle_to_domain,
    tick_to_quote,
    timeframe_to_interval,
)
from app.modules.broker.ports import KiteHttpPort, KiteTickerPort
from app.modules.broker.reconnect import BackoffPolicy, ReconnectState
from app.modules.market_data.domain.models import (
    Candle,
    InstrumentDTO,
    OptionChainSnapshot,
    Quote,
)
from app.modules.market_data.providers.base import MarketProvider, ProviderError

logger = get_logger("provider.zerodha")

# Builds a fresh ticker given (api_key, access_token) — the token is known only
# after the daily login flow, so the ticker is built lazily at connect time.
TickerBuilder = Callable[[str, str], KiteTickerPort]


class ZerodhaProvider(MarketProvider):
    name = "zerodha"

    def __init__(
        self,
        http: KiteHttpPort,
        ticker_builder: TickerBuilder,
        *,
        api_key: str = "",
        access_token: str | None = None,
        nifty500: set[str] | None = None,
        fno: set[str] | None = None,
        backoff: BackoffPolicy | None = None,
        queue_maxsize: int = 10_000,
    ) -> None:
        self._http = http
        self._ticker_builder = ticker_builder
        self._api_key = api_key
        self._access_token = access_token
        self._nifty500 = nifty500 or set()
        self._fno = fno or set()
        self._backoff = backoff or BackoffPolicy()
        self._ticker: KiteTickerPort | None = None
        self._queue: asyncio.Queue[Quote] = asyncio.Queue(maxsize=queue_maxsize)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._state = ReconnectState()
        self._token_by_symbol: dict[str, int] = {}
        self._symbol_by_token: dict[int, str] = {}
        self._instruments: list[InstrumentDTO] = []
        self._stopping = False

    # -- Auth ---------------------------------------------------------------
    def set_access_token(self, token: str) -> None:
        """Attach the daily access token (from the login flow) before connecting."""
        self._access_token = token
        self._http.set_access_token(token)
        metrics.BROKER_TOKEN_VALID.labels(broker=self.name).set(1)

    # -- Lifecycle ----------------------------------------------------------
    async def connect(self) -> None:
        if self._access_token is None:
            raise ProviderError(
                "Zerodha access token not set — complete the Kite login flow first "
                "(GET /api/v1/broker/zerodha/login-url → callback)."
            )
        self._stopping = False
        self._loop = asyncio.get_running_loop()
        self._http.set_access_token(self._access_token)
        if not self._instruments:
            await self.fetch_instruments()
        self._open_ticker()

    def _open_ticker(self) -> None:
        if self._access_token is None:
            raise ProviderError("Cannot open ticker without an access token.")
        ticker = self._ticker_builder(self._api_key, self._access_token)
        ticker.on_ticks = self._on_ticks
        ticker.on_connect = self._on_connect
        ticker.on_close = self._on_close
        ticker.on_error = self._on_error
        self._ticker = ticker
        ticker.connect(threaded=True)

    async def disconnect(self) -> None:
        self._stopping = True
        if self._ticker is not None:
            try:
                self._ticker.close()
            except Exception:
                logger.warning("zerodha_close_failed")
        self._state.connected = False
        metrics.BROKER_CONNECTED.labels(broker=self.name).set(0)

    @property
    def is_connected(self) -> bool:
        return self._state.connected

    # -- Instrument master --------------------------------------------------
    async def fetch_instruments(self) -> list[InstrumentDTO]:
        rows = await asyncio.to_thread(self._http.instruments)
        dtos = [instrument_to_dto(r, nifty500=self._nifty500, fno=self._fno) for r in rows]
        self._instruments = dtos
        self._token_by_symbol = {d.symbol: int(d.provider_token) for d in dtos if d.provider_token}
        self._symbol_by_token = {v: k for k, v in self._token_by_symbol.items()}
        logger.info("zerodha_instruments", count=len(dtos))
        return dtos

    # -- Subscriptions ------------------------------------------------------
    async def subscribe(self, symbols: list[str]) -> None:
        tokens = [self._token_by_symbol[s] for s in symbols if s in self._token_by_symbol]
        if not tokens or self._ticker is None:
            return
        self._ticker.subscribe(tokens)
        self._ticker.set_mode("full", tokens)
        metrics.BROKER_SUBSCRIPTIONS.labels(broker=self.name).set(len(tokens))

    async def unsubscribe(self, symbols: list[str]) -> None:
        tokens = [self._token_by_symbol[s] for s in symbols if s in self._token_by_symbol]
        if tokens and self._ticker is not None:
            self._ticker.unsubscribe(tokens)

    async def stream(self) -> AsyncIterator[Quote]:
        while True:
            yield await self._queue.get()

    # -- Option chain -------------------------------------------------------
    async def fetch_option_chain(self, underlying: str, expiry: str) -> OptionChainSnapshot:
        # Kite has no single option-chain endpoint; it is assembled from instrument
        # tokens + quotes. Assembly is deferred to a later sprint; kept explicit.
        raise ProviderError(
            "Zerodha option-chain assembly is not implemented in Sprint 6 "
            "(market data + historical only)."
        )

    # -- Historical ---------------------------------------------------------
    async def fetch_historical_candles(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> list[Candle]:
        token = self._token_by_symbol.get(symbol)
        if token is None:
            if not self._instruments:
                await self.fetch_instruments()
            token = self._token_by_symbol.get(symbol)
        if token is None:
            raise ProviderError(f"Unknown instrument token for {symbol!r}")
        interval = timeframe_to_interval(timeframe)
        rows = await asyncio.to_thread(self._http.historical_data, token, start, end, interval)
        return [kite_candle_to_domain(r, symbol, timeframe) for r in rows]

    async def health_check(self) -> bool:
        """Ticker connected AND a valid token (profile call succeeds)."""
        if not self._state.connected or self._access_token is None:
            return False
        try:
            await asyncio.to_thread(self._http.profile)
            return True
        except Exception:
            return False

    # -- Ticker callbacks (run on the SDK thread) ---------------------------
    def _on_ticks(self, ticks: list[dict[str, Any]]) -> None:
        if self._loop is None:
            return
        for tick in ticks:
            token = tick.get("instrument_token")
            symbol = self._symbol_by_token.get(int(token)) if token is not None else None
            if symbol is None:
                continue
            quote = tick_to_quote(tick, symbol)
            metrics.BROKER_TICKS.labels(broker=self.name).inc()
            self._loop.call_soon_threadsafe(self._enqueue, quote)

    def _enqueue(self, quote: Quote) -> None:
        try:
            self._queue.put_nowait(quote)
        except asyncio.QueueFull:  # drop-oldest under backpressure
            with contextlib.suppress(asyncio.QueueEmpty, asyncio.QueueFull):
                self._queue.get_nowait()
                self._queue.put_nowait(quote)

    def _on_connect(self, *_: object) -> None:
        self._state.on_connect()
        metrics.BROKER_CONNECTED.labels(broker=self.name).set(1)
        metrics.BROKER_RECONNECTS.labels(broker=self.name).inc()
        if self._ticker is not None and self._token_by_symbol:
            self._ticker.set_mode("full", list(self._symbol_by_token))
        logger.info("zerodha_connected", reconnects=self._state.total_reconnects)

    def _on_close(self, *_: object) -> None:
        self._state.on_disconnect()
        metrics.BROKER_CONNECTED.labels(broker=self.name).set(0)
        if self._stopping or self._loop is None:
            return
        delay = self._backoff.delay_for(self._state.attempts)
        logger.warning("zerodha_disconnected", attempt=self._state.attempts, delay=round(delay, 2))
        self._loop.call_soon_threadsafe(lambda: asyncio.ensure_future(self._reconnect(delay)))

    def _on_error(self, *args: object) -> None:
        logger.warning("zerodha_error", detail=str(args[-1]) if args else "unknown")

    async def _reconnect(self, delay: float) -> None:
        await asyncio.sleep(delay)
        if self._stopping:
            return
        try:
            self._open_ticker()
        except Exception:
            logger.warning("zerodha_reconnect_failed", attempt=self._state.attempts)
