"""Live market feed runner — the orchestrator of the real-time pipeline.

Wires the active provider's quote stream through: hot cache → candle builder →
persistence → event bus (QuoteUpdated, CandleClosed → IndicatorCalculated). A
separate task polls option chains. Runs as a background task, started on app
startup only when ``BKN_MARKET_FEED_ENABLED`` is true.

Provider-agnostic: it depends only on :class:`MarketProvider`.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from decimal import Decimal

from app.core.config import get_settings
from app.core.database import async_session_factory
from app.core.logging import get_logger
from app.modules.market_data import cache, metrics
from app.modules.market_data.candle_builder import CandleBuilder, WorkingCandle
from app.modules.market_data.indicator_engine import IndicatorEngine
from app.modules.market_data.instrument_master import InstrumentMasterService
from app.modules.market_data.option_chain_engine import OptionChainEngine
from app.modules.market_data.providers import MarketProvider, create_provider
from app.modules.market_data.repository import MarketDataRepository
from app.shared.events import CandleClosed, QuoteUpdated, event_bus

logger = get_logger("market_runner")


class MarketFeedRunner:
    def __init__(self, provider: MarketProvider | None = None) -> None:
        self._settings = get_settings()
        self._provider = provider or create_provider(self._settings.market_provider)
        self._symbol_ids: dict[str, int] = {}
        self._last_volume: dict[str, int] = {}
        self._closed: list[tuple[str, str, WorkingCandle]] = []
        self._builder = CandleBuilder(self._collect_close, self._settings.market_timeframes)
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    async def start(self) -> None:
        self._running = True
        await self._provider.connect()

        async with async_session_factory() as session:
            repo = MarketDataRepository(session)
            await InstrumentMasterService(repo, self._provider).sync()
            await session.commit()
            self._symbol_ids = await repo.symbol_id_map()

        # Indicator engine reacts to every candle close via the bus.
        event_bus.subscribe(CandleClosed, self._on_candle_closed)

        symbols = list(self._symbol_ids)
        await self._provider.subscribe(symbols)
        await cache.set_market_status("open")

        self._tasks = [
            asyncio.create_task(self._quote_loop()),
            asyncio.create_task(self._option_loop()),
        ]
        logger.info("market_feed_started", provider=self._provider.name, symbols=len(symbols))

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        with contextlib.suppress(Exception):
            await self._provider.disconnect()
        await cache.set_market_status("closed")

    async def _quote_loop(self) -> None:
        async for quote in self._provider.stream():
            if not self._running:
                break
            metrics.QUOTES_INGESTED.inc()
            await self._handle_quote(quote)

    async def _handle_quote(self, quote: object) -> None:
        # ``quote`` is a market_data.domain.models.Quote
        symbol = quote.symbol  # type: ignore[attr-defined]
        instrument_id = self._symbol_ids.get(symbol)
        if instrument_id is None:
            return
        price = float(quote.ltp)  # type: ignore[attr-defined]
        cum_vol = int(quote.volume)  # type: ignore[attr-defined]
        incr = max(0, cum_vol - self._last_volume.get(symbol, cum_vol))
        self._last_volume[symbol] = cum_vol

        await cache.set_quote(symbol, quote.model_dump(mode="json"))  # type: ignore[attr-defined]
        await event_bus.publish(
            QuoteUpdated(
                source="market_runner",
                instrument_id=instrument_id,
                symbol=symbol,
                ltp=Decimal(str(price)),
                volume=cum_vol,
                payload={"vwap": str(quote.vwap), "bid": str(quote.bid), "ask": str(quote.ask)},  # type: ignore[attr-defined]
            )
        )
        self._builder.add_quote(symbol, price, incr, quote.ts)  # type: ignore[attr-defined]
        await self._drain_closed()

    def _collect_close(self, symbol: str, timeframe: str, candle: WorkingCandle) -> None:
        self._closed.append((symbol, timeframe, candle))

    async def _drain_closed(self) -> None:
        if not self._closed:
            return
        pending = self._closed
        self._closed = []
        async with async_session_factory() as session:
            repo = MarketDataRepository(session)
            for symbol, timeframe, candle in pending:
                instrument_id = self._symbol_ids.get(symbol)
                if instrument_id is None:
                    continue
                await repo.upsert_candle(
                    instrument_id,
                    timeframe,
                    candle.bar_ts,
                    Decimal(str(candle.open)),
                    Decimal(str(candle.high)),
                    Decimal(str(candle.low)),
                    Decimal(str(candle.close)),
                    candle.volume,
                )
                metrics.CANDLES_BUILT.labels(timeframe=timeframe).inc()
            await session.commit()

        for symbol, timeframe, candle in pending:
            instrument_id = self._symbol_ids.get(symbol)
            if instrument_id is None:
                continue
            await event_bus.publish(
                CandleClosed(
                    source="candle_builder",
                    instrument_id=instrument_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    open=Decimal(str(candle.open)),
                    high=Decimal(str(candle.high)),
                    low=Decimal(str(candle.low)),
                    close=Decimal(str(candle.close)),
                    volume=candle.volume,
                    bar_ts=candle.bar_ts,
                )
            )

    async def _on_candle_closed(self, event: CandleClosed) -> None:
        async with async_session_factory() as session:
            engine = IndicatorEngine(MarketDataRepository(session))
            await engine.on_candle_closed(event)
            await session.commit()

    async def _option_loop(self) -> None:
        interval = self._settings.option_chain_poll_seconds
        underlyings = self._settings.option_chain_underlyings
        expiry = _nearest_expiry()
        while self._running:
            for underlying in underlyings:
                try:
                    snapshot = await self._provider.fetch_option_chain(underlying, expiry)
                    async with async_session_factory() as session:
                        engine = OptionChainEngine(MarketDataRepository(session))
                        await engine.process(snapshot)
                        await session.commit()
                    metrics.OPTION_CHAINS_UPDATED.inc()
                except Exception:
                    logger.exception("option_loop_error", underlying=underlying)
            await asyncio.sleep(interval)


def _nearest_expiry() -> str:
    """Next weekly Thursday expiry (NSE convention), as ISO date."""
    from datetime import UTC, timedelta

    today = datetime.now(UTC).date()
    days_ahead = (3 - today.weekday()) % 7  # Thursday == 3
    return (today + timedelta(days=days_ahead)).isoformat()
