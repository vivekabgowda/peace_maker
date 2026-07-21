"""paper trading, trade journal & performance reports (Sprint 7)

Revision ID: 0005_paper
Revises: 0004_broker
Create Date: 2026-07-21

Ordinary relational tables (account state, closed-trade book of record, stored
reports) — none are hypertables. No live order path exists anywhere; these tables
record *simulated* fills against live read-only prices.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_paper"
down_revision: str | None = "0004_broker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _ts_columns() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "paper_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(64), nullable=True),
        sa.Column("starting_cash", sa.Numeric(18, 4), nullable=False),
        sa.Column("cash", sa.Numeric(18, 4), nullable=False),
        sa.Column("realized_pnl", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("fees_paid", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_ts_columns(),
        sa.UniqueConstraint("user_id", name="uq_paper_accounts_user_id"),
    )

    op.create_table(
        "paper_orders",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("order_type", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("limit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("reference_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("fill_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("reason", sa.String(120), nullable=True),
        sa.Column("strategy_key", sa.String(64), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        *_ts_columns(),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["paper_accounts.id"],
            ondelete="CASCADE",
            name="fk_paper_orders_account_id_paper_accounts",
        ),
    )
    op.create_index(
        "ix_paper_orders_account_submitted", "paper_orders", ["account_id", "submitted_at"]
    )

    op.create_table(
        "paper_positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("side", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("entry_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stop", sa.Numeric(18, 4), nullable=True),
        sa.Column("target", sa.Numeric(18, 4), nullable=True),
        sa.Column("strategy_key", sa.String(64), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("status", sa.String(8), nullable=False, server_default="open"),
        sa.Column("exit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("exit_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_reason", sa.String(8), nullable=True),
        sa.Column("fees", sa.Numeric(18, 4), nullable=False, server_default="0"),
        *_ts_columns(),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["paper_accounts.id"],
            ondelete="CASCADE",
            name="fk_paper_positions_account_id_paper_accounts",
        ),
    )
    op.create_index(
        "ix_paper_positions_account_status", "paper_positions", ["account_id", "status"]
    )
    op.create_index("ix_paper_positions_symbol_status", "paper_positions", ["symbol", "status"])

    op.create_table(
        "journal_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("position_id", sa.BigInteger(), nullable=True),
        sa.Column("account_id", sa.BigInteger(), nullable=True),
        sa.Column("symbol", sa.String(64), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("strategy_key", sa.String(64), nullable=True),
        sa.Column("source", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("entry_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("entry_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("exit_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exit_reason", sa.String(8), nullable=True),
        sa.Column("gross_pnl", sa.Numeric(18, 4), nullable=False),
        sa.Column("fees", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("net_pnl", sa.Numeric(18, 4), nullable=False),
        sa.Column("r_multiple", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("holding_seconds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        *_ts_columns(),
        sa.UniqueConstraint("position_id", name="uq_journal_entries_position_id"),
    )
    op.create_index("ix_journal_entries_exit_ts", "journal_entries", ["exit_ts"])
    op.create_index("ix_journal_entries_strategy", "journal_entries", ["strategy_key"])

    op.create_table(
        "performance_reports",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("rendered", sa.Text(), nullable=False),
        *_ts_columns(),
        sa.UniqueConstraint("kind", "period_start", name="uq_performance_reports_kind_period"),
    )
    op.create_index(
        "ix_performance_reports_kind_end", "performance_reports", ["kind", "period_end"]
    )


def downgrade() -> None:
    op.drop_table("performance_reports")
    op.drop_table("journal_entries")
    op.drop_table("paper_positions")
    op.drop_table("paper_orders")
    op.drop_table("paper_accounts")
