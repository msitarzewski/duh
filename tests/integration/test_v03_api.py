"""End-to-end integration tests for v0.3 API features.

Exercises the full stack: FastAPI app -> consensus/voting engine -> DB,
using MockProvider (no real API calls) and in-memory SQLite (no disk I/O).
"""

from __future__ import annotations

import json
import tempfile
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from duh.api.app import create_app
from duh.config.schema import DuhConfig
from duh.providers.manager import ProviderManager
from tests.fixtures.providers import MockProvider
from tests.fixtures.responses import CONSENSUS_BASIC

# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def config() -> DuhConfig:
    """Config wired to in-memory SQLite and dev-mode (no API keys)."""
    cfg = DuhConfig()
    cfg.database.url = "sqlite+aiosqlite:///:memory:"
    cfg.general.max_rounds = 1
    cfg.providers = {}  # No real providers
    return cfg


@pytest.fixture
def mock_provider() -> MockProvider:
    return MockProvider(
        provider_id="mock",
        responses=CONSENSUS_BASIC,
        input_cost=1.0,
        output_cost=5.0,
    )


@pytest.fixture
def client(config: DuhConfig, mock_provider: MockProvider) -> TestClient:
    """Synchronous test client with lifespan managed.

    Patches _setup_providers in the lifespan so the app boots with
    our MockProvider instead of trying to reach real cloud APIs.
    """

    async def _mock_setup_providers(cfg: Any) -> ProviderManager:
        pm = ProviderManager()
        await pm.register(mock_provider)
        return pm

    with patch("duh.cli.app._setup_providers", side_effect=_mock_setup_providers):
        app = create_app(config)
        with TestClient(app) as c:
            yield c


# ── Helpers ──────────────────────────────────────────────────────


def _ask(client: TestClient, **overrides: Any) -> dict[str, Any]:
    """POST /api/ask with defaults and return parsed JSON."""
    body: dict[str, Any] = {
        "question": "What is the best database for a CLI tool?",
        "protocol": "consensus",
        "rounds": 1,
    }
    body.update(overrides)
    resp = client.post("/api/ask", json=body)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── TestAPIFullConsensus ─────────────────────────────────────────


class TestAPIFullConsensus:
    """POST /api/ask with consensus protocol returns a full result."""

    def test_consensus_returns_decision(self, client: TestClient) -> None:
        data = _ask(client)
        assert "decision" in data
        assert isinstance(data["decision"], str)
        assert len(data["decision"]) > 0

    def test_consensus_returns_confidence(self, client: TestClient) -> None:
        data = _ask(client)
        assert "confidence" in data
        assert isinstance(data["confidence"], float)
        assert 0.0 <= data["confidence"] <= 1.0

    def test_consensus_returns_cost(self, client: TestClient) -> None:
        data = _ask(client)
        assert "cost" in data
        assert isinstance(data["cost"], float)
        assert data["cost"] >= 0.0

    def test_consensus_protocol_used(self, client: TestClient) -> None:
        data = _ask(client)
        assert data["protocol_used"] == "consensus"


# ── TestAPIVoting ────────────────────────────────────────────────


class TestAPIVoting:
    """POST /api/ask with voting protocol."""

    def test_voting_returns_decision(self, client: TestClient) -> None:
        data = _ask(client, protocol="voting")
        assert "decision" in data
        assert isinstance(data["decision"], str)

    def test_voting_protocol_used(self, client: TestClient) -> None:
        data = _ask(client, protocol="voting")
        assert data["protocol_used"] == "voting"

    def test_voting_returns_confidence(self, client: TestClient) -> None:
        data = _ask(client, protocol="voting")
        assert "confidence" in data
        assert isinstance(data["confidence"], float)


# ── TestAPIThreadFlow ────────────────────────────────────────────


class TestAPIThreadFlow:
    """POST /api/ask -> GET /api/threads -> GET /api/threads/{id}."""

    def test_threads_list_returns_structure(self, client: TestClient) -> None:
        resp = client.get("/api/threads")
        assert resp.status_code == 200
        data = resp.json()
        assert "threads" in data
        assert "total" in data

    def test_thread_list_pagination(self, client: TestClient) -> None:
        """GET /api/threads supports limit and offset."""
        resp = client.get("/api/threads", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        data = resp.json()
        assert "threads" in data
        assert "total" in data

    def test_thread_not_found_returns_404(self, client: TestClient) -> None:
        """GET /api/threads/{bad-id} returns 404."""
        resp = client.get("/api/threads/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
        assert resp.status_code == 404


# ── TestAPIRecallFlow ────────────────────────────────────────────


class TestAPIRecallFlow:
    """GET /api/recall searches past decisions."""

    def test_recall_returns_results_structure(self, client: TestClient) -> None:
        resp = client.get("/api/recall", params={"query": "database"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "database"

    def test_recall_respects_limit(self, client: TestClient) -> None:
        resp = client.get("/api/recall", params={"query": "test", "limit": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 3

    def test_recall_missing_query_returns_422(self, client: TestClient) -> None:
        resp = client.get("/api/recall")
        assert resp.status_code == 422  # Missing required param


# ── TestAPIFeedbackFlow ──────────────────────────────────────────


class TestAPIFeedbackFlow:
    """POST /api/feedback records an outcome."""

    def test_feedback_requires_valid_thread(self, client: TestClient) -> None:
        resp = client.post(
            "/api/feedback",
            json={
                "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "result": "success",
            },
        )
        assert resp.status_code == 404

    def test_feedback_validates_result_field(self, client: TestClient) -> None:
        resp = client.post(
            "/api/feedback",
            json={
                "thread_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "result": "invalid_value",
            },
        )
        assert resp.status_code == 400


# ── TestAPICostFlow ──────────────────────────────────────────────


class TestAPICostFlow:
    """GET /api/cost returns cost summary."""

    def test_cost_returns_structure(self, client: TestClient) -> None:
        resp = client.get("/api/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost" in data
        assert "total_input_tokens" in data
        assert "total_output_tokens" in data
        assert "by_model" in data

    def test_cost_defaults_to_zero(self, client: TestClient) -> None:
        resp = client.get("/api/cost")
        data = resp.json()
        assert data["total_cost"] >= 0.0
        assert data["total_input_tokens"] >= 0
        assert data["total_output_tokens"] >= 0


# ── TestAPIModels ────────────────────────────────────────────────


class TestAPIModels:
    """GET /api/models returns available models."""

    def test_models_returns_mock_models(self, client: TestClient) -> None:
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "total" in data
        # MockProvider has 4 models from CONSENSUS_BASIC
        assert data["total"] == len(CONSENSUS_BASIC)

    def test_model_structure(self, client: TestClient) -> None:
        resp = client.get("/api/models")
        data = resp.json()
        assert len(data["models"]) > 0
        model = data["models"][0]
        assert "provider_id" in model
        assert "model_id" in model
        assert "display_name" in model
        assert "context_window" in model
        assert "input_cost_per_mtok" in model
        assert "output_cost_per_mtok" in model

    def test_models_all_from_mock_provider(self, client: TestClient) -> None:
        resp = client.get("/api/models")
        data = resp.json()
        for model in data["models"]:
            assert model["provider_id"] == "mock"


# ── TestHealthEndpoint ───────────────────────────────────────────


class TestHealthEndpoint:
    """GET /api/health is always accessible."""

    def test_health_returns_ok(self, client: TestClient) -> None:
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ── TestWebSocketConsensus ───────────────────────────────────────


class TestWebSocketConsensus:
    """WS /ws/ask streams consensus phase events."""

    def _collect_ws_events(
        self, client: TestClient, payload: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Helper: connect WS, send payload, collect events until complete/error."""
        events: list[dict[str, Any]] = []
        with client.websocket_connect("/ws/ask") as ws:
            ws.send_json(payload)
            while True:
                try:
                    msg = ws.receive_json()
                    events.append(msg)
                    if msg.get("type") in ("complete", "error"):
                        break
                except Exception:
                    break
        return events

    def test_ws_streams_phases(self, client: TestClient) -> None:
        events = self._collect_ws_events(
            client, {"question": "What database should I use?", "rounds": 1}
        )
        types = [e["type"] for e in events]
        assert "phase_start" in types
        assert "complete" in types

    def test_ws_complete_has_decision(self, client: TestClient) -> None:
        events = self._collect_ws_events(
            client, {"question": "Test question", "rounds": 1}
        )
        complete_events = [e for e in events if e["type"] == "complete"]
        assert len(complete_events) == 1
        complete = complete_events[0]
        assert "decision" in complete
        assert "confidence" in complete
        assert "cost" in complete

    def test_ws_missing_question_sends_error(self, client: TestClient) -> None:
        events = self._collect_ws_events(client, {"rounds": 1})
        assert len(events) >= 1
        assert events[0]["type"] == "error"

    def test_ws_streams_propose_challenge_revise(self, client: TestClient) -> None:
        events = self._collect_ws_events(
            client, {"question": "Architecture question", "rounds": 1}
        )
        phases = [e["phase"] for e in events if e.get("type") == "phase_start"]
        assert "PROPOSE" in phases
        assert "CHALLENGE" in phases
        assert "REVISE" in phases


# ── TestExportRoundTrip ──────────────────────────────────────────


class TestExportRoundTrip:
    """Create thread via DB, export as JSON and markdown via CLI formatters."""

    def _seed_thread(self, config: DuhConfig) -> tuple[Any, Any, str]:
        """Seed a thread with a decision into in-memory DB."""
        import asyncio

        from duh.cli.app import _create_db
        from duh.memory.repository import MemoryRepository

        async def _setup() -> tuple[Any, Any, str]:
            factory, engine = await _create_db(config)
            async with factory() as session:
                repo = MemoryRepository(session)
                thread = await repo.create_thread("Test question for export")
                turn = await repo.create_turn(thread.id, 1, "COMMIT")
                await repo.save_decision(
                    turn.id,
                    thread.id,
                    "Use SQLite",
                    0.85,
                    dissent="Consider Postgres",
                )
                await session.commit()
                tid = thread.id
            return factory, engine, tid

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_setup())
        finally:
            loop.close()

    def _load_thread(self, factory: Any) -> tuple[Any, list[Any]]:
        """Load thread and votes from factory."""
        import asyncio

        from duh.memory.repository import MemoryRepository

        async def _load(fac: Any) -> tuple[Any, list[Any]]:
            async with fac() as session:
                # list threads to get thread_id
                repo = MemoryRepository(session)
                threads = await repo.list_threads(limit=1)
                tid = threads[0].id
                thread = await repo.get_thread(tid)
                votes = await repo.get_votes(tid)
            return thread, votes

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_load(factory))
        finally:
            loop.close()

    def test_export_json_format(self, config: DuhConfig) -> None:
        factory, engine, _tid = self._seed_thread(config)
        thread, votes = self._load_thread(factory)

        from duh.cli.app import _format_thread_json

        output = _format_thread_json(thread, votes)

        import asyncio

        loop = asyncio.new_event_loop()
        loop.run_until_complete(engine.dispose())
        loop.close()

        parsed = json.loads(output)
        assert parsed["question"] == "Test question for export"
        assert len(parsed["turns"]) == 1
        assert parsed["turns"][0]["decision"]["content"] == "Use SQLite"
        assert parsed["turns"][0]["decision"]["confidence"] == 0.85

    def test_export_markdown_format(self, config: DuhConfig) -> None:
        factory, engine, _tid = self._seed_thread(config)
        thread, votes = self._load_thread(factory)

        from duh.cli.app import _format_thread_markdown

        output = _format_thread_markdown(thread, votes)

        import asyncio

        loop = asyncio.new_event_loop()
        loop.run_until_complete(engine.dispose())
        loop.close()

        assert "# Consensus: Test question for export" in output
        assert "## Decision" in output
        assert "Use SQLite" in output


# ── TestBatchProcessing ──────────────────────────────────────────


class TestBatchProcessing:
    """Batch file parsing and processing."""

    def test_batch_text_file_parsing(self) -> None:
        from duh.cli.app import _parse_batch_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("What is the best database?\n")
            f.write("# This is a comment\n")
            f.write("What is the best language?\n")
            f.write("\n")
            f.write("What is the best framework?\n")
            path = f.name

        questions = _parse_batch_file(path, "consensus")
        assert len(questions) == 3
        assert questions[0]["question"] == "What is the best database?"
        assert questions[0]["protocol"] == "consensus"
        assert questions[2]["question"] == "What is the best framework?"

    def test_batch_jsonl_file_parsing(self) -> None:
        from duh.cli.app import _parse_batch_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write('{"question": "Q1", "protocol": "voting"}\n')
            f.write('{"question": "Q2"}\n')
            path = f.name

        questions = _parse_batch_file(path, "consensus")
        assert len(questions) == 2
        assert questions[0]["question"] == "Q1"
        assert questions[0]["protocol"] == "voting"
        assert questions[1]["question"] == "Q2"
        assert questions[1]["protocol"] == "consensus"

    def test_batch_empty_file(self) -> None:
        from duh.cli.app import _parse_batch_file

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("")
            path = f.name

        questions = _parse_batch_file(path, "consensus")
        assert questions == []


# ── TestClientAgainstAPI ─────────────────────────────────────────


class TestClientAgainstAPI:
    """Use httpx AsyncClient with ASGITransport against the test app.

    Manually sets up app.state (db_factory, provider_manager) since
    ASGITransport does not invoke the ASGI lifespan by default.
    """

    @pytest.fixture
    async def async_client(self, config: DuhConfig, mock_provider: MockProvider) -> Any:
        import httpx

        from duh.cli.app import _create_db

        pm = ProviderManager()
        await pm.register(mock_provider)

        app = create_app(config)
        # Manually wire state that lifespan would normally set
        factory, engine = await _create_db(config)
        app.state.db_factory = factory
        app.state.engine = engine
        app.state.provider_manager = pm

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client

        await engine.dispose()

    async def test_client_health(self, async_client: Any) -> None:
        resp = await async_client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    async def test_client_ask_via_transport(self, async_client: Any) -> None:
        resp = await async_client.post(
            "/api/ask",
            json={
                "question": "Client test question",
                "protocol": "consensus",
                "rounds": 1,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert "confidence" in data

    async def test_client_models_via_transport(self, async_client: Any) -> None:
        resp = await async_client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == len(CONSENSUS_BASIC)

    async def test_client_threads_via_transport(self, async_client: Any) -> None:
        resp = await async_client.get("/api/threads")
        assert resp.status_code == 200
        data = resp.json()
        assert "threads" in data

    async def test_client_recall_via_transport(self, async_client: Any) -> None:
        resp = await async_client.get("/api/recall", params={"query": "test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data

    async def test_client_cost_via_transport(self, async_client: Any) -> None:
        resp = await async_client.get("/api/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_cost" in data
