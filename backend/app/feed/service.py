"""Market Feed Service — the dedicated, supervised ingestion pipeline.

Runs **only** in the feed process (never in API workers), behind a single-
instance lock. Wires provider → hot cache → candle builder → persistence → event
bus, with:
- **supervised loops** (restart on crash, backoff, circuit breaker, heartbeat),
- **session awareness** (candles only build during a live NSE session),
- an incremental **IndicatorEngine** consuming ``CandleClosed`` off the bus.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

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
from app.modules.paper_trading.runner import PaperTradingRunner
from app.shared.events import CandleClosed, QuoteUpdated, event_bus
from app.shared.market_calendar import SessionPhase, is_market_open, session_phase

if TYPE_CHECKING:
    from app.modules.broker.token_store import BrokerSession
from app.shared.supervision import Backoff, Supervisor

# A single broker WebSocket cannot subscribe to an entire exchange universe — Kite
# caps a connection at ~3000 instruments and rejects oversized frames ("Message too
# big"). A live instrument master spans 100k+ rows, so the live subscription is
# scoped to at most this many symbols (watchlist / Nifty 500 / capped cash equity).
_MAX_WS_SYMBOLS = 3000

logger = get_logger("feed_service")

_PHASE_CODE = {
    SessionPhase.CLOSED: 0,
    SessionPhase.PRE_OPEN: 1,
    SessionPhase.OPEN: 2,
    SessionPhase.CLOSING: 3,
    SessionPhase.MUHURAT: 4,
}


class FeedService:
    def __init__(
        self, provider: MarketProvider | None = None, *, enforce_session: bool = True
    ) -> None:
        self._settings = get_settings()
        self._provider = provider or create_provider(self._settings.market_provider)
        self._provider_injected = provider is not None
        self._enforce_session = enforce_session
        self._symbol_ids: dict[str, int] = {}
        self._sub_symbols: list[str] = []
        self._last_volume: dict[str, int] = {}
        self._closed: list[tuple[str, str, WorkingCandle]] = []
        self._builder = CandleBuilder(self._collect_close, self._settings.market_timeframes)
        self._indicator_engine = IndicatorEngine(async_session_factory)
        self._supervisor = Supervisor()
        self._paper_runner: PaperTradingRunner | None = None
        self._started = False

    # -- Lifecycle ----------------------------------------------------------
    async def start(self) -> None:
        await self._ensure_provider()
        await self._provider.connect()
        metrics.PROVIDER_CONNECTED.set(1)
        async with async_session_factory() as session:
            repo = MarketDataRepository(session)
            await InstrumentMasterService(repo, self._provider).sync()
            await session.commit()
            self._symbol_ids = await repo.symbol_id_map()
            self._sub_symbols = await self._resolve_subscriptions(repo)

        # Indicator engine consumes candle closes off the bus (decoupled).
        event_bus.subscribe(
            CandleClosed, self._indicator_engine.on_candle_closed, name="indicator_engine"
        )
        # Paper-trading position manager consumes live quotes off the same bus
        # (Sprint 7): marks open paper positions and closes them on stop/target.
        if self._settings.paper_trading_enabled:
            self._paper_runner = PaperTradingRunner(async_session_factory)
            self._paper_runner.attach(event_bus)
        # Cross-instance fan-out (R3): mirror WS-facing events to the Redis stream
        # so every API worker can deliver them to its own clients.
        if self._settings.event_stream_enabled:
            from app.shared.events.stream import EventStreamBridge, register_forwarder

            register_forwarder(event_bus, EventStreamBridge())
            logger.info("event_stream_forwarder_registered")
        await self._provider.subscribe(self._sub_symbols)
        await cache.set_market_status("open")

        # Supervised loops — a crash restarts with backoff under a circuit breaker.
        self._supervisor.add(
            "quote_stream", self._run_quote_stream, backoff=Backoff(base=0.5, max_delay=10)
        )
        self._supervisor.add(
            "option_poll", self._run_option_poll, backoff=Backoff(base=1, max_delay=15)
        )
        self._supervisor.add("session_watch", self._run_session_watch, backoff=Backoff(base=1))
        self._supervisor.add(
            "news_poll", self._run_news_poll, backoff=Backoff(base=2, max_delay=30)
        )
        # Sprint 7 loops: keep the paper-position set fresh and generate
        # daily/weekly performance reports automatically.
        if self._paper_runner is not None:
            self._supervisor.add(
                "paper_manager", self._run_paper_manager, backoff=Backoff(base=1, max_delay=15)
            )
        if self._settings.report_scheduler_enabled:
            self._supervisor.add(
                "report_scheduler",
                self._run_report_scheduler,
                backoff=Backoff(base=5, max_delay=60),
            )
        self._supervisor.start_all()
        self._started = True
        logger.info("feed_started", provider=self._provider.name, symbols=len(self._symbol_ids))

    async def _ensure_provider(self) -> None:
        """For a live broker provider, attach the encrypted daily token before
        connecting. If no valid token is available, **fall back to the simulated
        provider** rather than crashing the feed — the platform stays fully
        operational (advisory-only) and the operator is prompted to reconnect via
        the Admin broker panel. An explicitly-injected provider is never swapped.
        """
        if self._settings.market_provider != "zerodha":
            return
        set_token = getattr(self._provider, "set_access_token", None)
        token = await self._load_broker_token() if callable(set_token) else None
        if token is not None and callable(set_token):
            set_token(token.access_token)
            logger.info("zerodha_token_attached", kite_user=token.kite_user_id)
            return
        if self._provider_injected:
            return  # a test/caller injected the provider on purpose; leave it.
        logger.warning(
            "zerodha_token_missing_falling_back_to_simulated",
            reason="no valid daily token — complete the login flow in Admin → Broker",
        )
        self._provider = create_provider("simulated")

    async def _load_broker_token(self) -> BrokerSession | None:
        """Load a valid stored Zerodha session, or None."""
        key = self._settings.broker_enc_key
        if not key:
            logger.warning("broker_enc_key_unset_cannot_attach_token")
            return None
        from app.modules.broker.token_store import Cipher, DbTokenStore

        async with async_session_factory() as session:
            store = DbTokenStore(session, Cipher(key))
            broker_session = await store.load("zerodha")
        if broker_session and broker_session.is_valid:
            return broker_session
        return None

    async def _resolve_subscriptions(self, repo: MarketDataRepository) -> list[str]:
        """Choose the bounded set of symbols to stream from the provider.

        A live broker's instrument master spans the whole exchange (100k+ symbols)
        but a single WebSocket can only carry a few thousand. When the synced
        universe is small (e.g. the simulated provider) we keep subscribing to all
        of it — behaviour is unchanged. When it is large we scope to the configured
        watchlist / Nifty 500 / capped cash equity so the socket stays within Kite's
        per-connection limit and never trips a "Message too big" close.
        """
        if len(self._symbol_ids) <= _MAX_WS_SYMBOLS:
            return list(self._symbol_ids)
        sub_map = await repo.subscription_symbol_ids(
            watchlist=self._settings.broker_watchlist,
            include_fno=self._settings.broker_subscribe_fno,
            limit=_MAX_WS_SYMBOLS,
        )
        symbols = list(sub_map)
        logger.info(
            "subscription_scoped",
            universe=len(self._symbol_ids),
            subscribed=len(symbols),
            watchlist=len(self._settings.broker_watchlist),
        )
        return symbols

    async def stop(self) -> None:
        await self._supervisor.stop_all()
        with contextlib.suppress(Exception):
            await self._provider.disconnect()
        metrics.PROVIDER_CONNECTED.set(0)
        await cache.set_market_status("closed")

    def health(self) -> dict[str, object]:
        return {
            "started": self._started,
            "provider_connected": self._provider.is_connected,
            "supervisor": self._supervisor.health(),
        }

    # -- Supervised loop bodies --------------------------------------------
    async def _run_quote_stream(self) -> None:
        # A restart re-establishes the connection + subscriptions (reconnect).
        if not self._provider.is_connected:
            await self._provider.connect()
            await self._provider.subscribe(self._sub_symbols)
            metrics.PROVIDER_CONNECTED.set(1)
        task = self._supervisor.get("quote_stream")
        async for quote in self._provider.stream():
            task.heartbeat()
            metrics.QUOTES_INGESTED.inc()
            await self._handle_quote(quote)

    async def _run_option_poll(self) -> None:
        task = self._supervisor.get("option_poll")
        interval = self._settings.option_chain_poll_seconds
        expiry = _nearest_expiry()
        while True:
            task.heartbeat()
            for underlying in self._settings.option_chain_underlyings:
                snapshot = await self._provider.fetch_option_chain(underlying, expiry)
                async with async_session_factory() as session:
                    await OptionChainEngine(MarketDataRepository(session)).process(snapshot)
                    await session.commit()
                metrics.OPTION_CHAINS_UPDATED.inc()
            await asyncio.sleep(interval)

    async def _run_session_watch(self) -> None:
        task = self._supervisor.get("session_watch")
        while True:
            task.heartbeat()
            phase = session_phase(datetime.now(UTC))
            metrics.MARKET_SESSION_PHASE.set(_PHASE_CODE[phase])
            await cache.set_market_status(phase.value)
            stale = self._supervisor.watchdog()
            if stale:
                logger.warning("watchdog_stale_tasks", tasks=stale)
            await asyncio.sleep(5.0)

    async def _run_news_poll(self) -> None:
        from app.modules.news.providers import create_news_provider
        from app.modules.news.service import NewsService

        task = self._supervisor.get("news_poll")
        provider = create_news_provider(self._settings.news_provider)
        while True:
            task.heartbeat()
            async with async_session_factory() as session:
                await NewsService(session).ingest(provider)
                await session.commit()
            await asyncio.sleep(self._settings.news_poll_seconds)

    async def _run_paper_manager(self) -> None:
        # Refresh which symbols have open paper positions; the actual stop/target
        # marking happens on the bus quote handler (runner.attach).
        assert self._paper_runner is not None
        task = self._supervisor.get("paper_manager")
        while True:
            task.heartbeat()
            await self._paper_runner.refresh_active_symbols()
            await asyncio.sleep(10.0)

    async def _run_report_scheduler(self) -> None:
        from app.workers.reports import ReportScheduler

        task = self._supervisor.get("report_scheduler")
        scheduler = ReportScheduler(async_session_factory)
        while True:
            task.heartbeat()
            generated = await scheduler.tick()
            if generated:
                logger.info("reports_generated", kinds=generated)
            await asyncio.sleep(self._settings.report_scheduler_interval_seconds)

    # -- Processing ---------------------------------------------------------
    async def _handle_quote(self, quote: object) -> None:
        started = asyncio.get_event_loop().time()
        symbol = quote.symbol  # type: ignore[attr-defined]
        instrument_id = self._symbol_ids.get(symbol)
        if instrument_id is None:
            return
        price = float(quote.ltp)  # type: ignore[attr-defined]
        cum_vol = int(quote.volume)  # type: ignore[attr-defined]
        incr = max(0, cum_vol - self._last_volume.get(symbol, cum_vol))
        self._last_volume[symbol] = cum_vol
        ts = quote.ts  # type: ignore[attr-defined]

        await cache.set_quote(symbol, quote.model_dump(mode="json"))  # type: ignore[attr-defined]
        event_bus.publish(
            QuoteUpdated(
                source="feed",
                instrument_id=instrument_id,
                symbol=symbol,
                ltp=Decimal(str(price)),
                volume=cum_vol,
                payload={"vwap": str(quote.vwap), "bid": str(quote.bid), "ask": str(quote.ask)},  # type: ignore[attr-defined]
            )
        )
        # Session-aware: only build candles during a live session (no off-hours bars).
        if not self._enforce_session or is_market_open(ts):
            self._builder.add_quote(symbol, price, incr, ts)
            await self._drain_closed()
        metrics.QUOTE_LATENCY.observe(asyncio.get_event_loop().time() - started)

    def _collect_close(self, symbol: str, timeframe: str, candle: WorkingCandle) -> None:
        self._closed.append((symbol, timeframe, candle))

    async def _drain_closed(self) -> None:
        if not self._closed:
            return
        pending, self._closed = self._closed, []
        async with async_session_factory() as session:
            repo = MarketDataRepository(session)
            for symbol, timeframe, candle in pending:
                iid = self._symbol_ids.get(symbol)
                if iid is None:
                    continue
                await repo.upsert_candle(
                    iid,
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
            iid = self._symbol_ids.get(symbol)
            if iid is None:
                continue
            event_bus.publish(
                CandleClosed(
                    source="feed",
                    instrument_id=iid,
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


def _nearest_expiry() -> str:
    from app.shared.market_calendar import nearest_weekly_expiry

    return nearest_weekly_expiry(datetime.now(UTC).date()).isoformat()
