"""audit fixes: odds.last_seen_at, value_opportunities.blended_probability

Revision ID: a2b3c4d5e6f7
Revises: 17f992f36279
Create Date: 2026-08-30
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a2b3c4d5e6f7"
down_revision = "17f992f36279"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("odds") as b:
        b.add_column(sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    with op.batch_alter_table("value_opportunities") as b:
        b.add_column(sa.Column("blended_probability", sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("value_opportunities") as b:
        b.drop_column("blended_probability")
    with op.batch_alter_table("odds") as b:
        b.drop_column("last_seen_at")
