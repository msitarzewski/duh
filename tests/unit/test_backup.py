"""Tests for database backup utilities and CLI command."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from duh.cli.app import cli
from duh.memory.backup import backup_json, backup_sqlite, detect_db_type

# ── detect_db_type ──────────────────────────────────────────────


class TestDetectDbType:
    def test_sqlite_plain(self) -> None:
        assert detect_db_type("sqlite:///path/to/db.sqlite") == "sqlite"

    def test_sqlite_aiosqlite(self) -> None:
        assert detect_db_type("sqlite+aiosqlite:///path/to/db.db") == "sqlite"

    def test_sqlite_memory(self) -> None:
        assert detect_db_type("sqlite+aiosqlite://") == "sqlite"

    def test_postgresql_plain(self) -> None:
        assert detect_db_type("postgresql://user:pass@host/db") == "postgresql"

    def test_postgresql_asyncpg(self) -> None:
        assert detect_db_type("postgresql+asyncpg://user:pass@host/db") == "postgresql"

    def test_postgres_shorthand(self) -> None:
        assert detect_db_type("postgres://user:pass@host/db") == "postgresql"

    def test_unknown_url(self) -> None:
        assert detect_db_type("mysql://user:pass@host/db") == "unknown"


# ── backup_sqlite ───────────────────────────────────────────────


class TestBackupSqlite:
    def test_copies_file(self, tmp_path: Path) -> None:
        """Create a temp SQLite DB, backup, verify copy exists and is valid."""
        src_db = tmp_path / "source.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO test VALUES (1, 'hello')")
        conn.commit()
        conn.close()

        dest = tmp_path / "backup" / "backup.db"
        db_url = f"sqlite:///{src_db}"

        result = asyncio.run(backup_sqlite(db_url, dest))

        assert result == dest
        assert dest.exists()
        # Verify the copy is a valid SQLite database
        conn2 = sqlite3.connect(str(dest))
        rows = conn2.execute("SELECT * FROM test").fetchall()
        conn2.close()
        assert rows == [(1, "hello")]

    def test_memory_db_raises(self, tmp_path: Path) -> None:
        dest = tmp_path / "backup.db"
        with pytest.raises(ValueError, match="Cannot"):
            asyncio.run(backup_sqlite("sqlite+aiosqlite://", dest))

    def test_memory_db_triple_slash_raises(self, tmp_path: Path) -> None:
        dest = tmp_path / "backup.db"
        with pytest.raises(ValueError, match="in-memory"):
            asyncio.run(backup_sqlite("sqlite+aiosqlite:///:memory:", dest))

    def test_missing_source_raises(self, tmp_path: Path) -> None:
        dest = tmp_path / "backup.db"
        with pytest.raises(FileNotFoundError):
            asyncio.run(
                backup_sqlite("sqlite:///nonexistent/path/db.sqlite", dest)
            )

    def test_aiosqlite_url(self, tmp_path: Path) -> None:
        """Works with sqlite+aiosqlite:/// prefix too."""
        src_db = tmp_path / "source.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE t (x INTEGER)")
        conn.commit()
        conn.close()

        dest = tmp_path / "copy.db"
        db_url = f"sqlite+aiosqlite:///{src_db}"

        result = asyncio.run(backup_sqlite(db_url, dest))
        assert result == dest
        assert dest.exists()


# ── backup_json ─────────────────────────────────────────────────


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


class TestBackupJson:
    def test_exports_all_tables(self, tmp_path: Path) -> None:
        """Export to JSON and verify structure includes all expected tables."""
        factory, engine = _make_async_session()

        async def _run() -> Path:
            async with factory() as session:
                return await backup_json(session, tmp_path / "backup.json")

        result = asyncio.run(_run())
        assert result.exists()

        data = json.loads(result.read_text())
        expected_tables = {
            "threads",
            "turns",
            "contributions",
            "turn_summaries",
            "thread_summaries",
            "decisions",
            "outcomes",
            "subtasks",
            "votes",
            "api_keys",
        }
        assert expected_tables.issubset(set(data["tables"].keys()))
        asyncio.run(engine.dispose())

    def test_version_field(self, tmp_path: Path) -> None:
        """Verify version and exported_at in output."""
        factory, engine = _make_async_session()

        async def _run() -> Path:
            async with factory() as session:
                return await backup_json(session, tmp_path / "backup.json")

        result = asyncio.run(_run())
        data = json.loads(result.read_text())

        assert data["version"] == "0.5.0"
        assert "exported_at" in data
        # Verify exported_at is a valid ISO timestamp
        assert "T" in data["exported_at"]
        asyncio.run(engine.dispose())

    def test_includes_data(self, tmp_path: Path) -> None:
        """Create data in DB, export to JSON, verify rows present."""
        factory, engine = _make_async_session()

        async def _seed_and_export() -> Path:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Test question")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.add_contribution(
                    turn.id, "mock:model", "proposer", "Answer"
                )
                await repo.save_decision(
                    turn.id, thread.id, "Decision text", 0.9
                )
                await session.commit()

            async with factory() as session:
                return await backup_json(session, tmp_path / "backup.json")

        result = asyncio.run(_seed_and_export())
        data = json.loads(result.read_text())

        assert len(data["tables"]["threads"]) == 1
        assert data["tables"]["threads"][0]["question"] == "Test question"
        assert len(data["tables"]["turns"]) == 1
        assert len(data["tables"]["contributions"]) == 1
        assert len(data["tables"]["decisions"]) == 1
        asyncio.run(engine.dispose())

    def test_empty_db(self, tmp_path: Path) -> None:
        """Backup works on empty database — all tables present but empty."""
        factory, engine = _make_async_session()

        async def _run() -> Path:
            async with factory() as session:
                return await backup_json(session, tmp_path / "backup.json")

        result = asyncio.run(_run())
        data = json.loads(result.read_text())

        for table_name, rows in data["tables"].items():
            assert isinstance(rows, list), f"Table {table_name} should be a list"
            assert len(rows) == 0, f"Table {table_name} should be empty"

        asyncio.run(engine.dispose())


# ── CLI command ─────────────────────────────────────────────────


class TestBackupCli:
    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["backup", "--help"])
        assert result.exit_code == 0
        assert "PATH" in result.output
        assert "--format" in result.output

    def test_backup_json_via_cli(self, runner: CliRunner, tmp_path: Path) -> None:
        """Use CliRunner to test the CLI command with a temp DB."""
        factory, engine = _make_async_session()
        from duh.config.schema import DatabaseConfig, DuhConfig

        config = DuhConfig(
            database=DatabaseConfig(url="sqlite+aiosqlite://"),
        )

        dest = tmp_path / "cli_backup.json"

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["backup", "--format", "json", str(dest)])

        assert result.exit_code == 0, result.output
        assert "Backup saved to" in result.output
        assert dest.exists()

        data = json.loads(dest.read_text())
        assert data["version"] == "0.5.0"
        asyncio.run(engine.dispose())

    def test_backup_format_auto_sqlite(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Auto format uses sqlite copy for sqlite DB."""
        src_db = tmp_path / "source.db"
        conn = sqlite3.connect(str(src_db))
        conn.execute("CREATE TABLE t (id INTEGER)")
        conn.commit()
        conn.close()

        from duh.config.schema import DatabaseConfig, DuhConfig

        config = DuhConfig(
            database=DatabaseConfig(url=f"sqlite+aiosqlite:///{src_db}"),
        )

        dest = tmp_path / "auto_backup.db"

        with patch("duh.cli.app.load_config", return_value=config):
            result = runner.invoke(cli, ["backup", str(dest)])

        assert result.exit_code == 0, result.output
        assert "Backup saved to" in result.output
        assert dest.exists()

    def test_backup_sqlite_format_pg_errors(
        self, runner: CliRunner, tmp_path: Path
    ) -> None:
        """Cannot use sqlite backup format for a PostgreSQL database."""
        from duh.config.schema import DatabaseConfig, DuhConfig

        config = DuhConfig(
            database=DatabaseConfig(url="postgresql+asyncpg://user:pass@host/db"),
        )

        dest = tmp_path / "backup.db"

        with patch("duh.cli.app.load_config", return_value=config):
            result = runner.invoke(cli, ["backup", "--format", "sqlite", str(dest)])

        assert result.exit_code != 0
