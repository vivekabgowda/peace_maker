"""market intelligence layer (instruments, candles, indicators, options, news)

Revision ID: 0002_market
Revises: 0001_initial
Create Date: 2026-07-20

Sprint 2 schema. Time-series tables become TimescaleDB hypertables with
compression policies. Hypertable creation is guarded so the migration is a no-op
for those steps on non-Postgres engines.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_market"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("exchange", sa.String(8), nullable=False),
        sa.Column("instrument_type", sa.String(8), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("lot_size", sa.Integer(), nullable=True),
        sa.Column("tick_size", sa.Numeric(10, 4), nullable=True),
        sa.Column("isin", sa.String(20), nullable=True),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("in_fno", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("in_nifty500", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("provider_token", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("symbol", "exchange", "instrument_type", name="uq_instrument_identity"),
    )
    op.create_index(
        "ix_instruments_fno", "instruments", ["in_fno"], postgresql_where=sa.text("in_fno")
    )
    op.create_index("ix_instruments_symbol", "instruments", ["symbol"])

    op.create_table(
        "candles",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(18, 4), nullable=False),
        sa.Column("high", sa.Numeric(18, 4), nullable=False),
        sa.Column("low", sa.Numeric(18, 4), nullable=False),
        sa.Column("close", sa.Numeric(18, 4), nullable=False),
        sa.Column("volume", sa.BigInteger(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("instrument_id", "timeframe", "ts"),
    )

    op.create_table(
        "market_indicators",
        sa.Column("instrument_id", sa.BigInteger(), nullable=False),
        sa.Column("timeframe", sa.String(8), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ema_9", sa.Numeric(18, 4), nullable=True),
        sa.Column("ema_21", sa.Numeric(18, 4), nullable=True),
        sa.Column("ema_50", sa.Numeric(18, 4), nullable=True),
        sa.Column("ema_200", sa.Numeric(18, 4), nullable=True),
        sa.Column("rsi_14", sa.Numeric(10, 4), nullable=True),
        sa.Column("macd", sa.Numeric(18, 6), nullable=True),
        sa.Column("macd_signal", sa.Numeric(18, 6), nullable=True),
        sa.Column("atr_14", sa.Numeric(18, 4), nullable=True),
        sa.Column("adx_14", sa.Numeric(10, 4), nullable=True),
        sa.Column("vwap", sa.Numeric(18, 4), nullable=True),
        sa.Column("supertrend", sa.Numeric(18, 4), nullable=True),
        sa.Column("supertrend_dir", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("instrument_id", "timeframe", "ts"),
    )

    # Natural composite PK (underlying, expiry, ts). The partition column ``ts``
    # must be part of every unique index for TimescaleDB to build the hypertable,
    # so there is no surrogate id here.
    op.create_table(
        "option_chain_snapshots",
        sa.Column("underlying", sa.String(64), nullable=False),
        sa.Column("expiry", sa.String(20), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("spot", sa.Numeric(18, 4), nullable=False),
        sa.Column("pcr", sa.Numeric(10, 4), nullable=True),
        sa.Column("max_pain", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_ce_oi", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("total_pe_oi", sa.BigInteger(), server_default="0", nullable=False),
        sa.PrimaryKeyConstraint("underlying", "expiry", "ts"),
    )

    op.create_table(
        "news_articles",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(40), nullable=False),
        sa.Column("headline", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.String(1000), nullable=True),
        sa.Column("category", sa.String(40), server_default="general", nullable=False),
        sa.Column("sentiment", sa.Numeric(6, 4), server_default="0", nullable=False),
        sa.Column("impact", sa.Numeric(6, 4), server_default="0", nullable=False),
        sa.Column("symbols", sa.String(500), server_default="", nullable=False),
        sa.Column("sectors", sa.String(500), server_default="", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_news_published", "news_articles", ["published_at"])

    # --- TimescaleDB hypertables + compression (Postgres only) -------------
    if _is_postgres():
        for table, interval in (
            ("candles", "7 days"),
            ("market_indicators", "7 days"),
            ("option_chain_snapshots", "1 day"),
        ):
            op.execute(
                f"SELECT create_hypertable('{table}', 'ts', "
                f"chunk_time_interval => INTERVAL '{interval}', if_not_exists => TRUE, "
                f"migrate_data => TRUE)"
            )
        op.execute(
            "ALTER TABLE candles SET (timescaledb.compress, "
            "timescaledb.compress_segmentby = 'instrument_id, timeframe')"
        )
        op.execute("SELECT add_compression_policy('candles', INTERVAL '7 days')")


def downgrade() -> None:
    op.drop_table("news_articles")
    op.drop_table("option_chain_snapshots")
    op.drop_table("market_indicators")
    op.drop_table("candles")
    op.drop_table("instruments")
