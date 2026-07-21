"""Paper-trading runner — drives position management from the live tick stream.

Runs inside the **feed process** (the single-instance ingestion pipeline). It
subscribes to :class:`QuoteUpdated` and, for any symbol that currently has an open
paper position, marks the position and closes it if its stop or target has been
hit. Cross-process opens (a position submitted via the API in another process) are
picked up by periodically refreshing the active-symbol set, so a per-tick DB query
is avoided on the hot path.
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.modules.paper_trading.repository import PaperTradingRepository
from app.modules.paper_trading.service import PaperTradingService
from app.shared.events import QuoteUpdated, event_bus
from app.shared.events.bus import EventBus

logger = get_logger("paper_trading.runner")


class PaperTradingRunner:
    def __init__(self, session_factory: object, *, refresh_seconds: float = 10.0) -> None:
        # session_factory is an async_sessionmaker; typed loosely to avoid a hard
        # import cycle with app.core.database at module load.
        self._session_factory = session_factory
        self._refresh_seconds = refresh_seconds
        self._active: set[str] = set()

    def attach(self, bus: EventBus | None = None) -> None:
        """Subscribe the tick handler to the bus (call once, in feed.start())."""
        (bus or event_bus).subscribe(QuoteUpdated, self._on_quote, name="paper_trading")

    async def refresh_active_symbols(self) -> None:
        """Refresh the set of symbols with open positions (the loop body)."""
        async with self._session_factory() as session:  # type: ignore[operator]
            symbols = await PaperTradingRepository(session).open_symbols()
        self._active = set(symbols)

    async def run_refresh_loop(self) -> None:
        """Supervised loop: keep the active-symbol set fresh."""
        while True:
            await self.refresh_active_symbols()
            await asyncio.sleep(self._refresh_seconds)

    async def _on_quote(self, event: object) -> None:
        assert isinstance(event, QuoteUpdated)
        if event.symbol not in self._active:
            return
        price = float(event.ltp)
        async with self._session_factory() as session:  # type: ignore[operator]
            closed = await PaperTradingService(session).apply_price(event.symbol, price, event.ts)
            if closed:
                await session.commit()
                # A close changes the open-symbol set; drop the symbol eagerly if it
                # has no more open positions so we stop marking it until the next
                # refresh.
                remaining = await PaperTradingRepository(session).open_position_rows_by_symbol(
                    event.symbol
                )
                if not remaining:
                    self._active.discard(event.symbol)
                for c in closed:
                    logger.info("paper_tick_close", **{k: c[k] for k in ("symbol", "exit_reason")})
