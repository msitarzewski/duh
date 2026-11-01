"""Converge migrated schemas with the persisted ORM fields.

Revision ID: 006
Revises: 005

Existing SQLite installations may already have these columns from startup
patches. Preserve their contents while adding the missing constraints.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str = "005"
branch_labels: tuple[str, ...] | None = None
depends_on: str | None = None


def upgrade() -> None:
    thread_columns = {
        column["name"] for column in sa.inspect(op.get_bind()).get_columns("threads")
    }
    if (
        "slug" in thread_columns
        and op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM threads WHERE slug IS NOT NULL "
                "GROUP BY slug HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    ):
        raise RuntimeError(
            "Resolve duplicate thread slugs before migration; no rows were modified"
        )
    columns = {
        "users": [
            sa.Column(
                "is_guest", sa.Boolean(), server_default=sa.false(), nullable=False
            )
        ],
        "threads": [
            sa.Column(
                "is_public", sa.Boolean(), server_default=sa.false(), nullable=False
            ),
            sa.Column("slug", sa.String(200), nullable=True),
            sa.Column("followups_json", sa.Text(), nullable=True),
            sa.Column("usage_json", sa.Text(), nullable=True),
        ],
        "contributions": [sa.Column("citations_json", sa.Text(), nullable=True)],
        "decisions": [
            sa.Column("rigor", sa.Float(), server_default="0", nullable=False)
        ],
    }
    for table, additions in columns.items():
        existing = {
            col["name"]: col for col in sa.inspect(op.get_bind()).get_columns(table)
        }
        with op.batch_alter_table(table) as batch:
            for column in additions:
                if column.name not in existing:
                    batch.add_column(column)
                elif not column.nullable and existing[column.name]["nullable"]:
                    # Startup patches allowed NULL; fill only the absent value.
                    op.execute(
                        sa.table(table, sa.column(column.name))
                        .update()
                        .where(sa.column(column.name).is_(None))
                        .values(
                            {
                                column.name: False
                                if isinstance(column.type, sa.Boolean)
                                else 0
                            }
                        )
                    )
                    batch.alter_column(
                        column.name, existing_type=column.type, nullable=False
                    )
            if table == "users" and not existing["password_hash"]["nullable"]:
                batch.alter_column(
                    "password_hash", existing_type=sa.String(128), nullable=True
                )

    inspector = sa.inspect(op.get_bind())
    unique_slug = any(
        item["column_names"] == ["slug"]
        for item in inspector.get_unique_constraints("threads")
    ) or any(
        item["unique"] and item["column_names"] == ["slug"]
        for item in inspector.get_indexes("threads")
    )
    if not unique_slug:
        with op.batch_alter_table("threads") as batch:
            batch.create_unique_constraint("uq_threads_slug", ["slug"])
    for table, name, fields in (
        ("contributions", "ix_contributions_turn_role", ["turn_id", "role"]),
        ("decisions", "ix_decisions_thread_created", ["thread_id", "created_at"]),
        ("decisions", "ix_decisions_category_genus", ["category", "genus"]),
    ):
        existing_indexes = {
            item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)
        }
        if name not in existing_indexes:
            op.create_index(name, table, fields)
    # Revision 004 created both a unique index and a redundant UNIQUE
    # constraint. The ORM declares only the index; retain its enforcement.
    constraints = sa.inspect(op.get_bind()).get_unique_constraints("api_keys")
    for constraint in constraints:
        if constraint["column_names"] == ["key_hash"]:
            with op.batch_alter_table(
                "api_keys",
                naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
            ) as batch:
                batch.drop_constraint(
                    constraint["name"] or "uq_api_keys_key_hash", type_="unique"
                )


def downgrade() -> None:
    if (
        op.get_bind()
        .execute(sa.text("SELECT 1 FROM users WHERE password_hash IS NULL LIMIT 1"))
        .first()
    ):
        raise RuntimeError(
            "Cannot downgrade while passwordless users exist; preserve their data"
        )
    with op.batch_alter_table("api_keys") as batch:
        batch.create_unique_constraint("uq_api_keys_key_hash", ["key_hash"])
    for table, name in (
        ("contributions", "ix_contributions_turn_role"),
        ("decisions", "ix_decisions_thread_created"),
        ("decisions", "ix_decisions_category_genus"),
    ):
        op.drop_index(name, table_name=table)
    inspector = sa.inspect(op.get_bind())
    for index in inspector.get_indexes("threads"):
        if (
            index["unique"]
            and index["column_names"] == ["slug"]
            and not index.get("duplicates_constraint")
        ):
            op.drop_index(index["name"], table_name="threads")
    with op.batch_alter_table(
        "threads", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        for constraint in inspector.get_unique_constraints("threads"):
            if constraint["column_names"] == ["slug"]:
                batch.drop_constraint(
                    constraint["name"] or "uq_threads_slug", type_="unique"
                )
        for column in ("usage_json", "followups_json", "slug", "is_public"):
            batch.drop_column(column)
    with op.batch_alter_table("users") as batch:
        batch.drop_column("is_guest")
        batch.alter_column(
            "password_hash", existing_type=sa.String(128), nullable=False
        )
    op.drop_column("contributions", "citations_json")
    op.drop_column("decisions", "rigor")
