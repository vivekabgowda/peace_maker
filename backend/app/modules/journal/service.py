"""Trade-journal service (Sprint 7).

Writes one immutable entry per closed trade and serves the read side (list, get,
annotate). The paper-trading service calls :meth:`record` on every position close;
the analytics engine reads entries back through :meth:`stats_rows`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.modules.journal.models import ClosedTrade, JournalRecord, Outcome
from app.modules.journal.orm import JournalEntry

logger = get_logger("journal.service")


def _f(value: Decimal | float | None) -> float:
    return float(value) if value is not None else 0.0


class JournalService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(self, trade: ClosedTrade) -> JournalEntry:
        """Persist a closed trade. Idempotent per ``position_id`` (a re-close is
        ignored, protecting against duplicate exit events)."""
        if trade.position_id is not None:
            existing = await self._db.scalar(
                select(JournalEntry).where(JournalEntry.position_id == trade.position_id)
            )
            if existing is not None:
                return existing
        entry = JournalEntry(
            position_id=trade.position_id,
            account_id=trade.account_id,
            symbol=trade.symbol,
            direction=trade.direction,
            quantity=trade.quantity,
            strategy_key=trade.strategy_key,
            source=trade.source,
            entry_price=Decimal(str(trade.entry_price)),
            entry_ts=trade.entry_ts,
            exit_price=Decimal(str(trade.exit_price)),
            exit_ts=trade.exit_ts,
            exit_reason=trade.exit_reason,
            gross_pnl=Decimal(str(trade.gross_pnl)),
            fees=Decimal(str(trade.fees)),
            net_pnl=Decimal(str(trade.net_pnl)),
            r_multiple=Decimal(str(round(trade.r_multiple, 4))),
            holding_seconds=int(trade.holding_seconds),
            outcome=trade.outcome.value,
            tags=[],
        )
        self._db.add(entry)
        await self._db.flush()
        logger.info(
            "journal_entry_recorded",
            symbol=trade.symbol,
            net_pnl=round(trade.net_pnl, 2),
            outcome=trade.outcome.value,
        )
        return entry

    async def list_entries(
        self,
        *,
        strategy_key: str | None = None,
        symbol: str | None = None,
        since: datetime | None = None,
        limit: int = 200,
    ) -> list[JournalRecord]:
        stmt = select(JournalEntry).order_by(JournalEntry.exit_ts.desc())
        if strategy_key:
            stmt = stmt.where(JournalEntry.strategy_key == strategy_key)
        if symbol:
            stmt = stmt.where(JournalEntry.symbol == symbol)
        if since:
            stmt = stmt.where(JournalEntry.exit_ts >= since)
        stmt = stmt.limit(limit)
        rows = (await self._db.scalars(stmt)).all()
        return [self._to_record(r) for r in rows]

    async def get(self, entry_id: int) -> JournalRecord | None:
        row = await self._db.get(JournalEntry, entry_id)
        return self._to_record(row) if row else None

    async def annotate(
        self, entry_id: int, *, notes: str | None = None, tags: list[str] | None = None
    ) -> JournalRecord | None:
        row = await self._db.get(JournalEntry, entry_id)
        if row is None:
            return None
        if notes is not None:
            row.notes = notes
        if tags is not None:
            row.tags = tags
        await self._db.flush()
        return self._to_record(row)

    @staticmethod
    def _to_record(row: JournalEntry) -> JournalRecord:
        return JournalRecord(
            id=row.id,
            symbol=row.symbol,
            direction=row.direction,
            quantity=row.quantity,
            strategy_key=row.strategy_key,
            source=row.source,
            entry_price=_f(row.entry_price),
            entry_ts=row.entry_ts,
            exit_price=_f(row.exit_price),
            exit_ts=row.exit_ts,
            exit_reason=row.exit_reason,
            gross_pnl=_f(row.gross_pnl),
            fees=_f(row.fees),
            net_pnl=_f(row.net_pnl),
            r_multiple=_f(row.r_multiple),
            holding_seconds=row.holding_seconds,
            outcome=row.outcome or Outcome.of(_f(row.net_pnl)).value,
            notes=row.notes,
            tags=list(row.tags or []),
        )
