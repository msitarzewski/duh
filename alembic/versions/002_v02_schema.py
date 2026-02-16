"""v0.2 schema — taxonomy, outcomes, subtasks.

Revision ID: 002
Revises: 001
Create Date: 2026-02-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str = "001"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    # Add taxonomy columns to decisions
    with op.batch_alter_table("decisions") as batch_op:
        batch_op.add_column(sa.Column("intent", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("category", sa.String(50), nullable=True))
        batch_op.add_column(sa.Column("genus", sa.String(50), nullable=True))

    # Outcomes table
    op.create_table(
        "outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "decision_id",
            sa.String(36),
            sa.ForeignKey("decisions.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column(
            "thread_id",
            sa.String(36),
            sa.ForeignKey("threads.id"),
            nullable=False,
        ),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_outcomes_thread_id", "outcomes", ["thread_id"])

    # Subtasks table
    op.create_table(
        "subtasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "parent_thread_id",
            sa.String(36),
            sa.ForeignKey("threads.id"),
            nullable=False,
        ),
        sa.Column(
            "child_thread_id",
            sa.String(36),
            sa.ForeignKey("threads.id"),
            nullable=True,
        ),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("dependencies", sa.Text(), nullable=False, server_default="[]"),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("sequence_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_subtasks_parent_thread_id", "subtasks", ["parent_thread_id"]
    )


def downgrade() -> None:
    op.drop_table("subtasks")
    op.drop_table("outcomes")
    with op.batch_alter_table("decisions") as batch_op:
        batch_op.drop_column("genus")
        batch_op.drop_column("category")
        batch_op.drop_column("intent")
