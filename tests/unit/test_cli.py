"""Tests for the CLI commands: argument parsing, output formatting, errors."""

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


# ── CLI group ────────────────────────────────────────────────────


class TestCliGroup:
    def test_no_command_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli)
        assert result.exit_code == 0
        assert "Multi-model consensus engine" in result.output

    def test_version(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "duh" in result.output
        assert "0.1.0" in result.output

    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "ask" in result.output
        assert "recall" in result.output
        assert "threads" in result.output
        assert "show" in result.output
        assert "models" in result.output
        assert "cost" in result.output


# ── ask command ──────────────────────────────────────────────────


class TestAskCommand:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["ask", "--help"])
        assert result.exit_code == 0
        assert "QUESTION" in result.output
        assert "--rounds" in result.output

    def test_missing_question(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["ask"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_displays_decision(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        mock_run.return_value = (
            "Use SQLite for v0.1.",
            1.0,
            None,
            0.0042,
        )

        result = runner.invoke(cli, ["ask", "What database?"])

        assert result.exit_code == 0
        assert "Use SQLite for v0.1." in result.output
        assert "Confidence: 100%" in result.output
        assert "Cost: $0.0042" in result.output

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_displays_dissent(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        mock_run.return_value = (
            "Use SQLite.",
            0.75,
            "[model-a]: PostgreSQL would be better for scale.",
            0.01,
        )

        result = runner.invoke(cli, ["ask", "What database?"])

        assert result.exit_code == 0
        assert "Confidence: 75%" in result.output
        assert "Dissent" in result.output
        assert "PostgreSQL would be better" in result.output

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_no_dissent_when_none(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        mock_run.return_value = ("Answer.", 1.0, None, 0.0)

        result = runner.invoke(cli, ["ask", "Question?"])

        assert result.exit_code == 0
        assert "Dissent" not in result.output

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_rounds_option(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        mock_config.return_value = config
        mock_run.return_value = ("Answer.", 1.0, None, 0.0)

        result = runner.invoke(cli, ["ask", "--rounds", "5", "Question?"])

        assert result.exit_code == 0
        assert config.general.max_rounds == 5

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_error_handling(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig
        from duh.core.errors import ConsensusError

        mock_config.return_value = DuhConfig()
        mock_run.side_effect = ConsensusError("No models available")

        result = runner.invoke(cli, ["ask", "Question?"])

        assert result.exit_code != 0


# ── recall command ───────────────────────────────────────────────


class TestRecallCommand:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["recall", "--help"])
        assert result.exit_code == 0
        assert "QUERY" in result.output
        assert "--limit" in result.output

    def test_missing_query(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["recall"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output


# ── threads command ──────────────────────────────────────────────


class TestThreadsCommand:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["threads", "--help"])
        assert result.exit_code == 0
        assert "--status" in result.output
        assert "--limit" in result.output

    def test_status_choices(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["threads", "--help"])
        assert "active" in result.output
        assert "complete" in result.output
        assert "failed" in result.output


# ── show command ─────────────────────────────────────────────────


class TestShowCommand:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["show", "--help"])
        assert result.exit_code == 0
        assert "THREAD_ID" in result.output

    def test_missing_thread_id(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["show"])
        assert result.exit_code != 0
        assert "Missing argument" in result.output


# ── models command ───────────────────────────────────────────────


class TestModelsCommand:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["models", "--help"])
        assert result.exit_code == 0


# ── cost command ─────────────────────────────────────────────────


class TestCostCommand:
    def test_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["cost", "--help"])
        assert result.exit_code == 0


# ── Helpers for DB integration tests ─────────────────────────────


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


# ── Integration tests with in-memory DB ─────────────────────────


class TestDbCommands:
    """Integration tests using in-memory SQLite via StaticPool."""

    def test_threads_empty(self, runner: CliRunner) -> None:
        factory, engine = _make_db()

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["threads"])

        assert result.exit_code == 0
        assert "No threads found" in result.output
        asyncio.run(engine.dispose())

    def test_recall_empty(self, runner: CliRunner) -> None:
        factory, engine = _make_db()

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["recall", "anything"])

        assert result.exit_code == 0
        assert "No results" in result.output
        asyncio.run(engine.dispose())

    def test_show_not_found(self, runner: CliRunner) -> None:
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
                cli, ["show", "00000000-0000-0000-0000-000000000000"]
            )

        assert result.exit_code == 0
        assert "Thread not found" in result.output
        asyncio.run(engine.dispose())

    def test_cost_empty_db(self, runner: CliRunner) -> None:
        factory, engine = _make_db()

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["cost"])

        assert result.exit_code == 0
        assert "Total cost: $0.0000" in result.output
        assert "0 input" in result.output
        asyncio.run(engine.dispose())

    def test_threads_with_data(self, runner: CliRunner) -> None:
        """Create a thread in DB then list it."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Best database for CLI tools?")
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
            result = runner.invoke(cli, ["threads"])

        assert result.exit_code == 0
        assert thread_id[:8] in result.output
        assert "Best database" in result.output
        asyncio.run(engine.dispose())

    def test_show_with_data(self, runner: CliRunner) -> None:
        """Create thread + contributions and verify show output."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Best database?")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.add_contribution(
                    turn.id,
                    "mock:proposer",
                    "proposer",
                    "Use PostgreSQL for everything.",
                )
                await repo.add_contribution(
                    turn.id,
                    "mock:challenger-1",
                    "challenger",
                    "SQLite is simpler for CLI tools.",
                )
                await repo.save_decision(
                    turn.id,
                    thread.id,
                    "Use SQLite for v0.1.",
                    0.85,
                    dissent="PostgreSQL for future scale.",
                )
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
            result = runner.invoke(cli, ["show", thread_id])

        assert result.exit_code == 0
        assert "Best database?" in result.output
        assert "Round 1" in result.output
        assert "[PROPOSER] mock:proposer" in result.output
        assert "Use PostgreSQL" in result.output
        assert "[CHALLENGER] mock:challenger-1" in result.output
        assert "SQLite is simpler" in result.output
        assert "Decision (confidence 85%)" in result.output
        assert "Use SQLite for v0.1." in result.output
        assert "Dissent: PostgreSQL for future scale." in result.output
        asyncio.run(engine.dispose())

    def test_show_prefix_match(self, runner: CliRunner) -> None:
        """Show command supports prefix matching."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Prefix test question")
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
            result = runner.invoke(cli, ["show", prefix])

        assert result.exit_code == 0
        assert "Prefix test question" in result.output
        asyncio.run(engine.dispose())

    def test_recall_with_data(self, runner: CliRunner) -> None:
        """Search returns matching threads."""
        factory, engine = _make_db()

        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread(
                    "Best architecture for microservices?"
                )
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(
                    turn.id,
                    thread.id,
                    "Start with a monolith.",
                    0.9,
                )
                await session.commit()

        asyncio.run(_seed())

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["recall", "microservices"])

        assert result.exit_code == 0
        assert "microservices" in result.output
        asyncio.run(engine.dispose())

    def test_cost_with_data(self, runner: CliRunner) -> None:
        """Cost command aggregates from contributions."""
        factory, engine = _make_db()

        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Test cost tracking")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.add_contribution(
                    turn.id,
                    "anthropic:opus",
                    "proposer",
                    "Answer.",
                    input_tokens=1000,
                    output_tokens=500,
                    cost_usd=0.05,
                )
                await repo.add_contribution(
                    turn.id,
                    "openai:gpt-5",
                    "challenger",
                    "Challenge.",
                    input_tokens=800,
                    output_tokens=300,
                    cost_usd=0.03,
                )
                await session.commit()

        asyncio.run(_seed())

        with (
            patch("duh.cli.app.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            result = runner.invoke(cli, ["cost"])

        assert result.exit_code == 0
        assert "Total cost: $0.0800" in result.output
        assert "1,800 input" in result.output
        assert "800 output" in result.output
        assert "By model:" in result.output
        assert "anthropic:opus: $0.0500" in result.output
        assert "openai:gpt-5: $0.0300" in result.output
        asyncio.run(engine.dispose())


# ── Models command with mock provider ────────────────────────────


class TestModelsWithProvider:
    def test_models_lists_providers(self, runner: CliRunner) -> None:
        """Models command lists models from registered providers."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=3.0,
            output_cost=15.0,
        )

        async def fake_setup(cfg: Any) -> ProviderManager:
            pm = ProviderManager()
            await pm.register(provider)
            return pm

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch(
                "duh.cli.app._setup_providers",
                side_effect=fake_setup,
            ),
        ):
            result = runner.invoke(cli, ["models"])

        assert result.exit_code == 0
        assert "mock:" in result.output

    def test_models_no_providers(self, runner: CliRunner) -> None:
        """No configured providers shows guidance."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager

        config = DuhConfig()

        async def empty_setup(cfg: Any) -> ProviderManager:
            return ProviderManager()

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch(
                "duh.cli.app._setup_providers",
                side_effect=empty_setup,
            ),
        ):
            result = runner.invoke(cli, ["models"])

        assert result.exit_code == 0
        assert "No models available" in result.output
        assert "config.toml" in result.output


# ── Ask command integration ──────────────────────────────────────


class TestAskIntegration:
    def test_ask_full_loop(self, runner: CliRunner) -> None:
        """Full ask flow with mock provider."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=3.0,
            output_cost=15.0,
        )

        async def fake_ask(
            question: str, cfg: Any
        ) -> tuple[str, float, str | None, float]:
            pm = ProviderManager()
            await pm.register(provider)
            from duh.cli.app import _run_consensus

            return await _run_consensus(question, cfg, pm)

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch("duh.cli.app._ask_async", side_effect=fake_ask),
        ):
            result = runner.invoke(cli, ["ask", "What database?"])

        assert result.exit_code == 0
        assert "SQLite" in result.output or "repository" in result.output
        assert "Confidence:" in result.output
        assert "Cost:" in result.output
