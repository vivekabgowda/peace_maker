"""Paper-trading persistence (Sprint 7).

Three tables, all ordinary relational tables (not hypertables — this is account
state, not a time series):

- ``paper_accounts`` — one simulated account per user (starting cash, free cash,
  realized P&L).
- ``paper_orders``   — an immutable audit row for every order submitted
  (filled or rejected).
- ``paper_positions``— open and closed positions; a closed row is a round-trip.

Money is stored as ``Numeric(18, 4)`` (exact), matching the market-data tables;
the domain layer works in floats and converts at the repository boundary.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

_BigIntPK = BigInteger().with_variant(Integer, "sqlite")
_Price = Numeric(18, 4)


class PaperAccount(Base, TimestampMixin):
    __tablename__ = "paper_accounts"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    # One account per user. NULL user_id is the shared/default account (dev).
    user_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    starting_cash: Mapped[Decimal] = mapped_column(_Price, nullable=False)
    cash: Mapped[Decimal] = mapped_column(_Price, nullable=False)
    realized_pnl: Mapped[Decimal] = mapped_column(_Price, nullable=False, default=Decimal("0"))
    fees_paid: Mapped[Decimal] = mapped_column(_Price, nullable=False, default=Decimal("0"))


class PaperOrder(Base, TimestampMixin):
    __tablename__ = "paper_orders"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(8), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    limit_price: Mapped[Decimal | None] = mapped_column(_Price, nullable=True)
    reference_price: Mapped[Decimal | None] = mapped_column(_Price, nullable=True)
    fill_price: Mapped[Decimal | None] = mapped_column(_Price, nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120), nullable=True)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_paper_orders_account_submitted", "account_id", "submitted_at"),)


class PaperPosition(Base, TimestampMixin):
    __tablename__ = "paper_positions"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("paper_accounts.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # opening side
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    entry_price: Mapped[Decimal] = mapped_column(_Price, nullable=False)
    entry_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stop: Mapped[Decimal | None] = mapped_column(_Price, nullable=True)
    target: Mapped[Decimal | None] = mapped_column(_Price, nullable=True)
    strategy_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="open")
    exit_price: Mapped[Decimal | None] = mapped_column(_Price, nullable=True)
    exit_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(8), nullable=True)
    fees: Mapped[Decimal] = mapped_column(_Price, nullable=False, default=Decimal("0"))

    __table_args__ = (
        Index("ix_paper_positions_account_status", "account_id", "status"),
        Index("ix_paper_positions_symbol_status", "symbol", "status"),
    )
