"""Persistence for market data (instruments, candles, indicators, options)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.market_data.domain.models import InstrumentDTO
from app.modules.market_data.orm import (
    Candle,
    Instrument,
    MarketIndicator,
    OptionChainSnapshotRow,
)


class MarketDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -- Instruments --------------------------------------------------------
    async def upsert_instruments(self, instruments: list[InstrumentDTO]) -> int:
        count = 0
        for dto in instruments:
            existing = await self._session.scalar(
                select(Instrument).where(
                    Instrument.symbol == dto.symbol,
                    Instrument.exchange == dto.exchange.value,
                    Instrument.instrument_type == dto.instrument_type.value,
                )
            )
            if existing is None:
                self._session.add(
                    Instrument(
                        symbol=dto.symbol,
                        exchange=dto.exchange.value,
                        instrument_type=dto.instrument_type.value,
                        name=dto.name,
                        lot_size=dto.lot_size,
                        tick_size=dto.tick_size,
                        isin=dto.isin,
                        sector=dto.sector,
                        industry=dto.industry,
                        in_fno=dto.in_fno,
                        in_nifty500=dto.in_nifty500,
                        provider_token=dto.provider_token,
                    )
                )
                count += 1
            else:
                existing.sector = dto.sector
                existing.industry = dto.industry
                existing.in_fno = dto.in_fno
                existing.in_nifty500 = dto.in_nifty500
        await self._session.flush()
        return count

    async def list_instruments(self, *, fno_only: bool = False) -> list[Instrument]:
        stmt = select(Instrument).where(Instrument.is_active.is_(True))
        if fno_only:
            stmt = stmt.where(Instrument.in_fno.is_(True))
        return list((await self._session.execute(stmt.order_by(Instrument.symbol))).scalars())

    async def get_instrument_id(self, symbol: str) -> int | None:
        result = await self._session.scalar(
            select(Instrument.id).where(Instrument.symbol == symbol).limit(1)
        )
        return int(result) if result is not None else None

    async def symbol_id_map(self) -> dict[str, int]:
        rows = (await self._session.execute(select(Instrument.symbol, Instrument.id))).all()
        return {row[0]: row[1] for row in rows}

    async def subscription_symbol_ids(
        self,
        *,
        watchlist: Sequence[str] = (),
        include_fno: bool = False,
        limit: int = 3000,
    ) -> dict[str, int]:
        """Bounded symbol→id map for a live WebSocket subscription.

        A live provider's instrument master covers the whole exchange (100k+
        rows), far more than one broker socket can carry. Prefer the symbols the
        platform actually scans — Nifty 500, plus (optionally) F&O names and the
        operator's explicit watchlist. If none of those are flagged yet (a fresh
        live universe has no Nifty-500 membership wired), fall back to NSE cash
        equity so the feed still streams a sensible default set. Always bounded by
        ``limit`` (Kite allows ~3000 instruments per connection).
        """
        conditions = [Instrument.in_nifty500.is_(True)]
        if include_fno:
            conditions.append(Instrument.in_fno.is_(True))
        if watchlist:
            conditions.append(Instrument.symbol.in_(list(watchlist)))
        stmt = (
            select(Instrument.symbol, Instrument.id)
            .where(Instrument.is_active.is_(True), or_(*conditions))
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        if rows:
            return {row[0]: row[1] for row in rows}
        # Fallback: bounded NSE cash equity (no Nifty-500 flags / watchlist yet).
        stmt = (
            select(Instrument.symbol, Instrument.id)
            .where(
                Instrument.is_active.is_(True),
                Instrument.exchange == "NSE",
                Instrument.instrument_type == "EQ",
            )
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    # -- Candles ------------------------------------------------------------
    async def upsert_candle(
        self,
        instrument_id: int,
        timeframe: str,
        ts: datetime,
        o: Decimal,
        h: Decimal,
        low: Decimal,
        c: Decimal,
        volume: int,
    ) -> None:
        is_pg = self._session.bind.dialect.name == "postgresql"
        insert = pg_insert if is_pg else sqlite_insert
        # On a late/duplicate bar, widen the range rather than overwrite it.
        greatest = func.greatest if is_pg else func.max
        least = func.least if is_pg else func.min
        stmt = insert(Candle).values(
            instrument_id=instrument_id,
            timeframe=timeframe,
            ts=ts,
            open=o,
            high=h,
            low=low,
            close=c,
            volume=volume,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_id", "timeframe", "ts"],
            set_={
                "high": greatest(Candle.high, stmt.excluded.high),
                "low": least(Candle.low, stmt.excluded.low),
                "close": stmt.excluded.close,
                "volume": greatest(Candle.volume, stmt.excluded.volume),
            },
        )
        await self._session.execute(stmt)

    async def recent_candles(
        self, instrument_id: int, timeframe: str, limit: int = 300
    ) -> list[Candle]:
        stmt = (
            select(Candle)
            .where(Candle.instrument_id == instrument_id, Candle.timeframe == timeframe)
            .order_by(Candle.ts.desc())
            .limit(limit)
        )
        rows = list((await self._session.execute(stmt)).scalars())
        return list(reversed(rows))  # oldest first

    # -- Indicators ---------------------------------------------------------
    async def upsert_indicators(
        self, instrument_id: int, timeframe: str, ts: datetime, values: dict[str, object]
    ) -> None:
        insert = pg_insert if self._session.bind.dialect.name == "postgresql" else sqlite_insert
        stmt = insert(MarketIndicator).values(
            instrument_id=instrument_id, timeframe=timeframe, ts=ts, **values
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["instrument_id", "timeframe", "ts"], set_=values
        )
        await self._session.execute(stmt)

    # -- Option chain -------------------------------------------------------
    async def insert_option_snapshot(
        self,
        underlying: str,
        expiry: str,
        ts: datetime,
        spot: Decimal,
        pcr: Decimal | None,
        max_pain: Decimal | None,
        total_ce_oi: int,
        total_pe_oi: int,
    ) -> None:
        # Natural PK is (underlying, expiry, ts); a repeated snapshot for the
        # same key is upserted (idempotent) rather than raising a conflict.
        insert = pg_insert if self._session.bind.dialect.name == "postgresql" else sqlite_insert
        values = {
            "underlying": underlying,
            "expiry": expiry,
            "ts": ts,
            "spot": spot,
            "pcr": pcr,
            "max_pain": max_pain,
            "total_ce_oi": total_ce_oi,
            "total_pe_oi": total_pe_oi,
        }
        stmt = insert(OptionChainSnapshotRow).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["underlying", "expiry", "ts"],
            set_={
                "spot": stmt.excluded.spot,
                "pcr": stmt.excluded.pcr,
                "max_pain": stmt.excluded.max_pain,
                "total_ce_oi": stmt.excluded.total_ce_oi,
                "total_pe_oi": stmt.excluded.total_pe_oi,
            },
        )
        await self._session.execute(stmt)
