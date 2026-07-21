"""Candle upsert widens the range instead of overwriting it (finding #18)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.database import async_session_factory
from app.modules.market_data.domain.models import Exchange, InstrumentDTO, InstrumentType
from app.modules.market_data.repository import MarketDataRepository

pytestmark = pytest.mark.integration


async def test_upsert_candle_uses_greatest_least() -> None:
    ts = datetime(2026, 1, 27, 4, 0, tzinfo=UTC)
    async with async_session_factory() as session:
        repo = MarketDataRepository(session)
        await repo.upsert_instruments(
            [InstrumentDTO(symbol="ACME", exchange=Exchange.NSE, instrument_type=InstrumentType.EQ)]
        )
        iid = await repo.get_instrument_id("ACME")
        assert iid is not None

        # First write for the bar.
        await repo.upsert_candle(
            iid, "5m", ts, Decimal("100"), Decimal("105"), Decimal("99"), Decimal("102"), 1000
        )
        # A late duplicate for the SAME bar with a lower high / higher low must
        # NOT shrink the candle; volume takes the larger.
        await repo.upsert_candle(
            iid, "5m", ts, Decimal("100"), Decimal("104"), Decimal("101"), Decimal("103"), 800
        )
        await session.commit()

        rows = await repo.recent_candles(iid, "5m", 10)
        assert len(rows) == 1
        candle = rows[0]
        assert float(candle.high) == 105.0  # kept the higher high
        assert float(candle.low) == 99.0  # kept the lower low
        assert float(candle.close) == 103.0  # latest close
        assert candle.volume == 1000  # larger volume
