"""news intelligence assessments (Sprint 11 — institutional news agent)

Revision ID: 0009_news_intelligence
Revises: 0008_validation
Create Date: 2026-07-26

Append-only history of per-symbol News Intelligence assessments — the training
substrate for continuous calibration and the read model for the CIO/Scanner/
Journal/Analytics. Additive and independent; safe to downgrade.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_news_intelligence"
down_revision: str | None = "0008_validation"
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
        "news_assessments",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer, "sqlite"), primary_key=True),
        sa.Column("symbol", sa.String(length=64), nullable=False),
        sa.Column("news_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("sentiment", sa.String(length=20), nullable=False, server_default="neutral"),
        sa.Column("confidence", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("source_reliability", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "verification_status", sa.String(length=20), nullable=False, server_default="pending"
        ),
        sa.Column("impact_horizon", sa.String(length=20), nullable=False, server_default="swing"),
        sa.Column(
            "impact_timing", sa.String(length=20), nullable=False, server_default="multi_day"
        ),
        sa.Column("dominant_session", sa.String(length=20), nullable=True),
        sa.Column("article_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        *_ts_columns(),
    )
    op.create_index("ix_news_assessments_symbol", "news_assessments", ["symbol"])
    op.create_index(
        "ix_news_assessments_symbol_generated",
        "news_assessments",
        ["symbol", "generated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_news_assessments_symbol_generated", table_name="news_assessments")
    op.drop_index("ix_news_assessments_symbol", table_name="news_assessments")
    op.drop_table("news_assessments")
