"""Historical OHLCV ingestion (Sprint 6).

Downloads candles from the broker (chunked to respect Kite's per-request date
limits) and persists them into TimescaleDB via the market-data repository — the
same `candles` hypertable the live pipeline writes to, so backfill and live data
are indistinguishable downstream.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.core.logging import get_logger
from app.modules.market_data.providers.base import MarketProvider, ProviderError
from app.modules.market_data.repository import MarketDataRepository

logger = get_logger("broker.historical")

# Kite per-request span limits (days) by timeframe. Conservative vs. the docs.
_MAX_DAYS: dict[str, int] = {
    "1m": 55,
    "5m": 95,
    "15m": 190,
    "1h": 390,
    "1d": 1900,
}


def _date_chunks(
    start: datetime, end: datetime, max_days: int
) -> Iterator[tuple[datetime, datetime]]:
    cursor = start
    step = timedelta(days=max_days)
    while cursor < end:
        chunk_end = min(cursor + step, end)
        yield cursor, chunk_end
        cursor = chunk_end


@dataclass(frozen=True, slots=True)
class BackfillResult:
    symbol: str
    timeframe: str
    candles: int
    chunks: int


class HistoricalDataService:
    def __init__(self, provider: MarketProvider, repo: MarketDataRepository) -> None:
        self._provider = provider
        self._repo = repo

    async def backfill(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> BackfillResult:
        """Download and persist candles for ``symbol``/``timeframe`` over a range."""
        if timeframe not in _MAX_DAYS:
            raise ValueError(f"Unsupported timeframe: {timeframe!r}")
        instrument_id = await self._repo.get_instrument_id(symbol)
        if instrument_id is None:
            raise ProviderError(
                f"{symbol!r} is not in the instrument master — sync instruments first."
            )
        stored = 0
        chunks = 0
        for chunk_start, chunk_end in _date_chunks(start, end, _MAX_DAYS[timeframe]):
            chunks += 1
            candles = await self._provider.fetch_historical_candles(
                symbol, timeframe, chunk_start, chunk_end
            )
            for c in candles:
                await self._repo.upsert_candle(
                    instrument_id, timeframe, c.ts, c.open, c.high, c.low, c.close, c.volume
                )
                stored += 1
        logger.info(
            "backfill_complete", symbol=symbol, timeframe=timeframe, candles=stored, chunks=chunks
        )
        return BackfillResult(symbol=symbol, timeframe=timeframe, candles=stored, chunks=chunks)
