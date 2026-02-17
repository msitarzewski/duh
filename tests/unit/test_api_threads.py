"""Tests for GET /api/threads endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.routes.threads import router
from duh.memory.models import Base
from duh.memory.repository import MemoryRepository

# ── Helpers ────────────────────────────────────────────────────


async def _make_app() -> FastAPI:
    """Create a minimal FastAPI app with threads router and in-memory DB."""
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
    app.state.db_factory = factory
    app.state.engine = engine
    app.include_router(router)
    return app


async def _seed_thread(
    app: FastAPI,
    question: str,
    *,
    status: str = "active",
    thread_id: str | None = None,
) -> str:
    """Insert a thread and return its ID."""
    async with app.state.db_factory() as session:
        repo = MemoryRepository(session)
        thread = await repo.create_thread(question)
        if status != "active":
            thread.status = status
        if thread_id is not None:
            thread.id = thread_id
        await session.commit()
        return thread.id


async def _seed_thread_with_turn(
    app: FastAPI,
    question: str,
    *,
    contrib_content: str = "Test contribution",
    decision_content: str | None = None,
) -> str:
    """Insert a thread with a turn, contribution, and optional decision."""
    async with app.state.db_factory() as session:
        repo = MemoryRepository(session)
        thread = await repo.create_thread(question)
        turn = await repo.create_turn(thread.id, round_number=1, state="PROPOSE")
        await repo.add_contribution(
            turn.id,
            model_ref="openai/gpt-4",
            role="proposer",
            content=contrib_content,
            input_tokens=100,
            output_tokens=50,
            cost_usd=0.005,
        )
        if decision_content is not None:
            await repo.save_decision(
                turn.id,
                thread.id,
                content=decision_content,
                confidence=0.85,
                dissent="Minor disagreement",
            )
        thread.status = "complete"
        await session.commit()
        return thread.id


# ── TestListThreads ───────────────────────────────────────────


class TestListThreads:
    async def test_empty_list(self) -> None:
        """Returns empty list when no threads exist."""
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["threads"] == []
        assert data["total"] == 0

    async def test_returns_threads(self) -> None:
        """Returns seeded threads."""
        app = await _make_app()
        await _seed_thread(app, "What is Python?")
        await _seed_thread(app, "What is Rust?")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["threads"]) == 2
        questions = {t["question"] for t in data["threads"]}
        assert questions == {"What is Python?", "What is Rust?"}

    async def test_status_filter(self) -> None:
        """Filters threads by status."""
        app = await _make_app()
        await _seed_thread(app, "Active thread", status="active")
        await _seed_thread(app, "Complete thread", status="complete")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads", params={"status": "complete"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["threads"][0]["question"] == "Complete thread"
        assert data["threads"][0]["status"] == "complete"

    async def test_limit_param(self) -> None:
        """Respects limit parameter."""
        app = await _make_app()
        for i in range(5):
            await _seed_thread(app, f"Thread {i}")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads", params={"limit": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["threads"]) == 2

    async def test_offset_param(self) -> None:
        """Respects offset parameter."""
        app = await _make_app()
        for i in range(5):
            await _seed_thread(app, f"Thread {i}")

        client = TestClient(app, raise_server_exceptions=False)
        # Get with offset=3 of 5 total → should return 2
        resp = client.get("/api/threads", params={"limit": 10, "offset": 3})
        data = resp.json()
        assert data["total"] == 2
        assert len(data["threads"]) == 2

    async def test_response_shape(self) -> None:
        """Thread summary has the expected fields."""
        app = await _make_app()
        await _seed_thread(app, "Shape test")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads")
        assert resp.status_code == 200
        thread = resp.json()["threads"][0]
        assert "thread_id" in thread
        assert "question" in thread
        assert "status" in thread
        assert "created_at" in thread
        # Summary should NOT have turns
        assert "turns" not in thread


# ── TestGetThread ─────────────────────────────────────────────


class TestGetThread:
    async def test_returns_full_detail(self) -> None:
        """Returns thread with turns, contributions, and decision."""
        app = await _make_app()
        tid = await _seed_thread_with_turn(
            app,
            "Detail test",
            contrib_content="My analysis",
            decision_content="Final answer",
        )

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/threads/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["thread_id"] == tid
        assert data["question"] == "Detail test"
        assert data["status"] == "complete"
        assert "created_at" in data

        # Turns
        assert len(data["turns"]) == 1
        turn = data["turns"][0]
        assert turn["round_number"] == 1
        assert turn["state"] == "PROPOSE"

        # Contributions
        assert len(turn["contributions"]) == 1
        contrib = turn["contributions"][0]
        assert contrib["model_ref"] == "openai/gpt-4"
        assert contrib["role"] == "proposer"
        assert contrib["content"] == "My analysis"
        assert contrib["input_tokens"] == 100
        assert contrib["output_tokens"] == 50
        assert contrib["cost_usd"] == 0.005

        # Decision
        assert turn["decision"] is not None
        assert turn["decision"]["content"] == "Final answer"
        assert turn["decision"]["confidence"] == 0.85
        assert turn["decision"]["dissent"] == "Minor disagreement"

    async def test_returns_thread_without_decision(self) -> None:
        """Returns thread when turn has no decision."""
        app = await _make_app()
        tid = await _seed_thread_with_turn(app, "No decision", decision_content=None)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/threads/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        turn = data["turns"][0]
        assert turn["decision"] is None
        assert len(turn["contributions"]) == 1

    async def test_404_for_missing(self) -> None:
        """Returns 404 for non-existent thread ID."""
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/00000000-0000-0000-0000-000000000000")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_prefix_matching(self) -> None:
        """Short IDs resolve to full thread via prefix match."""
        app = await _make_app()
        tid = await _seed_thread(app, "Prefix test")

        client = TestClient(app, raise_server_exceptions=False)
        prefix = tid[:8]
        resp = client.get(f"/api/threads/{prefix}")
        assert resp.status_code == 200
        assert resp.json()["thread_id"] == tid

    async def test_ambiguous_prefix_returns_400(self) -> None:
        """Ambiguous prefix returns 400."""
        app = await _make_app()
        # Seed two threads with same prefix by forcing IDs
        id_a = "aaaa0000-0000-0000-0000-000000000001"
        id_b = "aaaa0000-0000-0000-0000-000000000002"
        await _seed_thread(app, "Thread A", thread_id=id_a)
        await _seed_thread(app, "Thread B", thread_id=id_b)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/aaaa")
        assert resp.status_code == 400
        assert "ambiguous" in resp.json()["detail"].lower()

    async def test_prefix_not_found_returns_404(self) -> None:
        """Prefix with no matches returns 404."""
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/threads/zzzz")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    async def test_response_shape(self) -> None:
        """Detail response has the expected fields."""
        app = await _make_app()
        tid = await _seed_thread(app, "Shape detail test")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(f"/api/threads/{tid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "thread_id" in data
        assert "question" in data
        assert "status" in data
        assert "created_at" in data
        assert "turns" in data
        assert isinstance(data["turns"], list)
