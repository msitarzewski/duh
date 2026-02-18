"""Tests for the duh calibration CLI command."""

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


# ── DB helpers (same pattern as test_cli_export.py) ──────────────────


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


async def _seed_decision_with_outcome(
    factory: Any,
    confidence: float,
    outcome_result: str | None = None,
) -> str:
    """Seed a thread + turn + decision, optionally with an outcome."""
    from duh.memory.repository import MemoryRepository

    async with factory() as session:
        repo = MemoryRepository(session)
        thread = await repo.create_thread("Test question")
        turn = await repo.create_turn(thread.id, 1, "COMMIT")
        decision = await repo.save_decision(
            turn.id, thread.id, "Some decision", confidence
        )
        if outcome_result is not None:
            await repo.save_outcome(decision.id, thread.id, outcome_result)
        await session.commit()
        return thread.id


# ── Tests ────────────────────────────────────────────────────────


class TestCalibrationCLI:
    def test_no_decisions(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        config = _mem_config()

        with (
            patch("duh.cli.app._load_config", return_value=config),
            patch("duh.cli.app._create_db", new_callable=AsyncMock) as mock_db,
        ):
            mock_db.return_value = (factory, engine)
            result = runner.invoke(cli, ["calibration"])

        assert result.exit_code == 0
        assert "No decisions found" in result.output

    def test_with_outcomes(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        config = _mem_config()

        # Seed some decisions with outcomes
        asyncio.run(_seed_decision_with_outcome(factory, 0.9, "success"))
        asyncio.run(_seed_decision_with_outcome(factory, 0.9, "success"))
        asyncio.run(_seed_decision_with_outcome(factory, 0.5, "failure"))

        with (
            patch("duh.cli.app._load_config", return_value=config),
            patch("duh.cli.app._create_db", new_callable=AsyncMock) as mock_db,
        ):
            mock_db.return_value = (factory, engine)
            result = runner.invoke(cli, ["calibration"])

        assert result.exit_code == 0
        assert "Total decisions: 3" in result.output
        assert "With outcomes: 3" in result.output
        assert "ECE:" in result.output
        assert "Calibration:" in result.output

    def test_without_outcomes(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        config = _mem_config()

        # Seed decisions without outcomes
        asyncio.run(_seed_decision_with_outcome(factory, 0.8))
        asyncio.run(_seed_decision_with_outcome(factory, 0.6))

        with (
            patch("duh.cli.app._load_config", return_value=config),
            patch("duh.cli.app._create_db", new_callable=AsyncMock) as mock_db,
        ):
            mock_db.return_value = (factory, engine)
            result = runner.invoke(cli, ["calibration"])

        assert result.exit_code == 0
        assert "Total decisions: 2" in result.output
        assert "With outcomes: 0" in result.output
        assert "Overall accuracy: 0.0%" in result.output

    def test_category_filter(self, runner: CliRunner) -> None:
        factory, engine = _make_db()
        config = _mem_config()

        with (
            patch("duh.cli.app._load_config", return_value=config),
            patch("duh.cli.app._create_db", new_callable=AsyncMock) as mock_db,
        ):
            mock_db.return_value = (factory, engine)
            result = runner.invoke(cli, ["calibration", "--category", "tech"])

        assert result.exit_code == 0
        assert "No decisions found" in result.output
