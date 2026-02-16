"""Tests for decomposition CLI integration.

Tests --decompose flag, display methods, and subtask persistence.
"""

from __future__ import annotations

import asyncio
import io
import json
from typing import Any
from unittest.mock import patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from duh.cli.app import cli
from duh.cli.display import ConsensusDisplay
from duh.consensus.machine import SubtaskSpec
from duh.consensus.scheduler import SubtaskResult
from duh.consensus.synthesis import SynthesisResult

# ── Display helpers ─────────────────────────────────────────────


def _make_display() -> tuple[ConsensusDisplay, io.StringIO]:
    """Create a display with captured output."""
    buf = io.StringIO()
    console = Console(file=buf, width=80, no_color=True)
    display = ConsensusDisplay(console=console)
    return display, buf


def _output(buf: io.StringIO) -> str:
    """Read captured output."""
    return buf.getvalue()


# ── show_decompose ──────────────────────────────────────────────


class TestShowDecompose:
    def test_shows_subtask_labels_and_descriptions(self) -> None:
        display, buf = _make_display()
        specs = [
            SubtaskSpec(
                label="research",
                description="Research options",
                dependencies=[],
            ),
            SubtaskSpec(
                label="compare",
                description="Compare results",
                dependencies=["research"],
            ),
        ]
        display.show_decompose(specs)
        out = _output(buf)
        assert "DECOMPOSE" in out
        assert "2 subtasks" in out
        assert "research" in out
        assert "Research options" in out
        assert "compare" in out
        assert "Compare results" in out

    def test_shows_dependencies(self) -> None:
        display, buf = _make_display()
        specs = [
            SubtaskSpec(label="a", description="First task", dependencies=[]),
            SubtaskSpec(
                label="b",
                description="Second task",
                dependencies=["a"],
            ),
        ]
        display.show_decompose(specs)
        out = _output(buf)
        assert "Dependencies: none" in out
        assert "Dependencies: a" in out

    def test_shows_multiple_dependencies(self) -> None:
        display, buf = _make_display()
        specs = [
            SubtaskSpec(label="a", description="First", dependencies=[]),
            SubtaskSpec(label="b", description="Second", dependencies=[]),
            SubtaskSpec(
                label="c",
                description="Third",
                dependencies=["a", "b"],
            ),
        ]
        display.show_decompose(specs)
        out = _output(buf)
        assert "3 subtasks" in out
        assert "a, b" in out

    def test_subtask_count_in_title(self) -> None:
        display, buf = _make_display()
        specs = [
            SubtaskSpec(
                label=f"task_{i}",
                description=f"Task {i}",
                dependencies=[],
            )
            for i in range(4)
        ]
        display.show_decompose(specs)
        out = _output(buf)
        assert "4 subtasks" in out


# ── show_subtask_progress ───────────────────────────────────────


class TestShowSubtaskProgress:
    def test_shows_label_and_confidence(self) -> None:
        display, buf = _make_display()
        result = SubtaskResult(
            label="research",
            decision="Use SQLite.",
            confidence=0.85,
        )
        display.show_subtask_progress(result)
        out = _output(buf)
        assert "research" in out
        assert "85%" in out

    def test_shows_decision_content(self) -> None:
        display, buf = _make_display()
        result = SubtaskResult(
            label="compare",
            decision="PostgreSQL is better for scale.",
            confidence=0.9,
        )
        display.show_subtask_progress(result)
        out = _output(buf)
        assert "PostgreSQL is better" in out

    def test_truncates_long_decision(self) -> None:
        display, buf = _make_display()
        result = SubtaskResult(label="long", decision="x" * 600, confidence=0.7)
        display.show_subtask_progress(result)
        out = _output(buf)
        assert "..." in out


# ── show_synthesis ──────────────────────────────────────────────


class TestShowSynthesis:
    def test_shows_content_and_strategy(self) -> None:
        display, buf = _make_display()
        result = SynthesisResult(
            content="Combined final answer here.",
            confidence=0.88,
            strategy="merge",
        )
        display.show_synthesis(result)
        out = _output(buf)
        assert "SYNTHESIS" in out
        assert "merge" in out
        assert "Combined final answer here." in out

    def test_shows_aggregate_confidence(self) -> None:
        display, buf = _make_display()
        result = SynthesisResult(
            content="Answer.",
            confidence=0.75,
            strategy="prioritize",
        )
        display.show_synthesis(result)
        out = _output(buf)
        assert "Aggregate confidence: 75%" in out
        assert "prioritize" in out

    def test_content_not_truncated(self) -> None:
        display, buf = _make_display()
        long_content = "x" * 1000
        result = SynthesisResult(
            content=long_content,
            confidence=0.9,
            strategy="merge",
        )
        display.show_synthesis(result)
        out = _output(buf)
        # Synthesis content should NOT be truncated
        assert "..." not in out


# ── Full decomposition display flow ─────────────────────────────


class TestFullDecomposeDisplay:
    def test_complete_decompose_flow(self) -> None:
        """Verify a complete decompose flow renders all phases."""
        display, buf = _make_display()
        display.start()

        specs = [
            SubtaskSpec(
                label="research",
                description="Research databases",
                dependencies=[],
            ),
            SubtaskSpec(
                label="compare",
                description="Compare options",
                dependencies=["research"],
            ),
        ]
        display.show_decompose(specs)

        for spec in specs:
            sr = SubtaskResult(
                label=spec.label,
                decision=f"Result for {spec.label}",
                confidence=0.85,
            )
            display.show_subtask_progress(sr)

        synthesis = SynthesisResult(
            content="Use SQLite for v0.1.",
            confidence=0.85,
            strategy="merge",
        )
        display.show_synthesis(synthesis)
        display.show_final_decision("Use SQLite for v0.1.", 0.85, 0.042, None)

        out = _output(buf)
        assert "DECOMPOSE" in out
        assert "2 subtasks" in out
        assert "research" in out
        assert "compare" in out
        assert "SYNTHESIS" in out
        assert "Decision" in out
        assert "Use SQLite for v0.1." in out


# ── CLI --decompose flag ────────────────────────────────────────


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestAskDecomposeFlag:
    def test_help_shows_decompose_option(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["ask", "--help"])
        assert result.exit_code == 0
        assert "--decompose" in result.output

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_decompose_flag_calls_decompose_async(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        mock_run.return_value = None

        result = runner.invoke(cli, ["ask", "--decompose", "Complex question?"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        coro = mock_run.call_args[0][0]
        assert "decompose" in coro.cr_code.co_qualname
        coro.close()

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_config_decompose_flag_triggers_decompose(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        config.general.decompose = True
        mock_config.return_value = config
        mock_run.return_value = None

        result = runner.invoke(cli, ["ask", "Complex question?"])

        assert result.exit_code == 0
        mock_run.assert_called_once()
        coro = mock_run.call_args[0][0]
        assert "decompose" in coro.cr_code.co_qualname
        coro.close()

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_decompose_error_handling(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig
        from duh.core.errors import ConsensusError

        mock_config.return_value = DuhConfig()
        mock_run.side_effect = ConsensusError("Decomposition failed")

        result = runner.invoke(cli, ["ask", "--decompose", "Question?"])
        assert result.exit_code != 0


# ── Subtask persistence ─────────────────────────────────────────


def _make_db() -> tuple[Any, Any]:
    """Create in-memory SQLite engine + sessionmaker synchronously."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import (
        async_sessionmaker,
        create_async_engine,
    )
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


class TestDecomposePersistence:
    def test_subtasks_persisted_to_db(self) -> None:
        """Verify that subtasks are saved to the database."""
        factory, engine = _make_db()

        subtask_specs = [
            SubtaskSpec(
                label="research",
                description="Research options",
                dependencies=[],
            ),
            SubtaskSpec(
                label="compare",
                description="Compare results",
                dependencies=["research"],
            ),
        ]

        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Complex question?")

                for i, spec in enumerate(subtask_specs):
                    await repo.save_subtask(
                        parent_thread_id=thread.id,
                        label=spec.label,
                        description=spec.description,
                        dependencies=json.dumps(spec.dependencies),
                        sequence_order=i,
                    )
                await session.commit()

        asyncio.run(_seed())

        async def _verify() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                threads = await repo.list_threads()
                assert len(threads) == 1
                assert threads[0].question == "Complex question?"

                subtasks = await repo.get_subtasks(threads[0].id)
                assert len(subtasks) == 2
                assert subtasks[0].label == "research"
                assert subtasks[0].description == "Research options"
                assert json.loads(subtasks[0].dependencies) == []
                assert subtasks[1].label == "compare"
                assert subtasks[1].description == "Compare results"
                deps = json.loads(subtasks[1].dependencies)
                assert deps == ["research"]

        asyncio.run(_verify())
        asyncio.run(engine.dispose())

    def test_subtask_sequence_order(self) -> None:
        """Verify subtasks preserve sequence ordering."""
        factory, engine = _make_db()

        labels = ["alpha", "beta", "gamma"]

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Ordered test")

                for i, label in enumerate(labels):
                    await repo.save_subtask(
                        parent_thread_id=thread.id,
                        label=label,
                        description=f"Task {label}",
                        sequence_order=i,
                    )
                await session.commit()
                return thread.id

        tid = asyncio.run(_seed())

        async def _verify() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                subtasks = await repo.get_subtasks(tid)
                assert len(subtasks) == 3
                for i, label in enumerate(labels):
                    assert subtasks[i].label == label
                    assert subtasks[i].sequence_order == i

        asyncio.run(_verify())
        asyncio.run(engine.dispose())
