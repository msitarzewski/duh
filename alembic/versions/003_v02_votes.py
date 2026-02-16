"""v0.2 schema -- votes table for voting protocol.

Revision ID: 003
Revises: 002
Create Date: 2026-02-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str = "002"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "votes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("threads.id"),
            nullable=False,
        ),
        sa.Column("model_ref", sa.String(100), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_votes_thread_id", "votes", ["thread_id"])


def downgrade() -> None:
    op.drop_table("votes")
