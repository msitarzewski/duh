"""Database backup and restore utilities."""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
import time
from contextlib import closing
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


def _sqlite_path(db_url: str) -> Path:
    from sqlalchemy.engine import make_url

    if ":///" not in db_url:
        raise ValueError("Cannot extract a SQLite file path from this URL")
    url = make_url(db_url)
    if url.get_backend_name() != "sqlite":
        raise ValueError("Expected a SQLite database URL")
    if not url.database or url.database == ":memory:":
        raise ValueError("Cannot snapshot or restore an in-memory SQLite database")
    return Path(url.database).expanduser().resolve()


def _sqlite_snapshot(source: Path, dest: Path, *, publish: bool) -> None:
    """Use SQLite's transactional backup API, including committed WAL pages."""
    source = source.resolve(strict=True)
    if source == dest.resolve() or (dest.exists() and source.samefile(dest)):
        raise ValueError("Source and destination must be different databases")
    dest.parent.mkdir(parents=True, exist_ok=True)
    staged: Path | None = None
    try:
        with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as reader:
            if reader.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise ValueError("SQLite source failed integrity verification")
            target = dest
            if publish:
                fd, name = tempfile.mkstemp(prefix=f".{dest.name}.", dir=dest.parent)
                os.close(fd)
                staged = target = Path(name)
            elif not target.exists():
                target.touch(mode=0o600, exist_ok=False)
            deadline = time.monotonic() + 30

            def progress(status: int, remaining: int, total: int) -> None:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        "SQLite snapshot timed out waiting for the database"
                    )

            writer = sqlite3.connect(target)
            try:
                reader.backup(writer, pages=256, progress=progress, sleep=0.05)
            finally:
                writer.close()
        if staged is not None:
            with staged.open("rb") as file:
                os.fsync(file.fileno())
            os.replace(staged, dest)
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


async def backup_sqlite(db_url: str, dest: Path) -> Path:
    """Publish a consistent snapshot without exposing an incomplete backup."""
    await asyncio.to_thread(_sqlite_snapshot, _sqlite_path(db_url), dest, publish=True)
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
        "version": "0.6.0",
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

    SQLite replaces the destination contents transactionally, including when
    existing connections use WAL. Renaming a file over that database would
    leave those connections using the old inode and its WAL.
    """
    await asyncio.to_thread(
        _sqlite_snapshot, source, _sqlite_path(db_url), publish=False
    )


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
        UTCDateTime,
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
            if isinstance(col.type, (SADateTime, UTCDateTime))
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
