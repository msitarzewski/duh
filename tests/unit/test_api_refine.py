"""Tests for POST /api/refine and POST /api/enrich endpoints."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.app import create_app
from duh.config.schema import DuhConfig
from duh.memory.models import Base
from duh.providers.manager import ProviderManager
from tests.fixtures.providers import MockProvider


async def _make_app() -> TestClient:
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
        responses={"model-a": json.dumps({"needs_refinement": False})},
        input_cost=1.0,
        output_cost=5.0,
    )
    pm = ProviderManager(cost_hard_limit=100.0)
    await pm.register(mock_prov)  # type: ignore[arg-type]

    app = create_app(config)
    app.state.db_factory = factory
    app.state.engine = engine
    app.state.provider_manager = pm
    return TestClient(app, raise_server_exceptions=False)


class TestRefineEndpoint:
    async def test_refine_no_refinement(self) -> None:
        client = await _make_app()
        with patch(
            "duh.consensus.refine.analyze_question",
            new_callable=AsyncMock,
            return_value={"needs_refinement": False},
        ):
            resp = client.post("/api/refine", json={"question": "What is 2+2?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_refinement"] is False
        assert data["questions"] == []

    async def test_refine_with_questions(self) -> None:
        client = await _make_app()
        questions = [
            {"question": "What scale?", "hint": "users/day"},
            {"question": "Budget?", "hint": None},
        ]
        with patch(
            "duh.consensus.refine.analyze_question",
            new_callable=AsyncMock,
            return_value={"needs_refinement": True, "questions": questions},
        ):
            resp = client.post("/api/refine", json={"question": "What DB?"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["needs_refinement"] is True
        assert len(data["questions"]) == 2

    async def test_refine_custom_max_questions(self) -> None:
        client = await _make_app()
        with patch(
            "duh.consensus.refine.analyze_question",
            new_callable=AsyncMock,
            return_value={"needs_refinement": False},
        ) as mock_analyze:
            client.post(
                "/api/refine",
                json={"question": "Test?", "max_questions": 2},
            )
            mock_analyze.assert_called_once()
            _, kwargs = mock_analyze.call_args
            assert kwargs["max_questions"] == 2


class TestEnrichEndpoint:
    async def test_enrich(self) -> None:
        client = await _make_app()
        with patch(
            "duh.consensus.refine.enrich_question",
            new_callable=AsyncMock,
            return_value="What DB for a 10k-user SaaS?",
        ):
            resp = client.post(
                "/api/enrich",
                json={
                    "original_question": "What DB?",
                    "clarifications": [
                        {"question": "Scale?", "answer": "10k users"},
                    ],
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "10k" in data["enriched_question"]
