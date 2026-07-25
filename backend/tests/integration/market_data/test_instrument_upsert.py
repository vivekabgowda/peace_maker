"""Instrument upsert is idempotent and de-duplicates the provider dump.

Regression: a live provider's instrument master lists some identities twice and
is re-synced on every startup, which previously raised a UniqueViolationError on
a populated table (per-row add with autoflush disabled).
"""

from __future__ import annotations

import pytest
from app.core.database import async_session_factory
from app.modules.market_data.domain.models import Exchange, InstrumentDTO, InstrumentType
from app.modules.market_data.repository import MarketDataRepository

pytestmark = pytest.mark.integration


def _eq(symbol: str) -> InstrumentDTO:
    return InstrumentDTO(symbol=symbol, exchange=Exchange.NSE, instrument_type=InstrumentType.EQ)


async def test_upsert_instruments_dedupes_and_is_idempotent() -> None:
    async with async_session_factory() as session:
        repo = MarketDataRepository(session)
        # A same-batch duplicate identity must not raise and is collapsed to one row.
        written = await repo.upsert_instruments([_eq("DUPE"), _eq("DUPE"), _eq("UNIQ")])
        await session.commit()
        assert written == 2
        assert await repo.get_instrument_id("DUPE") is not None
        assert await repo.get_instrument_id("UNIQ") is not None

        # Re-syncing against the now-populated table must also be safe (idempotent).
        again = await repo.upsert_instruments([_eq("DUPE"), _eq("UNIQ")])
        await session.commit()
        assert again == 2
