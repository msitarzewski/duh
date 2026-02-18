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

    def test_help_shows_new_options(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export", "--help"])
        assert result.exit_code == 0
        assert "--content" in result.output
        assert "--no-dissent" in result.output
        assert "--output" in result.output

    def test_missing_thread_id(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    def test_format_choices(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export", "--help"])
        assert "json" in result.output
        assert "markdown" in result.output
        assert "pdf" in result.output


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

        # Contributions (order not guaranteed by DB)
        assert len(turn["contributions"]) == 2
        by_role = {c["role"]: c for c in turn["contributions"]}
        proposer = by_role["proposer"]
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

        # Votes (order not guaranteed by DB)
        assert len(data["votes"]) == 2
        votes_by_model = {v["model_ref"]: v for v in data["votes"]}
        assert votes_by_model["anthropic:claude-opus-4-6"]["content"] == "SQLite"

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
    def test_markdown_full_report(self, runner: CliRunner) -> None:
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

        # Header - new format
        assert "# Consensus: Best database for CLI tools?" in output

        # Decision section appears first
        assert "## Decision" in output
        assert "Use SQLite for v0.1." in output
        assert "Confidence: 85%" in output

        # Dissent
        assert "## Dissent" in output
        assert "PostgreSQL for future scale." in output

        # Consensus process section
        assert "## Consensus Process" in output
        assert "### Round 1" in output

        # Contributions organized by role
        assert "#### Proposal (anthropic:claude-opus-4-6)" in output
        assert "Use PostgreSQL for everything." in output
        assert "#### Challenges" in output
        assert "**openai:gpt-5.2**: SQLite is simpler for CLI tools." in output

        # Votes under process
        assert "### Votes" in output
        assert "**anthropic:claude-opus-4-6**: SQLite" in output

        # Footer with cost
        assert "duh v" in output
        assert "Cost: $" in output

        asyncio.run(engine.dispose())

    def test_markdown_decision_first(self, runner: CliRunner) -> None:
        """Decision section appears before Consensus Process."""
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

        output = result.output
        decision_pos = output.index("## Decision")
        process_pos = output.index("## Consensus Process")
        assert decision_pos < process_pos

        asyncio.run(engine.dispose())

    def test_markdown_content_decision_only(self, runner: CliRunner) -> None:
        """--content decision produces decision-only markdown."""
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
            result = runner.invoke(
                cli,
                ["export", thread_id, "--format", "markdown", "--content", "decision"],
            )

        assert result.exit_code == 0
        output = result.output

        # Has decision
        assert "## Decision" in output
        assert "Use SQLite for v0.1." in output

        # No process section
        assert "## Consensus Process" not in output
        assert "### Round" not in output
        assert "#### Proposal" not in output

        asyncio.run(engine.dispose())

    def test_markdown_no_dissent(self, runner: CliRunner) -> None:
        """--no-dissent suppresses dissent section."""
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
            result = runner.invoke(
                cli,
                [
                    "export",
                    thread_id,
                    "--format",
                    "markdown",
                    "--no-dissent",
                ],
            )

        assert result.exit_code == 0
        output = result.output

        assert "## Decision" in output
        assert "## Dissent" not in output
        assert "PostgreSQL for future scale." not in output

        asyncio.run(engine.dispose())

    def test_markdown_output_to_file(self, runner: CliRunner, tmp_path: Any) -> None:
        """--output writes to file instead of stdout."""
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)
        out_file = str(tmp_path / "export.md")

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
                    "export",
                    thread_id,
                    "--format",
                    "markdown",
                    "-o",
                    out_file,
                ],
            )

        assert result.exit_code == 0
        assert "Exported to" in result.output

        from pathlib import Path

        content = Path(out_file).read_text()
        assert "# Consensus:" in content
        assert "## Decision" in content

        asyncio.run(engine.dispose())


# ── PDF export tests ─────────────────────────────────────────


class TestExportPdf:
    def test_pdf_requires_output(self, runner: CliRunner) -> None:
        """PDF format requires --output flag."""
        result = runner.invoke(cli, ["export", "abc12345", "--format", "pdf"])
        assert result.exit_code != 0
        assert "--output" in result.output or "required" in result.output.lower()

    def test_pdf_produces_valid_file(self, runner: CliRunner, tmp_path: Any) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)
        out_file = str(tmp_path / "out.pdf")

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
                ["export", thread_id, "--format", "pdf", "-o", out_file],
            )

        assert result.exit_code == 0
        assert "PDF exported to" in result.output

        from pathlib import Path

        pdf_bytes = Path(out_file).read_bytes()
        # Valid PDF starts with %PDF
        assert pdf_bytes[:4] == b"%PDF"

        asyncio.run(engine.dispose())

    def test_pdf_decision_only(self, runner: CliRunner, tmp_path: Any) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)
        out_file = str(tmp_path / "decision.pdf")

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
                    "export",
                    thread_id,
                    "--format",
                    "pdf",
                    "--content",
                    "decision",
                    "-o",
                    out_file,
                ],
            )

        assert result.exit_code == 0

        from pathlib import Path

        pdf_bytes = Path(out_file).read_bytes()
        assert pdf_bytes[:4] == b"%PDF"
        # Decision-only PDF should be smaller than full
        assert len(pdf_bytes) > 0

        asyncio.run(engine.dispose())

    def test_pdf_no_dissent(self, runner: CliRunner, tmp_path: Any) -> None:
        factory, engine = _make_db()
        thread_id = _seed_thread_with_data(factory)
        out_file = str(tmp_path / "no_dissent.pdf")

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
                    "export",
                    thread_id,
                    "--format",
                    "pdf",
                    "--no-dissent",
                    "-o",
                    out_file,
                ],
            )

        assert result.exit_code == 0

        from pathlib import Path

        pdf_bytes = Path(out_file).read_bytes()
        assert pdf_bytes[:4] == b"%PDF"

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

    def test_all_format_options_accepted(
        self, runner: CliRunner, tmp_path: Any
    ) -> None:
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

        # PDF format
        factory3, engine3 = _make_db()
        thread_id3 = _seed_thread_with_data(factory3)
        out_file = str(tmp_path / "test.pdf")

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory3, engine3),
            ),
        ):
            pdf_result = runner.invoke(
                cli, ["export", thread_id3, "--format", "pdf", "-o", out_file]
            )

        assert pdf_result.exit_code == 0

    def test_invalid_format_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["export", "abc12345", "--format", "csv"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output
