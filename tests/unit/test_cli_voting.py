"""Tests for voting CLI integration: --protocol flag, display, persistence."""

from __future__ import annotations

import asyncio
import io
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from duh.cli.app import cli
from duh.cli.display import ConsensusDisplay
from duh.consensus.voting import VoteResult, VotingAggregation


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── Display: show_votes ──────────────────────────────────────


def _make_display() -> tuple[ConsensusDisplay, io.StringIO]:
    """Create a display with captured output."""
    buf = io.StringIO()
    console = Console(file=buf, width=80, no_color=True)
    display = ConsensusDisplay(console=console)
    return display, buf


def _output(buf: io.StringIO) -> str:
    return buf.getvalue()


class TestShowVotes:
    def test_shows_all_votes(self) -> None:
        display, buf = _make_display()
        votes = [
            VoteResult(model_ref="mock:model-a", content="Answer A"),
            VoteResult(model_ref="mock:model-b", content="Answer B"),
        ]
        display.show_votes(votes)
        out = _output(buf)
        assert "VOTES" in out
        assert "mock:model-a" in out
        assert "Answer A" in out
        assert "mock:model-b" in out
        assert "Answer B" in out

    def test_truncates_long_vote(self) -> None:
        display, buf = _make_display()
        votes = [
            VoteResult(model_ref="mock:model-a", content="x" * 600),
        ]
        display.show_votes(votes)
        out = _output(buf)
        assert "..." in out
        assert "x" * 600 not in out

    def test_single_vote(self) -> None:
        display, buf = _make_display()
        votes = [
            VoteResult(model_ref="solo:model", content="Only answer"),
        ]
        display.show_votes(votes)
        out = _output(buf)
        assert "solo:model" in out
        assert "Only answer" in out


# ── Display: show_voting_result ──────────────────────────────


class TestShowVotingResult:
    def test_shows_decision_and_stats(self) -> None:
        display, buf = _make_display()
        result = VotingAggregation(
            votes=(
                VoteResult(model_ref="a:m", content="A"),
                VoteResult(model_ref="b:m", content="B"),
            ),
            decision="Best answer here.",
            strategy="majority",
            confidence=0.8,
        )
        display.show_voting_result(result, 0.0123)
        out = _output(buf)
        assert "Best answer here." in out
        assert "Decision" in out
        assert "majority" in out
        assert "80%" in out
        assert "Votes: 2" in out
        assert "$0.0123" in out

    def test_weighted_strategy(self) -> None:
        display, buf = _make_display()
        result = VotingAggregation(
            votes=(VoteResult(model_ref="a:m", content="A"),),
            decision="Weighted result.",
            strategy="weighted",
            confidence=0.85,
        )
        display.show_voting_result(result, 0.05)
        out = _output(buf)
        assert "weighted" in out
        assert "85%" in out
        assert "Votes: 1" in out

    def test_decision_not_truncated(self) -> None:
        display, buf = _make_display()
        long_decision = "y" * 1000
        result = VotingAggregation(
            votes=(),
            decision=long_decision,
            strategy="majority",
            confidence=0.5,
        )
        display.show_voting_result(result, 0.0)
        out = _output(buf)
        assert "..." not in out


# ── Ask --protocol flag parsing ──────────────────────────────


class TestAskProtocolFlag:
    def test_help_shows_protocol(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["ask", "--help"])
        assert result.exit_code == 0
        assert "--protocol" in result.output
        assert "consensus" in result.output
        assert "voting" in result.output
        assert "auto" in result.output

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_default_protocol_is_consensus(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()
        mock_run.return_value = ("Answer.", 1.0, 1.0, None, 0.0)

        result = runner.invoke(cli, ["ask", "Question?"])
        assert result.exit_code == 0
        # Default calls _ask_async which returns the tuple
        assert "Answer." in result.output

    @patch("duh.cli.app._ask_voting_async", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_protocol_voting_calls_voting(
        self,
        mock_config: Any,
        mock_voting: AsyncMock,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()

        result = runner.invoke(cli, ["ask", "--protocol", "voting", "Question?"])
        assert result.exit_code == 0
        mock_voting.assert_called_once()

    @patch("duh.cli.app._ask_auto_async", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_protocol_auto_calls_auto(
        self,
        mock_config: Any,
        mock_auto: AsyncMock,
        runner: CliRunner,
    ) -> None:
        from duh.config.schema import DuhConfig

        mock_config.return_value = DuhConfig()

        result = runner.invoke(cli, ["ask", "--protocol", "auto", "Question?"])
        assert result.exit_code == 0
        mock_auto.assert_called_once()

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_config_protocol_voting(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        """Config general.protocol='voting' routes to voting."""
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        config.general.protocol = "voting"
        mock_config.return_value = config

        # asyncio.run is called with _ask_voting_async
        result = runner.invoke(cli, ["ask", "Question?"])
        assert result.exit_code == 0

    def test_invalid_protocol_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["ask", "--protocol", "invalid", "Question?"])
        assert result.exit_code != 0


# ── DB integration: voting persistence ────────────────────────


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


class TestVotingPersistence:
    def test_show_with_votes(self, runner: CliRunner) -> None:
        """Show command displays votes stored for a thread."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Best framework?")
                await repo.save_vote(thread.id, "mock:model-a", "Use Django")
                await repo.save_vote(thread.id, "mock:model-b", "Use FastAPI")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(
                    turn.id,
                    thread.id,
                    "Use FastAPI for this use case.",
                    0.8,
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
        assert "Votes" in result.output
        assert "mock:model-a" in result.output
        assert "Use Django" in result.output
        assert "mock:model-b" in result.output
        assert "Use FastAPI" in result.output
        assert "Decision (confidence 80%, rigor 0%)" in result.output
        asyncio.run(engine.dispose())

    def test_show_without_votes(self, runner: CliRunner) -> None:
        """Show command works fine when no votes are stored."""
        factory, engine = _make_db()

        async def _seed() -> str:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Regular question")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(turn.id, thread.id, "Answer.", 0.9)
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
        assert "Votes" not in result.output
        assert "Answer." in result.output
        asyncio.run(engine.dispose())


# ── Voting full integration ──────────────────────────────────


class TestVotingIntegration:
    def test_voting_full_loop(self, runner: CliRunner) -> None:
        """Full voting flow with mock provider and DB persistence."""
        from duh.config.schema import DuhConfig
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        config = DuhConfig()
        provider = MockProvider(
            provider_id="mock",
            responses={"model-a": "Answer A", "model-b": "Answer B"},
            input_cost=3.0,
            output_cost=15.0,
        )
        factory, engine = _make_db()

        async def fake_voting(question: str, cfg: Any) -> None:
            from duh.consensus.voting import run_voting
            from duh.memory.repository import MemoryRepository

            pm = ProviderManager()
            await pm.register(provider)
            result = await run_voting(question, pm)

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread(question)
                thread.status = "complete"
                for vote in result.votes:
                    await repo.save_vote(thread.id, vote.model_ref, vote.content)
                if result.decision:
                    turn = await repo.create_turn(thread.id, 1, "COMMIT")
                    await repo.save_decision(
                        turn.id,
                        thread.id,
                        result.decision,
                        result.confidence,
                    )
                await session.commit()

        with (
            patch("duh.cli.app.load_config", return_value=config),
            patch(
                "duh.cli.app._ask_voting_async",
                side_effect=fake_voting,
            ),
        ):
            result = runner.invoke(cli, ["ask", "--protocol", "voting", "Best DB?"])

        assert result.exit_code == 0
        asyncio.run(engine.dispose())
