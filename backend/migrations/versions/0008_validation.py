"""validation runs (Sprint 14 — quant validation framework)

Revision ID: 0008_validation
Revises: 0007_admin
Create Date: 2026-07-22

Append-only store of cost-aware, out-of-sample strategy validation runs. Additive
and independent; safe to downgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_validation"
down_revision: str | None = "0007_admin"
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
        "validation_runs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="walk_forward"),
        sa.Column("params", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("results", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_ts_columns(),
    )
    op.create_index("ix_validation_runs_created_at", "validation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_validation_runs_created_at", table_name="validation_runs")
    op.drop_table("validation_runs")
