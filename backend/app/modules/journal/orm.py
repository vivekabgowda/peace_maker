"""Trade-journal persistence (Sprint 7).

The journal is the platform's **book of record** for closed trades. Every time a
paper position closes, one immutable :class:`JournalEntry` is written with the
performance figures denormalized (gross/net P&L, R-multiple, holding time) so the
analytics engine can read the whole trade history in a single query. Free-text
``notes`` and ``tags`` support the behavioural side of journalling.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

_BigIntPK = BigInteger().with_variant(Integer, "sqlite")
_Price = Numeric(18, 4)


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entries"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    # Link back to the paper position that produced this entry (nullable so the
    # journal can also hold manually imported trades later).
    position_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, unique=True)
    account_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # long | short
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")

    entry_price: Mapped[Decimal] = mapped_column(_Price, nullable=False)
    entry_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_price: Mapped[Decimal] = mapped_column(_Price, nullable=False)
    exit_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    exit_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)

    gross_pnl: Mapped[Decimal] = mapped_column(_Price, nullable=False)
    fees: Mapped[Decimal] = mapped_column(_Price, nullable=False, default=Decimal("0"))
    net_pnl: Mapped[Decimal] = mapped_column(_Price, nullable=False)
    r_multiple: Mapped[Decimal] = mapped_column(
        Numeric(12, 4), nullable=False, default=Decimal("0")
    )
    holding_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str] = mapped_column(String(10), nullable=False)  # win|loss|breakeven

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    __table_args__ = (
        Index("ix_journal_entries_exit_ts", "exit_ts"),
        Index("ix_journal_entries_strategy", "strategy_key"),
    )
