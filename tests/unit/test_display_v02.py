"""Tests for v0.2 display methods: taxonomy and outcome rendering."""

from __future__ import annotations

import asyncio
from io import StringIO
from typing import Any
from unittest.mock import AsyncMock, patch

from click.testing import CliRunner
from rich.console import Console

from duh.cli.display import ConsensusDisplay

# ── Display unit tests ────────────────────────────────────────


def _make_display() -> tuple[ConsensusDisplay, StringIO]:
    """Create a display with a captured StringIO console."""
    buf = StringIO()
    console = Console(file=buf, width=80, no_color=True)
    display = ConsensusDisplay(console=console)
    return display, buf


class TestShowTaxonomy:
    def test_renders_all_fields(self) -> None:
        display, buf = _make_display()
        display.show_taxonomy("factual", "database", "relational")
        output = buf.getvalue()
        assert "Intent: factual" in output
        assert "Category: database" in output
        assert "Genus: relational" in output
        assert "Taxonomy" in output

    def test_renders_partial_fields(self) -> None:
        display, buf = _make_display()
        display.show_taxonomy("technical", None, None)
        output = buf.getvalue()
        assert "Intent: technical" in output
        assert "Category" not in output
        assert "Genus" not in output

    def test_no_output_when_all_none(self) -> None:
        display, buf = _make_display()
        display.show_taxonomy(None, None, None)
        output = buf.getvalue()
        assert output.strip() == ""

    def test_no_output_when_all_empty(self) -> None:
        display, buf = _make_display()
        display.show_taxonomy("", "", "")
        output = buf.getvalue()
        assert output.strip() == ""


class TestShowOutcome:
    def test_renders_result(self) -> None:
        display, buf = _make_display()
        display.show_outcome("success", None)
        output = buf.getvalue()
        assert "Result: success" in output
        assert "Outcome" in output
        assert "Notes" not in output

    def test_renders_result_with_notes(self) -> None:
        display, buf = _make_display()
        display.show_outcome("failure", "Needs more testing")
        output = buf.getvalue()
        assert "Result: failure" in output
        assert "Notes: Needs more testing" in output

    def test_partial_result(self) -> None:
        display, buf = _make_display()
        display.show_outcome("partial", "Half done")
        output = buf.getvalue()
        assert "Result: partial" in output
        assert "Notes: Half done" in output


# ── CLI show command taxonomy/outcome integration ─────────────


def _make_db() -> tuple[Any, Any]:
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


class TestShowCommandTaxonomy:
    def test_show_renders_taxonomy(self) -> None:
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("What database?")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(
                    turn.id,
                    thread.id,
                    "Use SQLite.",
                    0.9,
                    intent="technical",
                    category="database",
                    genus="relational",
                )
                tid = thread.id
                await session.commit()
            return tid

        thread_id = asyncio.run(_seed())
        runner = CliRunner()

        from duh.cli.app import cli

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["show", thread_id])

        assert result.exit_code == 0
        assert "Taxonomy:" in result.output
        assert "intent=technical" in result.output
        assert "category=database" in result.output
        assert "genus=relational" in result.output
        asyncio.run(engine.dispose())

    def test_show_renders_outcome(self) -> None:
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Best approach?")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                decision = await repo.save_decision(
                    turn.id, thread.id, "Use monolith.", 0.85
                )
                await repo.save_outcome(
                    decision.id, thread.id, "success", notes="Worked well"
                )
                tid = thread.id
                await session.commit()
            return tid

        thread_id = asyncio.run(_seed())
        runner = CliRunner()

        from duh.cli.app import cli

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["show", thread_id])

        assert result.exit_code == 0
        assert "Outcome: success" in result.output
        assert "Worked well" in result.output
        asyncio.run(engine.dispose())
