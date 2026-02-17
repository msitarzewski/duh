"""Tests for database restore utilities and CLI command."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from duh.cli.app import cli
from duh.memory.backup import detect_backup_format, restore_json, restore_sqlite

if TYPE_CHECKING:
    from pathlib import Path


# ── helpers ────────────────────────────────────────────────────


def _make_async_session() -> tuple[Any, Any]:
    """Create an in-memory SQLite async session with tables created."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from duh.memory.models import Base

    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async def _init() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_init())
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory, engine


def _make_json_backup(
    tmp_path: Path,
    tables: dict[str, list[dict[str, Any]]] | None = None,
    *,
    version: str = "0.5.0",
    filename: str = "backup.json",
) -> Path:
    """Create a JSON backup file for testing."""
    data = {
        "version": version,
        "exported_at": "2026-01-01T00:00:00+00:00",
        "tables": tables or {},
    }
    dest = tmp_path / filename
    dest.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return dest


# ── detect_backup_format ───────────────────────────────────────


class TestDetectBackupFormat:
    def test_json_file(self, tmp_path: Path) -> None:
        f = tmp_path / "backup.json"
        f.write_text('{"version": "0.5.0", "tables": {}}')
        assert detect_backup_format(f) == "json"

    def test_json_array(self, tmp_path: Path) -> None:
        f = tmp_path / "backup.json"
        f.write_text("[1, 2, 3]")
        assert detect_backup_format(f) == "json"

    def test_sqlite_file(self, tmp_path: Path) -> None:
        f = tmp_path / "backup.db"
        conn = sqlite3.connect(str(f))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()
        assert detect_backup_format(f) == "sqlite"

    def test_invalid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "backup.bin"
        f.write_bytes(b"\x00\x01\x02\x03random binary")
        with pytest.raises(ValueError, match="Cannot detect"):
            detect_backup_format(f)

    def test_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.dat"
        f.write_bytes(b"")
        with pytest.raises(ValueError, match="empty"):
            detect_backup_format(f)


# ── restore_json ───────────────────────────────────────────────


class TestRestoreJson:
    def test_restore_empty(self, tmp_path: Path) -> None:
        """Restore from a backup of an empty DB works."""
        factory, engine = _make_async_session()
        backup_file = _make_json_backup(tmp_path, tables={
            "threads": [],
            "turns": [],
            "contributions": [],
            "decisions": [],
        })

        async def _run() -> dict[str, int]:
            async with factory() as session:
                return await restore_json(session, backup_file)

        counts = asyncio.run(_run())
        assert counts["threads"] == 0
        assert counts["decisions"] == 0
        asyncio.run(engine.dispose())

    def test_restore_with_data(self, tmp_path: Path) -> None:
        """Restore from backup with threads/decisions, verify data present."""
        import uuid

        factory, engine = _make_async_session()

        thread_id = str(uuid.uuid4())
        turn_id = str(uuid.uuid4())
        decision_id = str(uuid.uuid4())

        backup_file = _make_json_backup(tmp_path, tables={
            "users": [],
            "threads": [{
                "id": thread_id,
                "question": "Test question?",
                "status": "complete",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }],
            "turns": [{
                "id": turn_id,
                "thread_id": thread_id,
                "round_number": 1,
                "state": "COMMIT",
                "created_at": "2026-01-01T00:00:00+00:00",
            }],
            "contributions": [],
            "turn_summaries": [],
            "thread_summaries": [],
            "decisions": [{
                "id": decision_id,
                "turn_id": turn_id,
                "thread_id": thread_id,
                "content": "The answer is 42",
                "confidence": 0.95,
                "created_at": "2026-01-01T00:00:00+00:00",
            }],
            "outcomes": [],
            "subtasks": [],
            "votes": [],
            "api_keys": [],
        })

        async def _run() -> dict[str, int]:
            async with factory() as session:
                return await restore_json(session, backup_file)

        counts = asyncio.run(_run())
        assert counts["threads"] == 1
        assert counts["decisions"] == 1

        # Verify data is actually in the DB
        async def _verify() -> None:
            from sqlalchemy import select

            from duh.memory.models import Decision, Thread

            async with factory() as session:
                result = await session.execute(select(Thread))
                threads = result.scalars().all()
                assert len(threads) == 1
                assert threads[0].question == "Test question?"

                result = await session.execute(select(Decision))
                decisions = result.scalars().all()
                assert len(decisions) == 1
                assert decisions[0].content == "The answer is 42"

        asyncio.run(_verify())
        asyncio.run(engine.dispose())

    def test_restore_clears_existing(self, tmp_path: Path) -> None:
        """Non-merge mode clears existing data first."""
        import uuid

        factory, engine = _make_async_session()

        # Seed existing data
        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                await repo.create_thread("Old question")
                await session.commit()

        asyncio.run(_seed())

        # Restore with new data (non-merge)
        thread_id = str(uuid.uuid4())
        backup_file = _make_json_backup(tmp_path, tables={
            "users": [],
            "threads": [{
                "id": thread_id,
                "question": "New question",
                "status": "active",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }],
            "turns": [],
            "contributions": [],
            "turn_summaries": [],
            "thread_summaries": [],
            "decisions": [],
            "outcomes": [],
            "subtasks": [],
            "votes": [],
            "api_keys": [],
        })

        async def _restore() -> dict[str, int]:
            async with factory() as session:
                return await restore_json(session, backup_file)

        counts = asyncio.run(_restore())
        assert counts["threads"] == 1

        # Verify only the new data exists
        async def _verify() -> None:
            from sqlalchemy import select

            from duh.memory.models import Thread

            async with factory() as session:
                result = await session.execute(select(Thread))
                threads = result.scalars().all()
                assert len(threads) == 1
                assert threads[0].question == "New question"

        asyncio.run(_verify())
        asyncio.run(engine.dispose())

    def test_restore_merge_mode(self, tmp_path: Path) -> None:
        """Merge mode keeps existing data and adds new."""
        import uuid

        factory, engine = _make_async_session()

        # Seed existing data
        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                await repo.create_thread("Existing question")
                await session.commit()

        asyncio.run(_seed())

        # Restore with additional data (merge mode)
        new_thread_id = str(uuid.uuid4())
        backup_file = _make_json_backup(tmp_path, tables={
            "users": [],
            "threads": [{
                "id": new_thread_id,
                "question": "New merged question",
                "status": "active",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }],
            "turns": [],
            "contributions": [],
            "turn_summaries": [],
            "thread_summaries": [],
            "decisions": [],
            "outcomes": [],
            "subtasks": [],
            "votes": [],
            "api_keys": [],
        })

        async def _restore() -> dict[str, int]:
            async with factory() as session:
                return await restore_json(session, backup_file, merge=True)

        counts = asyncio.run(_restore())
        assert counts["threads"] == 1  # 1 new record processed

        # Verify both old and new data exist
        async def _verify() -> None:
            from sqlalchemy import select

            from duh.memory.models import Thread

            async with factory() as session:
                result = await session.execute(select(Thread))
                threads = result.scalars().all()
                assert len(threads) == 2
                questions = {t.question for t in threads}
                assert "Existing question" in questions
                assert "New merged question" in questions

        asyncio.run(_verify())
        asyncio.run(engine.dispose())

    def test_restore_validates_structure(self, tmp_path: Path) -> None:
        """Missing 'tables' key raises ValueError."""
        bad_backup = tmp_path / "bad.json"
        bad_backup.write_text(json.dumps({"version": "0.5.0"}), encoding="utf-8")

        factory, engine = _make_async_session()

        async def _run() -> dict[str, int]:
            async with factory() as session:
                return await restore_json(session, bad_backup)

        with pytest.raises(ValueError, match="missing 'tables'"):
            asyncio.run(_run())

        asyncio.run(engine.dispose())


# ── restore_sqlite ─────────────────────────────────────────────


class TestRestoreSqlite:
    def test_copies_file(self, tmp_path: Path) -> None:
        """SQLite restore replaces the DB file."""
        # Create a backup SQLite file
        backup_db = tmp_path / "backup.db"
        conn = sqlite3.connect(str(backup_db))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'restored')")
        conn.commit()
        conn.close()

        # Create target DB path
        target_db = tmp_path / "target" / "duh.db"
        target_db.parent.mkdir(parents=True, exist_ok=True)
        # Create an empty target
        conn2 = sqlite3.connect(str(target_db))
        conn2.execute("CREATE TABLE empty (id INTEGER)")
        conn2.commit()
        conn2.close()

        db_url = f"sqlite:///{target_db}"
        asyncio.run(restore_sqlite(backup_db, db_url))

        # Verify the restored data
        conn3 = sqlite3.connect(str(target_db))
        rows = conn3.execute("SELECT * FROM test").fetchall()
        conn3.close()
        assert rows == [(1, "restored")]

    def test_memory_db_raises(self, tmp_path: Path) -> None:
        backup_db = tmp_path / "backup.db"
        backup_db.write_bytes(b"")
        with pytest.raises(ValueError, match="in-memory"):
            asyncio.run(restore_sqlite(backup_db, "sqlite+aiosqlite:///:memory:"))

    def test_no_triple_slash_raises(self, tmp_path: Path) -> None:
        backup_db = tmp_path / "backup.db"
        backup_db.write_bytes(b"")
        with pytest.raises(ValueError, match="Cannot extract"):
            asyncio.run(restore_sqlite(backup_db, "sqlite://badurl"))


# ── CLI command ────────────────────────────────────────────────


class TestRestoreCli:
    @pytest.fixture()
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["restore", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output
        assert "--merge" in result.output

    def test_restore_json_via_cli(self, runner: CliRunner, tmp_path: Path) -> None:
        """Use CliRunner to test the restore command with JSON backup."""
        factory, engine = _make_async_session()
        from duh.config.schema import DatabaseConfig, DuhConfig

        config = DuhConfig(
            database=DatabaseConfig(url="sqlite+aiosqlite://"),
        )

        backup_file = _make_json_backup(tmp_path, tables={
            "threads": [],
            "turns": [],
            "contributions": [],
            "turn_summaries": [],
            "thread_summaries": [],
            "decisions": [],
            "outcomes": [],
            "subtasks": [],
            "votes": [],
            "api_keys": [],
        })

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["restore", str(backup_file)])

        assert result.exit_code == 0, result.output
        assert "Restored" in result.output
        asyncio.run(engine.dispose())

    def test_restore_sqlite_pg_errors(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Cannot restore a SQLite backup into a PostgreSQL database."""
        from duh.config.schema import DatabaseConfig, DuhConfig

        config = DuhConfig(
            database=DatabaseConfig(url="postgresql+asyncpg://user:pass@host/db"),
        )

        backup_db = tmp_path / "backup.db"
        conn = sqlite3.connect(str(backup_db))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        with patch("duh.cli.app.load_config", return_value=config):
            result = runner.invoke(cli, ["restore", str(backup_db)])

        assert result.exit_code != 0
