"""Instrument upsert is idempotent and de-duplicates the provider dump.

Regression: a live provider's instrument master lists some identities twice and
is re-synced on every startup, which previously raised a UniqueViolationError on
a populated table (per-row add with autoflush disabled).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import async_session_factory
from app.modules.market_data.domain.models import Exchange, InstrumentDTO, InstrumentType
from app.modules.market_data.orm import Instrument
from app.modules.market_data.repository import MarketDataRepository

pytestmark = pytest.mark.integration


def _eq(symbol: str) -> InstrumentDTO:
    return InstrumentDTO(symbol=symbol, exchange=Exchange.NSE, instrument_type=InstrumentType.EQ)


def _index(symbol: str) -> InstrumentDTO:
    return InstrumentDTO(symbol=symbol, exchange=Exchange.NSE, instrument_type=InstrumentType.INDEX)


async def test_subscription_always_includes_indices() -> None:
    # The dashboard ticker, market breadth, and the scanner benchmark all need the
    # headline indices streamed. They must be in the bounded subscription set even
    # when the operator's watchlist names none of them.
    async with async_session_factory() as session:
        repo = MarketDataRepository(session)
        await repo.upsert_instruments([_eq("RELIANCE"), _index("NIFTY"), _index("BANKNIFTY")])
        await session.commit()

        subs = await repo.subscription_symbol_ids(watchlist=["RELIANCE"])
        assert "RELIANCE" in subs  # the explicit watchlist name
        assert "NIFTY" in subs and "BANKNIFTY" in subs  # indices unioned in regardless


async def test_subscription_includes_symbols_with_history() -> None:
    # "Stream what you analyze": a symbol we hold stored candles for must be in the
    # live subscription even when it is in no watchlist and carries no Nifty-500
    # flag — seeding history is what enrols a symbol into the tracked universe.
    async with async_session_factory() as session:
        session.add(Instrument(symbol="SEEDED", exchange="NSE", instrument_type="EQ"))
        session.add(Instrument(symbol="UNSEEN", exchange="NSE", instrument_type="EQ"))
        await session.flush()
        repo = MarketDataRepository(session)
        iid = await repo.get_instrument_id("SEEDED")
        assert iid is not None
        await repo.upsert_candle(
            iid,
            "1d",
            datetime(2026, 3, 2, tzinfo=UTC),
            Decimal("100"),
            Decimal("101"),
            Decimal("99"),
            Decimal("100.5"),
            1000,
        )
        await session.commit()

        subs = await repo.subscription_symbol_ids()  # no watchlist, no flags
        assert "SEEDED" in subs  # has candles → subscribed
        assert "UNSEEN" not in subs  # no history, no flag → not streamed


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
