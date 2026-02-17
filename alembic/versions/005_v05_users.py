"""v0.5 users table and user_id foreign keys.

Revision ID: 005
Revises: 004
Create Date: 2026-02-17
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="contributor"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # Add user_id column to threads (batch mode for SQLite compatibility)
    with op.batch_alter_table("threads") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(36), nullable=True))
        batch_op.create_index("ix_threads_user_id", ["user_id"])
        batch_op.create_foreign_key(
            "fk_threads_user_id", "users", ["user_id"], ["id"]
        )

    # Add user_id column to decisions
    with op.batch_alter_table("decisions") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(36), nullable=True))
        batch_op.create_index("ix_decisions_user_id", ["user_id"])
        batch_op.create_foreign_key(
            "fk_decisions_user_id", "users", ["user_id"], ["id"]
        )

    # Add user_id column to api_keys
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.String(36), nullable=True))
        batch_op.create_index("ix_api_keys_user_id", ["user_id"])
        batch_op.create_foreign_key(
            "fk_api_keys_user_id", "users", ["user_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("api_keys") as batch_op:
        batch_op.drop_index("ix_api_keys_user_id")
        batch_op.drop_constraint("fk_api_keys_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("decisions") as batch_op:
        batch_op.drop_index("ix_decisions_user_id")
        batch_op.drop_constraint("fk_decisions_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    with op.batch_alter_table("threads") as batch_op:
        batch_op.drop_index("ix_threads_user_id")
        batch_op.drop_constraint("fk_threads_user_id", type_="foreignkey")
        batch_op.drop_column("user_id")

    op.drop_table("users")
