"""broker credential storage (Sprint 6 — Zerodha Kite Connect)

Revision ID: 0004_broker
Revises: 0003_ts_policies
Create Date: 2026-07-21

One encrypted token row per broker. Not a hypertable (identity data, not a series).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_broker"
down_revision: str | None = "0003_ts_policies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "broker_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("broker", sa.String(32), nullable=False),
        sa.Column("kite_user_id", sa.String(64), nullable=True),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("public_token_enc", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.UniqueConstraint("broker", name="uq_broker_tokens_broker"),
    )


def downgrade() -> None:
    op.drop_table("broker_tokens")
