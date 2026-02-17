"""Tests for the MCP server tools."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from duh.cli.app import cli
from duh.memory.models import Base

# ── Helpers ──────────────────────────────────────────────────────


async def _make_db_async() -> tuple[Any, Any]:
    """Create an in-memory SQLite engine + sessionmaker (async-safe)."""
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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory, engine


def _mem_config() -> Any:
    from duh.config.schema import DuhConfig

    return DuhConfig(
        database={"url": "sqlite+aiosqlite://"},  # type: ignore[arg-type]
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── Tool schemas ─────────────────────────────────────────────────


class TestToolSchemas:
    """Verify that tool definitions are correct."""

    def test_get_tools_returns_three(self) -> None:
        from duh.mcp.server import _get_tools

        tools = _get_tools()
        assert len(tools) == 3

    def test_tool_names(self) -> None:
        from duh.mcp.server import _get_tools

        tools = _get_tools()
        names = {t.name for t in tools}
        assert names == {"duh_ask", "duh_recall", "duh_threads"}

    def test_duh_ask_schema(self) -> None:
        from duh.mcp.server import _get_tools

        tools = _get_tools()
        ask = next(t for t in tools if t.name == "duh_ask")
        assert ask.description is not None
        assert "consensus" in ask.description.lower()
        schema = ask.inputSchema
        assert schema["required"] == ["question"]
        assert "question" in schema["properties"]
        assert "protocol" in schema["properties"]
        assert "rounds" in schema["properties"]

    def test_duh_recall_schema(self) -> None:
        from duh.mcp.server import _get_tools

        tools = _get_tools()
        recall = next(t for t in tools if t.name == "duh_recall")
        assert recall.description is not None
        assert "search" in recall.description.lower()
        schema = recall.inputSchema
        assert schema["required"] == ["query"]
        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]

    def test_duh_threads_schema(self) -> None:
        from duh.mcp.server import _get_tools

        tools = _get_tools()
        threads = next(t for t in tools if t.name == "duh_threads")
        assert threads.description is not None
        assert "thread" in threads.description.lower()
        schema = threads.inputSchema
        assert "status" in schema["properties"]
        assert "limit" in schema["properties"]


# ── call_tool routing ────────────────────────────────────────────


class TestCallToolRouting:
    """Verify call_tool routes to correct handlers."""

    async def test_routes_to_ask(self) -> None:
        from duh.mcp.server import call_tool

        with patch("duh.mcp.server._handle_ask", new_callable=AsyncMock) as mock:
            from mcp.types import TextContent

            mock.return_value = [TextContent(type="text", text="ok")]
            result = await call_tool("duh_ask", {"question": "test"})
            mock.assert_called_once_with({"question": "test"})
            assert result[0].text == "ok"

    async def test_routes_to_recall(self) -> None:
        from duh.mcp.server import call_tool

        with patch("duh.mcp.server._handle_recall", new_callable=AsyncMock) as mock:
            from mcp.types import TextContent

            mock.return_value = [TextContent(type="text", text="[]")]
            result = await call_tool("duh_recall", {"query": "test"})
            mock.assert_called_once_with({"query": "test"})
            assert result[0].text == "[]"

    async def test_routes_to_threads(self) -> None:
        from duh.mcp.server import call_tool

        with patch("duh.mcp.server._handle_threads", new_callable=AsyncMock) as mock:
            from mcp.types import TextContent

            mock.return_value = [TextContent(type="text", text="[]")]
            result = await call_tool("duh_threads", {})
            mock.assert_called_once_with({})
            assert result[0].text == "[]"

    async def test_unknown_tool(self) -> None:
        from duh.mcp.server import call_tool

        result = await call_tool("duh_nonexistent", {})
        assert len(result) == 1
        assert "Unknown tool" in result[0].text


# ── _handle_ask ──────────────────────────────────────────────────


class TestHandleAsk:
    """Test _handle_ask with mocked consensus functions."""

    async def test_consensus_protocol(self) -> None:
        from duh.mcp.server import _handle_ask

        mock_pm = AsyncMock()
        mock_pm.total_cost = 0.05

        with (
            patch("duh.config.loader.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._setup_providers",
                new_callable=AsyncMock,
                return_value=mock_pm,
            ),
            patch(
                "duh.cli.app._run_consensus",
                new_callable=AsyncMock,
                return_value=("Use SQLite.", 0.9, "minor dissent", 0.05),
            ),
        ):
            result = await _handle_ask({"question": "What DB?", "rounds": 2})

        data = json.loads(result[0].text)
        assert data["decision"] == "Use SQLite."
        assert data["confidence"] == 0.9
        assert data["dissent"] == "minor dissent"
        assert data["cost"] == 0.05

    async def test_voting_protocol(self) -> None:
        from dataclasses import dataclass

        from duh.mcp.server import _handle_ask

        @dataclass
        class FakeVote:
            model_ref: str
            content: str
            confidence: float

        @dataclass
        class FakeAggregation:
            votes: tuple  # type: ignore[type-arg]
            decision: str
            strategy: str
            confidence: float

        fake_result = FakeAggregation(
            votes=(FakeVote("m1", "Use X", 0.9),),
            decision="Use X",
            strategy="majority",
            confidence=0.85,
        )
        mock_pm = AsyncMock()
        mock_pm.total_cost = 0.03

        with (
            patch("duh.config.loader.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._setup_providers",
                new_callable=AsyncMock,
                return_value=mock_pm,
            ),
            patch(
                "duh.consensus.voting.run_voting",
                new_callable=AsyncMock,
                return_value=fake_result,
            ),
        ):
            result = await _handle_ask({"question": "What?", "protocol": "voting"})

        data = json.loads(result[0].text)
        assert data["decision"] == "Use X"
        assert data["confidence"] == 0.85
        assert data["votes"] == 1
        assert data["cost"] == 0.03


# ── _handle_recall ───────────────────────────────────────────────


class TestHandleRecall:
    """Test _handle_recall with in-memory DB."""

    async def test_recall_empty(self) -> None:
        factory, engine = await _make_db_async()

        with (
            patch("duh.config.loader.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            from duh.mcp.server import _handle_recall

            result = await _handle_recall({"query": "test"})

        data = json.loads(result[0].text)
        assert data == []
        await engine.dispose()

    async def test_recall_with_data(self) -> None:
        factory, engine = await _make_db_async()

        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Best database for microservices?")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(turn.id, thread.id, "Use PostgreSQL.", 0.9)
                await session.commit()

        await _seed()

        with (
            patch("duh.config.loader.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            from duh.mcp.server import _handle_recall

            result = await _handle_recall({"query": "microservices"})

        data = json.loads(result[0].text)
        assert len(data) == 1
        assert "microservices" in data[0]["question"]
        assert data[0]["decision"] == "Use PostgreSQL."
        assert data[0]["confidence"] == 0.9
        await engine.dispose()


# ── _handle_threads ──────────────────────────────────────────────


class TestHandleThreads:
    """Test _handle_threads with in-memory DB."""

    async def test_threads_empty(self) -> None:
        factory, engine = await _make_db_async()

        with (
            patch("duh.config.loader.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            from duh.mcp.server import _handle_threads

            result = await _handle_threads({})

        data = json.loads(result[0].text)
        assert data == []
        await engine.dispose()

    async def test_threads_with_data(self) -> None:
        factory, engine = await _make_db_async()

        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                t1 = await repo.create_thread("Question one")
                t1.status = "complete"
                t2 = await repo.create_thread("Question two")
                t2.status = "active"
                await session.commit()

        await _seed()

        with (
            patch("duh.config.loader.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            from duh.mcp.server import _handle_threads

            result = await _handle_threads({})

        data = json.loads(result[0].text)
        assert len(data) == 2
        await engine.dispose()

    async def test_threads_filter_by_status(self) -> None:
        factory, engine = await _make_db_async()

        async def _seed() -> None:
            from duh.memory.repository import MemoryRepository

            async with factory() as session:
                repo = MemoryRepository(session)
                t1 = await repo.create_thread("Complete question")
                t1.status = "complete"
                t2 = await repo.create_thread("Active question")
                t2.status = "active"
                await session.commit()

        await _seed()

        with (
            patch("duh.config.loader.load_config", return_value=_mem_config()),
            patch(
                "duh.cli.app._create_db",
                new_callable=AsyncMock,
                return_value=(factory, engine),
            ),
        ):
            from duh.mcp.server import _handle_threads

            result = await _handle_threads({"status": "complete"})

        data = json.loads(result[0].text)
        assert len(data) == 1
        assert data[0]["status"] == "complete"
        await engine.dispose()


# ── CLI command ──────────────────────────────────────────────────


class TestMcpCliCommand:
    """Verify the mcp CLI command exists."""

    def test_mcp_help(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["mcp", "--help"])
        assert result.exit_code == 0
        assert "MCP server" in result.output

    def test_mcp_in_help_listing(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "mcp" in result.output
