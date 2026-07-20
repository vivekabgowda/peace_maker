"""timescaledb compression + retention on all hypertables

Revision ID: 0003_ts_policies
Revises: 0002_market
Create Date: 2026-07-20

Adds compression + retention policies to the indicator and option-chain
hypertables (candles were already compressed in 0002). Postgres-only; a no-op on
other engines. Retention windows are conservative defaults — tune per data
volume and licensing.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003_ts_policies"
down_revision: str | None = "0002_market"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if not _is_postgres():
        return

    # Compression on the high-volume time-series tables.
    op.execute(
        "ALTER TABLE market_indicators SET (timescaledb.compress, "
        "timescaledb.compress_segmentby = 'instrument_id, timeframe')"
    )
    op.execute(
        "ALTER TABLE option_chain_snapshots SET (timescaledb.compress, "
        "timescaledb.compress_segmentby = 'underlying')"
    )
    op.execute("SELECT add_compression_policy('market_indicators', INTERVAL '7 days')")
    op.execute("SELECT add_compression_policy('option_chain_snapshots', INTERVAL '2 days')")

    # Retention — drop old chunks automatically. Daily candles are downsampled
    # elsewhere; intraday data is bounded here.
    op.execute("SELECT add_retention_policy('option_chain_snapshots', INTERVAL '90 days')")
    op.execute("SELECT add_retention_policy('market_indicators', INTERVAL '180 days')")


def downgrade() -> None:
    if not _is_postgres():
        return
    op.execute("SELECT remove_retention_policy('market_indicators', if_exists => TRUE)")
    op.execute("SELECT remove_retention_policy('option_chain_snapshots', if_exists => TRUE)")
    op.execute("SELECT remove_compression_policy('market_indicators', if_exists => TRUE)")
    op.execute("SELECT remove_compression_policy('option_chain_snapshots', if_exists => TRUE)")
    op.execute("ALTER TABLE market_indicators SET (timescaledb.compress = false)")
    op.execute("ALTER TABLE option_chain_snapshots SET (timescaledb.compress = false)")
