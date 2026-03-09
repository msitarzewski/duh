"""Lightweight schema migrations for SQLite.

Runs on startup for file-based SQLite databases to add new columns
that were added after the initial schema. In-memory SQLite uses
``create_all`` which handles new columns automatically.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

logger = logging.getLogger(__name__)


async def _get_columns(conn: AsyncConnection, table: str) -> set[str]:
    """Get column names for a table via PRAGMA."""
    rows = await conn.exec_driver_sql(f"PRAGMA table_info({table})")
    return {row[1] for row in rows}


async def ensure_schema(engine: AsyncEngine) -> None:
    """Apply pending schema migrations.

    Handles:
    - Adding ``rigor`` column to ``decisions`` table.
    - Adding ``is_guest`` column to ``users`` table.
    - Adding ``is_public`` and ``slug`` columns to ``threads`` table.
    - Making ``password_hash`` nullable on ``users`` (SQLite: already nullable
      if created with current models; this is a no-op safety check).
    """
    async with engine.begin() as conn:
        # ── decisions table ──
        decision_cols = await _get_columns(conn, "decisions")
        if "rigor" not in decision_cols:
            logger.info("Adding 'rigor' column to decisions table")
            await conn.exec_driver_sql(
                "ALTER TABLE decisions ADD COLUMN rigor FLOAT DEFAULT 0.0"
            )

        # ── users table ──
        user_cols = await _get_columns(conn, "users")
        if "is_guest" not in user_cols:
            logger.info("Adding 'is_guest' column to users table")
            await conn.exec_driver_sql(
                "ALTER TABLE users ADD COLUMN is_guest BOOLEAN DEFAULT 0"
            )

        # ── contributions table ──
        contrib_cols = await _get_columns(conn, "contributions")
        if "citations_json" not in contrib_cols:
            logger.info("Adding 'citations_json' column to contributions table")
            await conn.exec_driver_sql(
                "ALTER TABLE contributions ADD COLUMN citations_json TEXT DEFAULT NULL"
            )

        # ── threads table ──
        thread_cols = await _get_columns(conn, "threads")
        if "is_public" not in thread_cols:
            logger.info("Adding 'is_public' column to threads table")
            await conn.exec_driver_sql(
                "ALTER TABLE threads ADD COLUMN is_public BOOLEAN DEFAULT 0"
            )
        if "slug" not in thread_cols:
            logger.info("Adding 'slug' column to threads table")
            await conn.exec_driver_sql(
                "ALTER TABLE threads ADD COLUMN slug VARCHAR(200) DEFAULT NULL"
            )
        if "followups_json" not in thread_cols:
            logger.info("Adding 'followups_json' column to threads table")
            await conn.exec_driver_sql(
                "ALTER TABLE threads ADD COLUMN followups_json TEXT DEFAULT NULL"
            )
