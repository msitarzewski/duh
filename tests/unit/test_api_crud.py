"""Tests for CRUD endpoints: recall, feedback, models, cost."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware
from duh.api.routes.crud import router as crud_router
from duh.memory.models import Base
from duh.memory.repository import MemoryRepository

# -- Helpers -------------------------------------------------------------------


async def _make_app(*, provider_manager: object | None = None) -> FastAPI:
    """Create a minimal FastAPI app with in-memory DB and CRUD routes."""
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
    app.state.provider_manager = provider_manager

    app.add_middleware(RateLimitMiddleware, rate_limit=1000, window=60)
    app.add_middleware(APIKeyMiddleware)

    app.include_router(crud_router)
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


# -- Fake provider manager for /models ----------------------------------------


@dataclass(frozen=True)
class FakeModelInfo:
    provider_id: str
    model_id: str
    display_name: str
    context_window: int
    max_output_tokens: int
    input_cost_per_mtok: float
    output_cost_per_mtok: float
    proposer_eligible: bool = True


class FakeProviderManager:
    def __init__(self, models: list[FakeModelInfo] | None = None) -> None:
        self._models = models or []

    def list_all_models(self) -> list[FakeModelInfo]:
        return self._models


# -- TestRecall ----------------------------------------------------------------


class TestRecall:
    async def test_empty_results(self) -> None:
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/recall", params={"query": "nonexistent"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["query"] == "nonexistent"

    async def test_search_finds_threads(self) -> None:
        app = await _make_app()
        await _seed_thread_with_decision(app, question="Best database for analytics?")
        await _seed_thread_with_decision(app, question="Best language for web?")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/recall", params={"query": "database"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert "database" in data["results"][0]["question"].lower()
        assert data["results"][0]["decision"] is not None
        assert data["results"][0]["confidence"] is not None

    async def test_limit_param(self) -> None:
        app = await _make_app()
        for i in range(5):
            await _seed_thread_with_decision(app, question=f"Database question {i}")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/recall", params={"query": "Database", "limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) <= 2

    async def test_thread_without_decision(self) -> None:
        """Threads without decisions still appear, but decision/confidence are None."""
        app = await _make_app()
        async with app.state.db_factory() as session:
            repo = MemoryRepository(session)
            await repo.create_thread("Bare database thread")
            await session.commit()

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/recall", params={"query": "database"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 1
        assert data["results"][0]["decision"] is None
        assert data["results"][0]["confidence"] is None


# -- TestFeedback --------------------------------------------------------------


class TestFeedback:
    async def test_records_outcome(self) -> None:
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/feedback",
            json={"thread_id": thread_id, "result": "success", "notes": "Worked!"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "recorded"
        assert data["thread_id"] == thread_id

    async def test_404_for_missing_thread(self) -> None:
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/feedback",
            json={
                "thread_id": "00000000-0000-0000-0000-000000000000",
                "result": "success",
            },
        )
        assert resp.status_code == 404

    async def test_400_for_invalid_result(self) -> None:
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/feedback",
            json={"thread_id": thread_id, "result": "maybe"},
        )
        assert resp.status_code == 400
        assert "success" in resp.json()["detail"]

    async def test_prefix_matching(self) -> None:
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)
        prefix = thread_id[:8]

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/feedback",
            json={"thread_id": prefix, "result": "failure"},
        )
        assert resp.status_code == 200
        assert resp.json()["thread_id"] == thread_id

    async def test_404_no_decisions(self) -> None:
        """Thread exists but has no decisions."""
        app = await _make_app()
        async with app.state.db_factory() as session:
            repo = MemoryRepository(session)
            thread = await repo.create_thread("A question with no decisions")
            await session.commit()
            thread_id = thread.id

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/feedback",
            json={"thread_id": thread_id, "result": "success"},
        )
        assert resp.status_code == 404
        assert "No decisions" in resp.json()["detail"]


# -- TestModels ----------------------------------------------------------------


class TestModels:
    async def test_returns_model_list(self) -> None:
        fake_models = [
            FakeModelInfo(
                provider_id="openai",
                model_id="gpt-4o",
                display_name="GPT-4o",
                context_window=128000,
                max_output_tokens=4096,
                input_cost_per_mtok=5.0,
                output_cost_per_mtok=15.0,
            ),
            FakeModelInfo(
                provider_id="anthropic",
                model_id="claude-sonnet-4-5-20250929",
                display_name="Claude Sonnet 4.5",
                context_window=200000,
                max_output_tokens=8192,
                input_cost_per_mtok=3.0,
                output_cost_per_mtok=15.0,
            ),
        ]
        pm = FakeProviderManager(fake_models)
        app = await _make_app(provider_manager=pm)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["models"]) == 2

        model_ids = {m["model_id"] for m in data["models"]}
        assert "gpt-4o" in model_ids
        assert "claude-sonnet-4-5-20250929" in model_ids

    async def test_correct_fields(self) -> None:
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
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/models")
        assert resp.status_code == 200
        m = resp.json()["models"][0]
        assert m["provider_id"] == "openai"
        assert m["model_id"] == "gpt-4o"
        assert m["display_name"] == "GPT-4o"
        assert m["context_window"] == 128000
        assert m["max_output_tokens"] == 4096
        assert m["input_cost_per_mtok"] == 5.0
        assert m["output_cost_per_mtok"] == 15.0

    async def test_empty_models(self) -> None:
        pm = FakeProviderManager([])
        app = await _make_app(provider_manager=pm)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["models"] == []


# -- TestCost ------------------------------------------------------------------


class TestCost:
    async def test_returns_cost_summary(self) -> None:
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)
        turn_id = await _get_turn_id(app, thread_id)

        await _seed_contribution(
            app,
            turn_id,
            "openai:gpt-4o",
            input_tokens=500,
            output_tokens=1000,
            cost_usd=0.01,
        )
        await _seed_contribution(
            app,
            turn_id,
            "anthropic:claude-sonnet-4-5-20250929",
            input_tokens=300,
            output_tokens=800,
            cost_usd=0.008,
        )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost"] > 0
        assert data["total_input_tokens"] == 800
        assert data["total_output_tokens"] == 1800
        assert len(data["by_model"]) == 2

    async def test_empty_when_no_contributions(self) -> None:
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cost"] == 0.0
        assert data["total_input_tokens"] == 0
        assert data["total_output_tokens"] == 0
        assert data["by_model"] == []

    async def test_by_model_ordering(self) -> None:
        """Models should be ordered by cost descending."""
        app = await _make_app()
        thread_id, _ = await _seed_thread_with_decision(app)
        turn_id = await _get_turn_id(app, thread_id)

        await _seed_contribution(app, turn_id, "cheap:model", cost_usd=0.001)
        await _seed_contribution(app, turn_id, "expensive:model", cost_usd=0.05)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["by_model"]) == 2
        assert data["by_model"][0]["model_ref"] == "expensive:model"
        assert data["by_model"][1]["model_ref"] == "cheap:model"
