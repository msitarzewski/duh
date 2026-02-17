"""Tests for POST /api/ask endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.app import create_app
from duh.config.schema import DuhConfig
from duh.memory.models import Base
from duh.providers.manager import ProviderManager
from tests.fixtures.providers import MockProvider

# ── Helpers ────────────────────────────────────────────────────


async def _make_app() -> tuple[TestClient, DuhConfig]:
    """Create a test app with mocked providers and in-memory DB."""
    config = DuhConfig()
    config.database.url = "sqlite+aiosqlite:///:memory:"

    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)

    mock_prov = MockProvider(
        provider_id="mock",
        responses={"model-a": "Test decision from model A."},
        input_cost=1.0,
        output_cost=5.0,
    )

    pm = ProviderManager(cost_hard_limit=100.0)
    await pm.register(mock_prov)  # type: ignore[arg-type]

    app = create_app(config)
    app.state.db_factory = factory
    app.state.engine = engine
    app.state.provider_manager = pm

    client = TestClient(app, raise_server_exceptions=False)
    return client, config


# ── TestAskEndpoint ───────────────────────────────────────────


class TestAskEndpoint:
    async def test_post_returns_200(self) -> None:
        """POST /api/ask returns 200 with decision, confidence, cost."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_consensus",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.api.routes.ask import AskResponse

            mock_fn.return_value = AskResponse(
                decision="Use PostgreSQL",
                confidence=0.85,
                dissent=None,
                cost=0.0042,
                protocol_used="consensus",
            )
            resp = client.post("/api/ask", json={"question": "Which database?"})

        assert resp.status_code == 200
        data = resp.json()
        assert "decision" in data
        assert "confidence" in data
        assert "cost" in data

    async def test_consensus_protocol_default(self) -> None:
        """Default protocol is consensus."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_consensus",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.api.routes.ask import AskResponse

            mock_fn.return_value = AskResponse(
                decision="Consensus answer",
                confidence=0.9,
                cost=0.01,
                protocol_used="consensus",
            )
            resp = client.post("/api/ask", json={"question": "Test question"})

        assert resp.status_code == 200
        assert resp.json()["protocol_used"] == "consensus"
        mock_fn.assert_called_once()

    async def test_voting_protocol(self) -> None:
        """Voting protocol is invoked when protocol=voting."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_voting",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.api.routes.ask import AskResponse

            mock_fn.return_value = AskResponse(
                decision="Voting answer",
                confidence=0.8,
                cost=0.005,
                protocol_used="voting",
            )
            resp = client.post(
                "/api/ask",
                json={"question": "Best language?", "protocol": "voting"},
            )

        assert resp.status_code == 200
        assert resp.json()["protocol_used"] == "voting"
        mock_fn.assert_called_once()

    async def test_missing_question_returns_422(self) -> None:
        """Missing question field returns 422 validation error."""
        client, _ = await _make_app()
        resp = client.post("/api/ask", json={})
        assert resp.status_code == 422

    async def test_response_includes_protocol_used(self) -> None:
        """Response always includes protocol_used field."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_consensus",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.api.routes.ask import AskResponse

            mock_fn.return_value = AskResponse(
                decision="Answer",
                confidence=0.7,
                cost=0.003,
                protocol_used="consensus",
            )
            resp = client.post("/api/ask", json={"question": "Hello?"})

        assert resp.status_code == 200
        assert "protocol_used" in resp.json()

    async def test_custom_rounds_parameter(self) -> None:
        """Custom rounds parameter is passed through to config."""
        client, config = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_consensus",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.api.routes.ask import AskResponse

            mock_fn.return_value = AskResponse(
                decision="Answer",
                confidence=0.9,
                cost=0.01,
                protocol_used="consensus",
            )
            resp = client.post(
                "/api/ask",
                json={"question": "Test", "rounds": 5},
            )

        assert resp.status_code == 200
        # The route sets config.general.max_rounds from the request
        assert config.general.max_rounds == 5

    async def test_provider_error_returns_503(self) -> None:
        """ProviderError during consensus returns 503."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_consensus",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.core.errors import ProviderError

            mock_fn.side_effect = ProviderError("openai", "API key invalid")
            resp = client.post("/api/ask", json={"question": "Test"})

        assert resp.status_code == 503
        assert "Provider error" in resp.json()["detail"]

    async def test_consensus_error_returns_502(self) -> None:
        """ConsensusError during processing returns 502."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_consensus",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.core.errors import ConsensusError

            mock_fn.side_effect = ConsensusError("Convergence failed")
            resp = client.post("/api/ask", json={"question": "Test"})

        assert resp.status_code == 502
        assert "Consensus error" in resp.json()["detail"]

    async def test_duh_error_returns_400(self) -> None:
        """Generic DuhError returns 400."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_consensus",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.core.errors import DuhError

            mock_fn.side_effect = DuhError("Bad request data")
            resp = client.post("/api/ask", json={"question": "Test"})

        assert resp.status_code == 400
        assert "Bad request data" in resp.json()["detail"]

    async def test_decompose_protocol(self) -> None:
        """Decompose flag routes to decompose handler."""
        client, _ = await _make_app()
        with patch(
            "duh.api.routes.ask._handle_decompose",
            new_callable=AsyncMock,
        ) as mock_fn:
            from duh.api.routes.ask import AskResponse

            mock_fn.return_value = AskResponse(
                decision="Decomposed answer",
                confidence=0.75,
                cost=0.02,
                protocol_used="decompose",
            )
            resp = client.post(
                "/api/ask",
                json={"question": "Complex question", "decompose": True},
            )

        assert resp.status_code == 200
        assert resp.json()["protocol_used"] == "decompose"
        mock_fn.assert_called_once()
