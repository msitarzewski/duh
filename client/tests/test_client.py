"""Tests for duh-client library."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from duh_client import DuhClient
from duh_client.client import (
    DuhAPIError,
    RecallResult,
    ThreadSummary,
)
from fastapi import FastAPI
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware
from duh.api.routes.ask import router as ask_router
from duh.api.routes.crud import router as crud_router
from duh.api.routes.threads import router as threads_router
from duh.memory.models import Base
from duh.memory.repository import MemoryRepository

# -- Helpers -------------------------------------------------------------------


@dataclass(frozen=True)
class FakeModelInfo:
    provider_id: str
    model_id: str
    display_name: str
    context_window: int
    max_output_tokens: int
    input_cost_per_mtok: float
    output_cost_per_mtok: float


class FakeProviderManager:
    def __init__(self, models: list[FakeModelInfo] | None = None) -> None:
        self._models = models or []
        self.total_cost = 0.0

    def list_all_models(self) -> list[FakeModelInfo]:
        return self._models


async def _make_app(
    *, provider_manager: object | None = None
) -> FastAPI:
    """Create a minimal FastAPI app with in-memory DB for testing."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="test")
    app.state.config = SimpleNamespace(
        api=SimpleNamespace(
            cors_origins=["*"],
            rate_limit=1000,
            rate_limit_window=60,
        ),
    )
    app.state.db_factory = factory
    app.state.engine = engine
    app.state.provider_manager = provider_manager or FakeProviderManager()

    app.add_middleware(RateLimitMiddleware, rate_limit=1000, window=60)
    app.add_middleware(APIKeyMiddleware)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(ask_router)
    app.include_router(crud_router)
    app.include_router(threads_router)

    return app


async def _seed_thread_with_decision(
    app: FastAPI,
    question: str = "What is the best database?",
    decision_content: str = "PostgreSQL for most use cases.",
    confidence: float = 0.85,
) -> tuple[str, str]:
    """Seed a thread with a turn and decision. Returns (thread_id, decision_id)."""
    async with app.state.db_factory() as session:
        repo = MemoryRepository(session)
        thread = await repo.create_thread(question)
        turn = await repo.create_turn(thread.id, 1, "COMMIT")
        decision = await repo.save_decision(
            turn.id, thread.id, decision_content, confidence
        )
        await session.commit()
        return thread.id, decision.id


async def _seed_contribution(
    app: FastAPI,
    turn_id: str,
    model_ref: str = "openai:gpt-4o",
    *,
    input_tokens: int = 100,
    output_tokens: int = 200,
    cost_usd: float = 0.005,
) -> str:
    """Seed a contribution for a turn. Returns contribution id."""
    async with app.state.db_factory() as session:
        repo = MemoryRepository(session)
        contrib = await repo.add_contribution(
            turn_id,
            model_ref,
            "proposer",
            "Some content",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
        )
        await session.commit()
        return contrib.id


async def _get_turn_id(app: FastAPI, thread_id: str) -> str:
    """Get the first turn ID for a thread."""
    async with app.state.db_factory() as session:
        repo = MemoryRepository(session)
        thread = await repo.get_thread(thread_id)
        assert thread is not None
        return thread.turns[0].id


def _make_mock_transport(
    responses: dict[str, Any],
) -> httpx.MockTransport:
    """Create an httpx.MockTransport that returns canned JSON responses.

    *responses* maps ``"METHOD /path"`` (e.g. ``"GET /api/health"``) to a dict
    with ``status_code`` and ``json`` keys.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url.raw_path.decode().split('?')[0]}"
        if key in responses:
            entry = responses[key]
            return httpx.Response(
                status_code=entry.get("status_code", 200),
                json=entry["json"],
            )
        return httpx.Response(status_code=404, json={"detail": "Not found"})

    return httpx.MockTransport(handler)


# -- TestHealth ----------------------------------------------------------------


class TestHealth:
    async def test_health_returns_true(self) -> None:
        app = await _make_app()
        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )
        client._sync_client = httpx.Client(
            transport=_make_mock_transport(
                {"GET /api/health": {"json": {"status": "ok"}}}
            ),
            base_url="http://test",
        )

        assert await client.health() is True
        await client.aclose()

    async def test_health_returns_false_on_error(self) -> None:
        transport = httpx.MockTransport(
            lambda _: (_ for _ in ()).throw(httpx.ConnectError("refused"))
        )
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        assert await client.health() is False
        await client.aclose()

    def test_health_sync_returns_true(self) -> None:
        transport = _make_mock_transport(
            {"GET /api/health": {"json": {"status": "ok"}}}
        )
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._sync_client = httpx.Client(
            transport=transport, base_url="http://test"
        )

        assert client.health_sync() is True
        client.close()


# -- TestThreads ---------------------------------------------------------------


class TestThreads:
    async def test_threads_returns_list(self) -> None:
        app = await _make_app()
        await _seed_thread_with_decision(app, question="Thread one")
        await _seed_thread_with_decision(app, question="Thread two")

        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        result = await client.threads()
        assert len(result) == 2
        assert all(isinstance(t, ThreadSummary) for t in result)
        questions = {t.question for t in result}
        assert "Thread one" in questions
        assert "Thread two" in questions
        await client.aclose()

    async def test_threads_empty(self) -> None:
        app = await _make_app()
        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        result = await client.threads()
        assert result == []
        await client.aclose()

    def test_threads_sync(self) -> None:
        transport = _make_mock_transport(
            {
                "GET /api/threads": {
                    "json": {
                        "threads": [
                            {
                                "thread_id": "abc",
                                "question": "q1",
                                "status": "complete",
                                "created_at": "2025-01-01T00:00:00",
                            }
                        ],
                        "total": 1,
                    }
                }
            }
        )
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._sync_client = httpx.Client(
            transport=transport, base_url="http://test"
        )

        result = client.threads_sync()
        assert len(result) == 1
        assert result[0].thread_id == "abc"
        client.close()


# -- TestRecall ----------------------------------------------------------------


class TestRecall:
    async def test_recall_returns_results(self) -> None:
        app = await _make_app()
        await _seed_thread_with_decision(
            app, question="Best database for analytics?"
        )

        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        results = await client.recall("database")
        assert len(results) == 1
        assert all(isinstance(r, RecallResult) for r in results)
        assert "database" in results[0].question.lower()
        await client.aclose()

    async def test_recall_empty(self) -> None:
        app = await _make_app()
        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        results = await client.recall("nonexistent")
        assert results == []
        await client.aclose()

    def test_recall_sync(self) -> None:
        transport = _make_mock_transport(
            {
                "GET /api/recall": {
                    "json": {
                        "results": [
                            {
                                "thread_id": "abc",
                                "question": "DB question",
                                "decision": "PostgreSQL",
                                "confidence": 0.9,
                            }
                        ],
                        "query": "DB",
                    }
                }
            }
        )
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._sync_client = httpx.Client(
            transport=transport, base_url="http://test"
        )

        results = client.recall_sync("DB")
        assert len(results) == 1
        assert results[0].decision == "PostgreSQL"
        client.close()


# -- TestModels ----------------------------------------------------------------


class TestModels:
    async def test_models_returns_list(self) -> None:
        pm = FakeProviderManager(
            [
                FakeModelInfo(
                    provider_id="openai",
                    model_id="gpt-4o",
                    display_name="GPT-4o",
                    context_window=128000,
                    max_output_tokens=4096,
                    input_cost_per_mtok=5.0,
                    output_cost_per_mtok=15.0,
                ),
            ]
        )
        app = await _make_app(provider_manager=pm)
        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        result = await client.models()
        assert len(result) == 1
        assert result[0]["model_id"] == "gpt-4o"
        await client.aclose()

    def test_models_sync(self) -> None:
        transport = _make_mock_transport(
            {
                "GET /api/models": {
                    "json": {
                        "models": [
                            {
                                "provider_id": "openai",
                                "model_id": "gpt-4o",
                                "display_name": "GPT-4o",
                                "context_window": 128000,
                                "max_output_tokens": 4096,
                                "input_cost_per_mtok": 5.0,
                                "output_cost_per_mtok": 15.0,
                            }
                        ],
                        "total": 1,
                    }
                }
            }
        )
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._sync_client = httpx.Client(
            transport=transport, base_url="http://test"
        )

        result = client.models_sync()
        assert len(result) == 1
        assert result[0]["model_id"] == "gpt-4o"
        client.close()


# -- TestCost ------------------------------------------------------------------


class TestCost:
    async def test_cost_returns_dict(self) -> None:
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)
        turn_id = await _get_turn_id(app, thread_id)
        await _seed_contribution(
            app, turn_id, "openai:gpt-4o", cost_usd=0.01
        )

        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        result = await client.cost()
        assert result["total_cost"] > 0
        assert "total_input_tokens" in result
        assert "total_output_tokens" in result
        assert "by_model" in result
        await client.aclose()


# -- TestFeedback --------------------------------------------------------------


class TestFeedback:
    async def test_feedback_records(self) -> None:
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)

        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        result = await client.feedback(thread_id, "success", notes="Worked!")
        assert result["status"] == "recorded"
        assert result["thread_id"] == thread_id
        await client.aclose()


# -- TestShow ------------------------------------------------------------------


class TestShow:
    async def test_show_returns_thread_detail(self) -> None:
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)

        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        result = await client.show(thread_id)
        assert result["thread_id"] == thread_id
        assert "question" in result
        assert "turns" in result
        await client.aclose()

    async def test_show_404(self) -> None:
        app = await _make_app()
        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        with pytest.raises(DuhAPIError) as exc_info:
            await client.show("00000000-0000-0000-0000-000000000000")
        assert exc_info.value.status_code == 404
        await client.aclose()


# -- TestAPIError --------------------------------------------------------------


class TestAPIError:
    async def test_raised_on_4xx(self) -> None:
        app = await _make_app()
        transport = httpx.ASGITransport(app=app)
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._async_client = httpx.AsyncClient(
            transport=transport, base_url="http://test"
        )

        with pytest.raises(DuhAPIError) as exc_info:
            await client.show("nonexistent-thread-id-that-is-36-char")
        assert exc_info.value.status_code == 404
        await client.aclose()

    def test_sync_raised_on_error(self) -> None:
        transport = _make_mock_transport(
            {
                "GET /api/models": {
                    "status_code": 500,
                    "json": {"detail": "Internal server error"},
                }
            }
        )
        client = DuhClient.__new__(DuhClient)
        client._base_url = "http://test"
        client._sync_client = httpx.Client(
            transport=transport, base_url="http://test"
        )

        with pytest.raises(DuhAPIError) as exc_info:
            client.models_sync()
        assert exc_info.value.status_code == 500
        assert "Internal server error" in exc_info.value.detail
        client.close()

    def test_error_message_format(self) -> None:
        err = DuhAPIError(422, "Validation failed")
        assert str(err) == "HTTP 422: Validation failed"
        assert err.status_code == 422
        assert err.detail == "Validation failed"


# -- TestClientInit ------------------------------------------------------------


class TestClientInit:
    def test_default_init(self) -> None:
        client = DuhClient()
        assert client._base_url == "http://localhost:8080"
        client.close()

    def test_custom_base_url(self) -> None:
        client = DuhClient("http://example.com:9000/")
        assert client._base_url == "http://example.com:9000"
        client.close()

    def test_api_key_header(self) -> None:
        client = DuhClient(api_key="test-key-123")
        assert client._async_client.headers.get("X-API-Key") == "test-key-123"
        assert client._sync_client.headers.get("X-API-Key") == "test-key-123"
        client.close()

    def test_no_api_key_header_when_none(self) -> None:
        client = DuhClient()
        assert "X-API-Key" not in client._async_client.headers
        assert "X-API-Key" not in client._sync_client.headers
        client.close()

    async def test_async_context_manager(self) -> None:
        async with DuhClient() as client:
            assert client._base_url == "http://localhost:8080"
