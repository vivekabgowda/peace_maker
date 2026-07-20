"""Instrument master service.

Loads and refreshes the instrument universe (NSE/BSE/F&O/indices/options/futures,
with lot sizes, tick sizes, sectors, ISIN, expiries) from the active provider.
Idempotent — safe to run on startup and on a schedule.
"""

from __future__ import annotations

from app.core.logging import get_logger
from app.modules.market_data.providers.base import MarketProvider
from app.modules.market_data.repository import MarketDataRepository

logger = get_logger("instrument_master")


class InstrumentMasterService:
    def __init__(self, repository: MarketDataRepository, provider: MarketProvider) -> None:
        self._repo = repository
        self._provider = provider

    async def sync(self) -> int:
        """Fetch instruments from the provider and upsert them. Returns #new rows."""
        instruments = await self._provider.fetch_instruments()
        created = await self._repo.upsert_instruments(instruments)
        logger.info(
            "instrument_master_synced",
            provider=self._provider.name,
            total=len(instruments),
            created=created,
        )
        return created
