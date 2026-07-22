"""admin: committee config + audit log (Sprint 12)

Revision ID: 0007_admin
Revises: 0006_prefs
Create Date: 2026-07-22

Backing tables for the Admin dashboard: a single-row committee configuration
(operator overrides for agent enable/weight and CIO thresholds) and an
append-only audit trail of privileged actions.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_admin"
down_revision: str | None = "0006_prefs"
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
        "committee_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_ts_columns(),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("actor_email", sa.String(length=320), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=120), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        *_ts_columns(),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("committee_config")
