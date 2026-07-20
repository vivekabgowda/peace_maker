"""Market-data ORM models (instruments, candles, indicators, option snapshots).

Time-series tables (candles, market_indicators, option_chain_snapshots) become
TimescaleDB hypertables in the migration; the ORM shape stays portable (the test
suite runs them on SQLite).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin

# BigInteger PKs need INTEGER on SQLite for rowid autoincrement (test suite).
_BigIntPK = BigInteger().with_variant(Integer, "sqlite")


class Instrument(Base, TimestampMixin):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(64), nullable=False)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)
    instrument_type: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    lot_size: Mapped[int | None] = mapped_column(nullable=True)
    tick_size: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    isin: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sector: Mapped[str | None] = mapped_column(String(100), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    in_fno: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    in_nifty500: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    provider_token: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        UniqueConstraint("symbol", "exchange", "instrument_type", name="uq_instrument_identity"),
    )


class Candle(Base):
    __tablename__ = "candles"

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)


class MarketIndicator(Base):
    __tablename__ = "market_indicators"

    instrument_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True
    )
    timeframe: Mapped[str] = mapped_column(String(8), primary_key=True)
    ts: Mapped[datetime] = mapped_column(primary_key=True)
    ema_9: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ema_21: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ema_50: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    ema_200: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    rsi_14: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    macd: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    macd_signal: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    atr_14: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    adx_14: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    vwap: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    supertrend: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    supertrend_dir: Mapped[int | None] = mapped_column(nullable=True)


class OptionChainSnapshotRow(Base):
    __tablename__ = "option_chain_snapshots"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    underlying: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    expiry: Mapped[str] = mapped_column(String(20), nullable=False)
    ts: Mapped[datetime] = mapped_column(nullable=False)
    spot: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    pcr: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_pain: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_ce_oi: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_pe_oi: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
