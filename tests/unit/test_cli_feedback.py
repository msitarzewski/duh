"""Tests for the duh feedback CLI command."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from duh.cli.app import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── DB helpers (same pattern as test_cli.py) ──────────────────


def _make_db() -> tuple[Any, Any]:
    """Create an in-memory SQLite engine + sessionmaker synchronously."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

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

    asyncio.run(_init_tables(engine))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory, engine


async def _init_tables(engine: Any) -> None:
    from duh.memory.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _mem_config() -> Any:
    from duh.config.schema import DuhConfig

    return DuhConfig(
        database={"url": "sqlite+aiosqlite://"},  # type: ignore[arg-type]
    )


# ── Help & argument tests ────────────────────────────────────


class TestFeedbackHelp:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["feedback", "--help"])
        assert result.exit_code == 0
        assert "THREAD_ID" in result.output
        assert "--result" in result.output
        assert "--notes" in result.output

    def test_missing_thread_id(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["feedback"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_missing_result(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["feedback", "abc12345"])
        assert result.exit_code != 0

    def test_invalid_result_choice(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["feedback", "abc12345", "--result", "invalid"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output


# ── Integration tests with in-memory DB ──────────────────────


class TestFeedbackDb:
    def test_no_thread_found(self, runner: CliRunner) -> None:
        factory, engine = _make_db()

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["feedback", "nonexist", "--result", "success"])

        assert result.exit_code == 0
        assert "No thread matching" in result.output
        asyncio.run(engine.dispose())

    def test_no_decisions(self, runner: CliRunner) -> None:
        """Thread exists but has no decisions."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Test question")
                tid = thread.id
                await session.commit()
            return tid

        thread_id = asyncio.run(_seed())

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(
                cli,
                ["feedback", thread_id, "--result", "success"],
            )

        assert result.exit_code == 0
        assert "No decisions found" in result.output
        asyncio.run(engine.dispose())

    def test_success_outcome(self, runner: CliRunner) -> None:
        """Record a success outcome with notes."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Best database?")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(turn.id, thread.id, "Use SQLite.", 0.9)
                tid = thread.id
                await session.commit()
            return tid

        thread_id = asyncio.run(_seed())

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(
                cli,
                [
                    "feedback",
                    thread_id,
                    "--result",
                    "success",
                    "--notes",
                    "Worked great!",
                ],
            )

        assert result.exit_code == 0
        assert "Outcome recorded: success" in result.output
        asyncio.run(engine.dispose())

    def test_prefix_match(self, runner: CliRunner) -> None:
        """Feedback supports prefix matching."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Prefix test")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(turn.id, thread.id, "Decision.", 0.8)
                tid = thread.id
                await session.commit()
            return tid

        thread_id = asyncio.run(_seed())
        prefix = thread_id[:8]

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(
                cli,
                ["feedback", prefix, "--result", "failure"],
            )

        assert result.exit_code == 0
        assert "Outcome recorded: failure" in result.output
        asyncio.run(engine.dispose())
