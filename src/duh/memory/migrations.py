"""Lightweight schema migrations for SQLite.

Runs on startup for file-based SQLite databases to add new columns
that were added after the initial schema. In-memory SQLite uses
``create_all`` which handles new columns automatically.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

logger = logging.getLogger(__name__)


async def ensure_schema(engine: AsyncEngine) -> None:
    """Apply pending schema migrations.

    Currently handles:
    - Adding ``rigor`` column to ``decisions`` table (Phase A).
    """
    async with engine.begin() as conn:
        # Check if rigor column exists
        rows = await conn.exec_driver_sql("PRAGMA table_info(decisions)")
        columns = {row[1] for row in rows}

        if "rigor" not in columns:
            logger.info("Adding 'rigor' column to decisions table")
            await conn.exec_driver_sql(
                "ALTER TABLE decisions ADD COLUMN rigor FLOAT DEFAULT 0.0"
            )
