"""Tests for MemoryRepository: CRUD, search, thread listing."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from duh.core.errors import StorageError
from duh.memory.repository import MemoryRepository

# ── Helpers ──────────────────────────────────────────────────────


async def _seed_thread(
    repo: MemoryRepository,
    session: AsyncSession,
    question: str = "What is AI?",
    *,
    with_turn: bool = False,
    with_decision: bool = False,
) -> str:
    """Create a thread (and optionally a turn + decision), commit, return ID."""
    thread = await repo.create_thread(question)
    if with_turn or with_decision:
        turn = await repo.create_turn(thread.id, 1, "commit")
        if with_decision:
            await repo.save_decision(turn.id, thread.id, f"Answer to: {question}", 0.85)
    await session.commit()
    return thread.id


# ── Thread CRUD ──────────────────────────────────────────────────


class TestThreadCRUD:
    async def test_create_thread(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("What is AI?")
        await db_session.commit()

        assert thread.id is not None
        assert len(thread.id) == 36
        assert thread.question == "What is AI?"
        assert thread.status == "active"

    async def test_get_thread_found(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        tid = await _seed_thread(repo, db_session, with_turn=True)

        loaded = await repo.get_thread(tid)
        assert loaded is not None
        assert loaded.question == "What is AI?"
        assert len(loaded.turns) == 1

    async def test_get_thread_not_found(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        assert await repo.get_thread("nonexistent") is None

    async def test_get_thread_eager_loads_contributions(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "propose")
        await repo.add_contribution(turn.id, "mock:m", "proposer", "Response")
        await db_session.commit()

        loaded = await repo.get_thread(thread.id)
        assert loaded is not None
        assert len(loaded.turns[0].contributions) == 1

    async def test_list_threads_empty(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        assert await repo.list_threads() == []

    async def test_list_threads_ordered_by_recency(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        await _seed_thread(repo, db_session, "First")
        await _seed_thread(repo, db_session, "Second")
        await _seed_thread(repo, db_session, "Third")

        threads = await repo.list_threads()
        assert len(threads) == 3
        assert threads[0].question == "Third"
        assert threads[2].question == "First"

    async def test_list_threads_filter_by_status(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        t1 = await repo.create_thread("Active one")
        t2 = await repo.create_thread("Completed one")
        t2.status = "completed"
        await db_session.commit()

        active = await repo.list_threads(status="active")
        assert len(active) == 1
        assert active[0].id == t1.id

        completed = await repo.list_threads(status="completed")
        assert len(completed) == 1
        assert completed[0].id == t2.id

    async def test_list_threads_pagination(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        for i in range(5):
            await _seed_thread(repo, db_session, f"Thread {i}")

        page1 = await repo.list_threads(limit=2, offset=0)
        page2 = await repo.list_threads(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert page1[0].id != page2[0].id

    async def test_delete_thread(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        tid = await _seed_thread(repo, db_session, with_decision=True)

        await repo.delete_thread(tid)
        await db_session.commit()
        assert await repo.get_thread(tid) is None

    async def test_delete_nonexistent_thread_raises(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        with pytest.raises(StorageError, match="not found"):
            await repo.delete_thread("no-such-id")


# ── Turn CRUD ────────────────────────────────────────────────────


class TestTurnCRUD:
    async def test_create_turn(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "propose")
        await db_session.commit()

        assert turn.id is not None
        assert turn.round_number == 1
        assert turn.state == "propose"

    async def test_get_turn_found(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "propose")
        await repo.add_contribution(turn.id, "mock:m", "proposer", "Response")
        await db_session.commit()

        loaded = await repo.get_turn(turn.id)
        assert loaded is not None
        assert len(loaded.contributions) == 1

    async def test_get_turn_not_found(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        assert await repo.get_turn("nonexistent") is None


# ── Contribution CRUD ────────────────────────────────────────────


class TestContributionCRUD:
    async def test_add_contribution_defaults(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "propose")
        contrib = await repo.add_contribution(
            turn.id, "anthropic:opus", "proposer", "My response"
        )
        await db_session.commit()

        assert contrib.model_ref == "anthropic:opus"
        assert contrib.role == "proposer"
        assert contrib.input_tokens == 0
        assert contrib.cost_usd == 0.0

    async def test_add_contribution_with_usage(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "propose")
        contrib = await repo.add_contribution(
            turn.id,
            "openai:gpt-5.2",
            "challenger",
            "I disagree because...",
            input_tokens=500,
            output_tokens=200,
            cost_usd=0.0042,
            latency_ms=1500.0,
        )
        await db_session.commit()

        assert contrib.input_tokens == 500
        assert contrib.output_tokens == 200
        assert contrib.cost_usd == pytest.approx(0.0042)
        assert contrib.latency_ms == pytest.approx(1500.0)


# ── Decision CRUD ────────────────────────────────────────────────


class TestDecisionCRUD:
    async def test_save_decision(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "commit")
        decision = await repo.save_decision(
            turn.id, thread.id, "Final answer", 0.9, dissent="Minority view"
        )
        await db_session.commit()

        assert decision.content == "Final answer"
        assert decision.confidence == pytest.approx(0.9)
        assert decision.dissent == "Minority view"

    async def test_get_decisions_empty(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        await db_session.commit()

        assert await repo.get_decisions(thread.id) == []

    async def test_get_decisions_multiple(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn1 = await repo.create_turn(thread.id, 1, "commit")
        turn2 = await repo.create_turn(thread.id, 2, "commit")
        await repo.save_decision(turn1.id, thread.id, "First", 0.7)
        await repo.save_decision(turn2.id, thread.id, "Second", 0.9)
        await db_session.commit()

        decisions = await repo.get_decisions(thread.id)
        assert len(decisions) == 2
        assert decisions[0].content == "First"
        assert decisions[1].content == "Second"


# ── Summary CRUD ─────────────────────────────────────────────────


class TestSummaryCRUD:
    async def test_save_turn_summary_create(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "commit")
        ts = await repo.save_turn_summary(turn.id, "Summary text", "mock:m")
        await db_session.commit()

        assert ts.summary == "Summary text"
        assert ts.model_ref == "mock:m"

    async def test_save_turn_summary_update(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        turn = await repo.create_turn(thread.id, 1, "commit")
        ts1 = await repo.save_turn_summary(turn.id, "Old", "mock:a")
        await db_session.commit()

        ts2 = await repo.save_turn_summary(turn.id, "New", "mock:b")
        await db_session.commit()

        assert ts2.id == ts1.id  # same row updated
        assert ts2.summary == "New"
        assert ts2.model_ref == "mock:b"

    async def test_save_thread_summary_create(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        ts = await repo.save_thread_summary(thread.id, "Thread summary", "mock:m")
        await db_session.commit()

        assert ts.summary == "Thread summary"

    async def test_save_thread_summary_update(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test")
        ts1 = await repo.save_thread_summary(thread.id, "Old", "mock:a")
        await db_session.commit()

        ts2 = await repo.save_thread_summary(thread.id, "New", "mock:b")
        await db_session.commit()

        assert ts2.id == ts1.id
        assert ts2.summary == "New"


# ── Search ───────────────────────────────────────────────────────


class TestSearch:
    async def test_search_by_question(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        await _seed_thread(repo, db_session, "What is machine learning?")
        await _seed_thread(repo, db_session, "How do databases work?")

        results = await repo.search("machine")
        assert len(results) == 1
        assert results[0].question == "What is machine learning?"

    async def test_search_by_decision_content(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        await _seed_thread(repo, db_session, "General question", with_decision=True)
        # The decision content is "Answer to: General question"
        results = await repo.search("Answer to")
        assert len(results) == 1

    async def test_search_case_insensitive(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        await _seed_thread(repo, db_session, "UPPERCASE question")

        results = await repo.search("uppercase")
        assert len(results) == 1

    async def test_search_no_results(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        await _seed_thread(repo, db_session, "Something")

        assert await repo.search("nonexistent") == []

    async def test_search_empty_database(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        assert await repo.search("anything") == []

    async def test_search_deduplicates(self, db_session: AsyncSession):
        """Thread matching both question and decision appears once."""
        repo = MemoryRepository(db_session)
        await _seed_thread(
            repo,
            db_session,
            "What about microservices?",
            with_decision=True,
        )
        # Both question and decision content contain "microservices"
        results = await repo.search("microservices")
        assert len(results) == 1

    async def test_search_respects_limit(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        for i in range(5):
            await _seed_thread(repo, db_session, f"AI topic {i}")

        results = await repo.search("AI", limit=3)
        assert len(results) == 3


# ── Save/Load Cycle ──────────────────────────────────────────────


class TestSaveLoadCycle:
    async def test_full_consensus_save_and_reload(self, db_session: AsyncSession):
        """Create a full consensus round via the repo and reload it."""
        repo = MemoryRepository(db_session)

        thread = await repo.create_thread("Should we use Rust?")
        turn = await repo.create_turn(thread.id, 1, "commit")
        await repo.add_contribution(
            turn.id,
            "anthropic:opus",
            "proposer",
            "Yes because...",
            input_tokens=500,
            output_tokens=300,
            cost_usd=0.007,
        )
        await repo.add_contribution(
            turn.id,
            "openai:gpt-5.2",
            "challenger",
            "But consider...",
            input_tokens=600,
            output_tokens=250,
            cost_usd=0.005,
        )
        await repo.save_decision(
            turn.id,
            thread.id,
            "Use Rust for hot path only",
            0.85,
            dissent="Go is simpler",
        )
        await repo.save_turn_summary(turn.id, "Rust discussion", "mock:m")
        await repo.save_thread_summary(thread.id, "Language choice", "mock:m")
        await db_session.commit()

        # Reload
        loaded = await repo.get_thread(thread.id)
        assert loaded is not None
        assert loaded.question == "Should we use Rust?"
        assert len(loaded.turns) == 1

        t = loaded.turns[0]
        assert len(t.contributions) == 2
        assert t.decision is not None
        assert t.decision.dissent == "Go is simpler"
        assert t.summary is not None
        assert t.summary.summary == "Rust discussion"
        assert loaded.summary is not None
        assert loaded.summary.summary == "Language choice"

        decisions = await repo.get_decisions(thread.id)
        assert len(decisions) == 1
        assert decisions[0].confidence == pytest.approx(0.85)
