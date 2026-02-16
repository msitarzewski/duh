"""v0.1 baseline schema.

Revision ID: 001
Revises:
Create Date: 2026-02-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_threads_status", "threads", ["status"])
    op.create_index("ix_threads_created_at", "threads", ["created_at"])

    op.create_table(
        "turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("threads.id"),
            nullable=False,
        ),
        sa.Column("round_number", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_turns_thread_id", "turns", ["thread_id"])
    op.create_index(
        "ix_turns_thread_round",
        "turns",
        ["thread_id", "round_number"],
        unique=True,
    )

    op.create_table(
        "contributions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "turn_id",
            sa.String(36),
            sa.ForeignKey("turns.id"),
            nullable=False,
        ),
        sa.Column("model_ref", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("latency_ms", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contributions_turn_id", "contributions", ["turn_id"])
    op.create_index("ix_contributions_model_ref", "contributions", ["model_ref"])

    op.create_table(
        "turn_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "turn_id",
            sa.String(36),
            sa.ForeignKey("turns.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model_ref", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "thread_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("threads.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model_ref", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "turn_id",
            sa.String(36),
            sa.ForeignKey("turns.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("threads.id"),
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("dissent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_decisions_thread_id", "decisions", ["thread_id"])


def downgrade() -> None:
    op.drop_table("decisions")
    op.drop_table("thread_summaries")
    op.drop_table("turn_summaries")
    op.drop_table("contributions")
    op.drop_table("turns")
    op.drop_table("threads")
