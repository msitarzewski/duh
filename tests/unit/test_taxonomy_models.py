"""Tests for v0.2 taxonomy, outcome, and subtask models + repository."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from duh.core.errors import StorageError
from duh.memory.repository import MemoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Taxonomy fields on Decision ─────────────────────────────────────


class TestDecisionTaxonomy:
    async def test_taxonomy_fields_nullable(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test question")
        turn = await repo.create_turn(thread.id, 1, "complete")
        decision = await repo.save_decision(turn.id, thread.id, "Answer", 0.85)
        assert decision.intent is None
        assert decision.category is None
        assert decision.genus is None

    async def test_taxonomy_fields_set(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Test question")
        turn = await repo.create_turn(thread.id, 1, "complete")
        decision = await repo.save_decision(
            turn.id,
            thread.id,
            "Answer",
            0.85,
            intent="factual",
            category="science",
            genus="physics",
        )
        assert decision.intent == "factual"
        assert decision.category == "science"
        assert decision.genus == "physics"

    async def test_taxonomy_persists(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        turn = await repo.create_turn(thread.id, 1, "complete")
        await repo.save_decision(turn.id, thread.id, "A", 0.9, intent="judgment")
        await db_session.commit()

        loaded = await repo.get_decisions(thread.id)
        assert len(loaded) == 1
        assert loaded[0].intent == "judgment"


# ── Outcome CRUD ────────────────────────────────────────────────────


class TestOutcomeCRUD:
    async def test_save_and_get_outcome(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        turn = await repo.create_turn(thread.id, 1, "complete")
        decision = await repo.save_decision(turn.id, thread.id, "Answer", 0.8)
        outcome = await repo.save_outcome(
            decision.id, thread.id, "success", notes="Worked well"
        )
        assert outcome.result == "success"
        assert outcome.notes == "Worked well"

        loaded = await repo.get_outcome(decision.id)
        assert loaded is not None
        assert loaded.id == outcome.id

    async def test_get_outcome_missing(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        result = await repo.get_outcome("nonexistent")
        assert result is None

    async def test_get_outcomes_for_thread(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        t1 = await repo.create_turn(thread.id, 1, "complete")
        t2 = await repo.create_turn(thread.id, 2, "complete")
        d1 = await repo.save_decision(t1.id, thread.id, "A1", 0.8)
        d2 = await repo.save_decision(t2.id, thread.id, "A2", 0.9)
        await repo.save_outcome(d1.id, thread.id, "success")
        await repo.save_outcome(d2.id, thread.id, "partial")

        outcomes = await repo.get_outcomes_for_thread(thread.id)
        assert len(outcomes) == 2

    async def test_decisions_with_outcomes(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        turn = await repo.create_turn(thread.id, 1, "complete")
        decision = await repo.save_decision(turn.id, thread.id, "A", 0.8)
        await repo.save_outcome(decision.id, thread.id, "failure")

        decisions = await repo.get_decisions_with_outcomes(thread.id)
        assert len(decisions) == 1
        assert decisions[0].outcome is not None
        assert decisions[0].outcome.result == "failure"


# ── Subtask CRUD ────────────────────────────────────────────────────


class TestSubtaskCRUD:
    async def test_save_and_get_subtasks(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Complex Q")
        await repo.save_subtask(thread.id, "Part 1", "First part", sequence_order=0)
        await repo.save_subtask(thread.id, "Part 2", "Second part", sequence_order=1)

        subtasks = await repo.get_subtasks(thread.id)
        assert len(subtasks) == 2
        assert subtasks[0].label == "Part 1"
        assert subtasks[1].label == "Part 2"

    async def test_subtask_with_dependencies(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        st = await repo.save_subtask(
            thread.id,
            "Dependent",
            "Depends on others",
            dependencies='["st-1"]',
        )
        assert st.dependencies == '["st-1"]'

    async def test_update_subtask_status(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        st = await repo.save_subtask(thread.id, "Task", "Do it")
        assert st.status == "pending"

        updated = await repo.update_subtask_status(st.id, "complete")
        assert updated.status == "complete"

    async def test_update_missing_subtask_raises(
        self, db_session: AsyncSession
    ) -> None:
        repo = MemoryRepository(db_session)
        with pytest.raises(StorageError, match="Subtask not found"):
            await repo.update_subtask_status("nonexistent", "complete")

    async def test_subtask_with_child_thread(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        parent = await repo.create_thread("Parent Q")
        child = await repo.create_thread("Child Q")
        st = await repo.save_subtask(
            parent.id,
            "Sub",
            "Sub desc",
            child_thread_id=child.id,
        )
        assert st.child_thread_id == child.id

    async def test_get_subtasks_empty(self, db_session: AsyncSession) -> None:
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q")
        subtasks = await repo.get_subtasks(thread.id)
        assert subtasks == []
