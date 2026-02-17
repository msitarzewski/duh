"""Database backup and restore utilities."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def detect_db_type(db_url: str) -> str:
    """Return 'sqlite' or 'postgresql' based on URL."""
    if db_url.startswith("sqlite"):
        return "sqlite"
    if db_url.startswith("postgresql") or db_url.startswith("postgres"):
        return "postgresql"
    return "unknown"


async def backup_sqlite(db_url: str, dest: Path) -> Path:
    """Copy SQLite file to destination."""
    # Extract file path from sqlite:///path or sqlite+aiosqlite:///path
    if ":///" not in db_url:
        msg = f"Cannot extract file path from URL: {db_url}"
        raise ValueError(msg)

    raw_path = db_url.split("///", 1)[1]
    if not raw_path or raw_path == ":memory:":
        msg = "Cannot backup an in-memory SQLite database via file copy"
        raise ValueError(msg)

    # Expand ~ in paths
    src = Path(raw_path).expanduser()
    if not src.exists():
        msg = f"SQLite database file not found: {src}"
        raise FileNotFoundError(msg)

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


async def backup_json(session: AsyncSession, dest: Path) -> Path:
    """Export all tables to portable JSON format."""
    from sqlalchemy import inspect, select

    from duh.memory.models import (
        APIKey,
        Contribution,
        Decision,
        Outcome,
        Subtask,
        Thread,
        ThreadSummary,
        Turn,
        TurnSummary,
        Vote,
    )

    tables: dict[str, type[Any]] = {
        "threads": Thread,
        "turns": Turn,
        "contributions": Contribution,
        "turn_summaries": TurnSummary,
        "thread_summaries": ThreadSummary,
        "decisions": Decision,
        "outcomes": Outcome,
        "subtasks": Subtask,
        "votes": Vote,
        "api_keys": APIKey,
    }

    # Check if users table exists (may not be migrated yet)
    try:
        from duh.memory.models import User

        tables["users"] = User
    except ImportError:
        pass

    data: dict[str, Any] = {
        "version": "0.5.0",
        "exported_at": datetime.now(UTC).isoformat(),
        "tables": {},
    }

    for table_name, model_cls in tables.items():
        try:
            stmt = select(model_cls)
            result = await session.execute(stmt)
            rows = result.scalars().all()
        except Exception:
            # Table may not exist yet in the database
            data["tables"][table_name] = []
            continue

        row_list = []
        for row in rows:
            mapper = inspect(type(row))
            row_dict: dict[str, Any] = {}
            for col in mapper.columns:
                val = getattr(row, col.key)
                if isinstance(val, datetime):
                    val = val.isoformat()
                row_dict[col.key] = val
            row_list.append(row_dict)

        data["tables"][table_name] = row_list

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return dest


def detect_backup_format(source: Path) -> str:
    """Detect if backup file is 'sqlite' or 'json'.

    Reads the first bytes of the file to determine format.

    Raises:
        ValueError: If the file format cannot be determined.
    """
    with open(source, "rb") as f:
        header = f.read(16)

    if not header:
        msg = f"Cannot detect format: file is empty: {source}"
        raise ValueError(msg)

    if header.lstrip()[:1] in (b"{", b"["):
        return "json"
    if header.startswith(b"SQLite format"):
        return "sqlite"

    msg = f"Cannot detect backup format for: {source}"
    raise ValueError(msg)


async def restore_sqlite(source: Path, db_url: str) -> None:
    """Restore SQLite database from a backup file.

    Copies the source file to the database path extracted from the URL,
    overwriting the existing database.
    """
    if ":///" not in db_url:
        msg = f"Cannot extract file path from URL: {db_url}"
        raise ValueError(msg)

    raw_path = db_url.split("///", 1)[1]
    if not raw_path or raw_path == ":memory:":
        msg = "Cannot restore to an in-memory SQLite database"
        raise ValueError(msg)

    db_path = Path(raw_path).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, db_path)


async def restore_json(
    session: AsyncSession, source: Path, *, merge: bool = False
) -> dict[str, int]:
    """Restore database from JSON backup.

    Args:
        session: Database session.
        source: Path to JSON backup file.
        merge: If True, add records (skip conflicts). If False, clear tables first.

    Returns:
        dict with counts of restored records per table.
    """
    from sqlalchemy import DateTime as SADateTime
    from sqlalchemy import delete, inspect

    from duh.memory.models import (
        APIKey,
        Contribution,
        Decision,
        Outcome,
        Subtask,
        Thread,
        ThreadSummary,
        Turn,
        TurnSummary,
        Vote,
    )

    data = json.loads(source.read_text(encoding="utf-8"))

    if "tables" not in data:
        msg = "Invalid backup: missing 'tables' key"
        raise ValueError(msg)

    # Model map in dependency order (parents before children)
    model_map: dict[str, type[Any]] = {
        "threads": Thread,
        "turns": Turn,
        "contributions": Contribution,
        "turn_summaries": TurnSummary,
        "thread_summaries": ThreadSummary,
        "decisions": Decision,
        "outcomes": Outcome,
        "subtasks": Subtask,
        "votes": Vote,
        "api_keys": APIKey,
    }

    # Check if users table exists
    try:
        from duh.memory.models import User

        model_map = {"users": User, **model_map}
    except ImportError:
        pass

    # Delete order is reverse of insert (children before parents)
    if not merge:
        import contextlib

        delete_order = list(reversed(model_map.keys()))
        for table_name in delete_order:
            model_cls = model_map[table_name]
            with contextlib.suppress(Exception):
                await session.execute(delete(model_cls))
        await session.flush()

    counts: dict[str, int] = {}

    for table_name, model_cls in model_map.items():
        rows = data["tables"].get(table_name, [])
        if not rows:
            counts[table_name] = 0
            continue

        mapper = inspect(model_cls)
        col_names = {col.key for col in mapper.columns}
        # Identify datetime columns for ISO string parsing
        dt_cols = {
            col.key
            for col in mapper.columns
            if isinstance(col.type, SADateTime)
        }

        count = 0
        for row_data in rows:
            # Filter to only known columns
            filtered = {k: v for k, v in row_data.items() if k in col_names}
            # Convert ISO datetime strings to Python datetime objects
            for key in dt_cols:
                val = filtered.get(key)
                if isinstance(val, str):
                    filtered[key] = datetime.fromisoformat(val)
            obj = model_cls(**filtered)
            if merge:
                await session.merge(obj)
            else:
                session.add(obj)
            count += 1

        counts[table_name] = count

    await session.commit()
    return counts
