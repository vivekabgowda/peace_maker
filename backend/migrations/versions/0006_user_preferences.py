"""user profile preferences (Sprint 9 — Settings page)

Revision ID: 0006_prefs
Revises: 0005_paper
Create Date: 2026-07-22

Adds a JSON ``preferences`` column to ``user_profiles`` holding trading,
notification and appearance settings edited from the Settings page. The API
layer (``Preferences`` Pydantic model) is the source of truth for the shape;
the column defaults to an empty object so existing rows read back as defaults.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_prefs"
down_revision: str | None = "0005_paper"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "user_profiles",
        sa.Column(
            "preferences",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("user_profiles", "preferences")
