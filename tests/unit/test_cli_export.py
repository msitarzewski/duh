"""Tests for the duh export CLI command."""

from __future__ import annotations

import asyncio
import json
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


# ── Seed helper ──────────────────────────────────────────────


def _seed_thread_with_data(factory: Any) -> str:
    """Create a thread with turns, contributions, decisions, and votes."""

    async def _seed() -> str:
        from duh.memory.repository import MemoryRepository

        async with factory() as session:
            repo = MemoryRepository(session)
            thread = await repo.create_thread("Best database for CLI tools?")
            turn = await repo.create_turn(thread.id, 1, "COMMIT")
            await repo.add_contribution(
                turn.id,
                "anthropic:claude-opus-4-6",
                "proposer",
                "Use PostgreSQL for everything.",
                input_tokens=100,
                output_tokens=50,
                cost_usd=0.001,
            )
            await repo.add_contribution(
                turn.id,
                "openai:gpt-5.2",
                "challenger",
                "SQLite is simpler for CLI tools.",
                input_tokens=80,
                output_tokens=40,
                cost_usd=0.0008,
            )
            await repo.save_decision(
                turn.id,
                thread.id,
                "Use SQLite for v0.1.",
                0.85,
                dissent="PostgreSQL for future scale.",
            )
            await repo.save_vote(thread.id, "anthropic:claude-opus-4-6", "SQLite")
            await repo.save_vote(thread.id, "openai:gpt-5.2", "SQLite")
            tid = thread.id
            await session.commit()
        return tid

    return asyncio.run(_seed())


# ── Help & argument tests ────────────────────────────────────


class TestExportHelp:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        assert "THREAD_ID" in result.output
        assert "--format" in result.output

    def test_missing_thread_id(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_format_choices(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export", "--help"])
        assert "json" in result.output
        assert "markdown" in result.output


# ── JSON export tests ────────────────────────────────────────


class TestExportJson:
    def test_json_produces_valid_json(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["export", thread_id])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, dict)
        asyncio.run(engine.dispose())

    def test_json_has_expected_structure(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["export", thread_id])

        assert result.exit_code == 0
        data = json.loads(result.output)

        # Top-level fields
        assert data["thread_id"] == thread_id
        assert data["question"] == "Best database for CLI tools?"
        assert data["status"] == "active"
        assert "created_at" in data
        assert "exported_at" in data

        # Turns
        assert len(data["turns"]) == 1
        turn = data["turns"][0]
        assert turn["round_number"] == 1
        assert turn["state"] == "COMMIT"

        # Contributions
        assert len(turn["contributions"]) == 2
        proposer = turn["contributions"][0]
        assert proposer["model_ref"] == "anthropic:claude-opus-4-6"
        assert proposer["role"] == "proposer"
        assert proposer["content"] == "Use PostgreSQL for everything."
        assert proposer["input_tokens"] == 100
        assert proposer["output_tokens"] == 50
        assert proposer["cost_usd"] == 0.001

        # Decision
        assert turn["decision"] is not None
        assert turn["decision"]["content"] == "Use SQLite for v0.1."
        assert turn["decision"]["confidence"] == 0.85
        assert turn["decision"]["dissent"] == "PostgreSQL for future scale."

        # Votes
        assert len(data["votes"]) == 2
        assert data["votes"][0]["model_ref"] == "anthropic:claude-opus-4-6"
        assert data["votes"][0]["content"] == "SQLite"

        asyncio.run(engine.dispose())

    def test_json_default_format(self, runner: CliRunner) -> None:
        """Default format (no --format flag) is JSON."""
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["export", thread_id])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "thread_id" in data
        asyncio.run(engine.dispose())

    def test_json_explicit_format(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["export", thread_id, "--format", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "thread_id" in data
        asyncio.run(engine.dispose())


# ── Markdown export tests ────────────────────────────────────


class TestExportMarkdown:
    def test_markdown_has_heading_and_content(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["export", thread_id, "--format", "markdown"])

        assert result.exit_code == 0
        output = result.output

        # Header
        assert "# Thread: Best database for CLI tools?" in output
        assert "**Status**: active" in output

        # Round
        assert "## Round 1" in output

        # Contributions
        assert "### Proposer (anthropic:claude-opus-4-6)" in output
        assert "Use PostgreSQL for everything." in output
        assert "### Challenger (openai:gpt-5.2)" in output
        assert "SQLite is simpler for CLI tools." in output

        # Decision
        assert "### Decision" in output
        assert "**Confidence**: 85%" in output
        assert "**Dissent**: PostgreSQL for future scale." in output
        assert "Use SQLite for v0.1." in output

        # Votes
        assert "## Votes" in output
        assert "**anthropic:claude-opus-4-6**: SQLite" in output

        # Footer
        assert "Exported from duh v" in output

        asyncio.run(engine.dispose())


# ── Error & edge case tests ──────────────────────────────────


class TestExportErrors:
    def test_missing_thread(self, runner: CliRunner) -> None:
        factory, engine = _make_db()

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
                ["export", "00000000-0000-0000-0000-000000000000"],
            )

        assert result.exit_code == 0
        assert "Thread not found" in result.output
        asyncio.run(engine.dispose())

    def test_no_thread_matching_prefix(self, runner: CliRunner) -> None:
        factory, engine = _make_db()

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["export", "nonexist"])

        assert result.exit_code == 0
        assert "No thread matching" in result.output
        asyncio.run(engine.dispose())

    def test_prefix_matching_works(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)
        prefix = thread_id[:8]

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["export", prefix])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["thread_id"] == thread_id
        asyncio.run(engine.dispose())

    def test_both_format_options_accepted(self, runner: CliRunner) -> None:
        # JSON format
        factory1, engine1 = _make_db()
        thread_id = _seed_thread_with_data(factory1)

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory1, engine1),
            ),
        ):
            json_result = runner.invoke(cli, ["export", thread_id, "--format", "json"])

        assert json_result.exit_code == 0

        # Markdown format
        factory2, engine2 = _make_db()
        thread_id2 = _seed_thread_with_data(factory2)

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory2, engine2),
            ),
        ):
            md_result = runner.invoke(
                cli, ["export", thread_id2, "--format", "markdown"]
            )

        assert md_result.exit_code == 0

    def test_invalid_format_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export", "abc12345", "--format", "csv"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output
