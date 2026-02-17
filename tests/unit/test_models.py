"""Tests for SQLAlchemy models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from duh.memory.models import (
    Base,
    Contribution,
    Decision,
    Thread,
    ThreadSummary,
    Turn,
    TurnSummary,
)


def _make_thread(question: str = "What is AI?", **kwargs) -> Thread:
    return Thread(question=question, **kwargs)


def _make_turn(thread: Thread, round_number: int = 1, state: str = "propose") -> Turn:
    return Turn(thread=thread, round_number=round_number, state=state)


def _make_contribution(
    turn: Turn,
    model_ref: str = "mock:model-a",
    role: str = "proposer",
    content: str = "Test response",
) -> Contribution:
    return Contribution(turn=turn, model_ref=model_ref, role=role, content=content)


# ── Model Creation ───────────────────────────────────────────────


class TestModelCreation:
    def test_thread_has_table_name(self) -> None:
        assert Thread.__tablename__ == "threads"

    def test_turn_has_table_name(self) -> None:
        assert Turn.__tablename__ == "turns"

    def test_contribution_has_table_name(self) -> None:
        assert Contribution.__tablename__ == "contributions"

    def test_turn_summary_has_table_name(self) -> None:
        assert TurnSummary.__tablename__ == "turn_summaries"

    def test_thread_summary_has_table_name(self) -> None:
        assert ThreadSummary.__tablename__ == "thread_summaries"

    def test_decision_has_table_name(self) -> None:
        assert Decision.__tablename__ == "decisions"

    async def test_thread_defaults_after_persist(self, db_session: AsyncSession):
        thread = _make_thread()
        db_session.add(thread)
        await db_session.commit()

        assert thread.status == "active"
        assert thread.id is not None
        assert len(thread.id) == 36  # UUID format
        assert isinstance(thread.created_at, datetime)
        assert isinstance(thread.updated_at, datetime)

    async def test_contribution_defaults_after_persist(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        contrib = _make_contribution(turn)
        db_session.add(contrib)
        await db_session.commit()

        assert contrib.input_tokens == 0
        assert contrib.output_tokens == 0
        assert contrib.cost_usd == 0.0
        assert contrib.latency_ms == 0.0

    async def test_turn_completed_at_nullable(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        db_session.add(turn)
        await db_session.commit()

        assert turn.completed_at is None

    async def test_decision_dissent_nullable(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        decision = Decision(
            turn=turn, thread=thread, content="Final answer", confidence=0.9
        )
        db_session.add(decision)
        await db_session.commit()

        assert decision.dissent is None
        assert decision.confidence == pytest.approx(0.9)


# ── Relationships ────────────────────────────────────────────────


class TestRelationships:
    async def test_thread_has_turns(self, db_session: AsyncSession):
        thread = _make_thread()
        _make_turn(thread, round_number=1)
        _make_turn(thread, round_number=2)
        db_session.add(thread)
        await db_session.commit()

        assert len(thread.turns) == 2
        assert thread.turns[0].round_number == 1
        assert thread.turns[1].round_number == 2

    async def test_turns_ordered_by_round_number(self, db_session: AsyncSession):
        thread = _make_thread()
        # Add in reverse order
        _make_turn(thread, round_number=3, state="revise")
        _make_turn(thread, round_number=1, state="propose")
        _make_turn(thread, round_number=2, state="challenge")
        db_session.add(thread)
        await db_session.commit()
        tid = thread.id

        # Reload from DB to test SQL-level ordering
        db_session.expunge_all()
        loaded = await db_session.get(Thread, tid)
        assert loaded is not None
        await db_session.refresh(loaded, ["turns"])
        rounds = [t.round_number for t in loaded.turns]
        assert rounds == [1, 2, 3]

    async def test_turn_has_contributions(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        _make_contribution(turn, role="proposer")
        _make_contribution(turn, model_ref="mock:model-b", role="challenger")
        db_session.add(thread)
        await db_session.commit()

        assert len(turn.contributions) == 2
        roles = {c.role for c in turn.contributions}
        assert roles == {"proposer", "challenger"}

    async def test_turn_has_decision(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        decision = Decision(turn=turn, thread=thread, content="Answer", confidence=0.8)
        db_session.add(thread)
        await db_session.commit()

        assert turn.decision is not None
        assert turn.decision is decision
        assert turn.decision.content == "Answer"

    async def test_turn_has_summary(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        ts = TurnSummary(turn=turn, summary="Turn summary", model_ref="mock:m")
        db_session.add(thread)
        await db_session.commit()

        assert turn.summary is ts
        assert turn.summary.summary == "Turn summary"

    async def test_thread_has_summary(self, db_session: AsyncSession):
        thread = _make_thread()
        ts = ThreadSummary(thread=thread, summary="Thread summary", model_ref="mock:m")
        db_session.add(thread)
        await db_session.commit()

        assert thread.summary is ts

    async def test_thread_decisions_viewonly(self, db_session: AsyncSession):
        thread = _make_thread()
        turn1 = _make_turn(thread, round_number=1)
        turn2 = _make_turn(thread, round_number=2)
        Decision(turn=turn1, thread=thread, content="First", confidence=0.7)
        Decision(turn=turn2, thread=thread, content="Second", confidence=0.9)
        db_session.add(thread)
        await db_session.commit()

        # Expire and reload to test lazy load
        db_session.expire(thread)
        await db_session.refresh(thread, ["decisions"])
        assert len(thread.decisions) == 2

    async def test_contribution_navigates_to_turn(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        contrib = _make_contribution(turn)
        db_session.add(thread)
        await db_session.commit()

        assert contrib.turn is turn
        assert contrib.turn.thread is thread

    async def test_decision_navigates_to_thread(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        decision = Decision(turn=turn, thread=thread, content="Answer", confidence=0.8)
        db_session.add(thread)
        await db_session.commit()

        assert decision.thread is thread
        assert decision.turn is turn


# ── Constraints ──────────────────────────────────────────────────


class TestConstraints:
    async def test_thread_question_not_null(self, db_session: AsyncSession):
        thread = Thread()  # no question
        db_session.add(thread)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_turn_unique_thread_round(self, db_session: AsyncSession):
        thread = _make_thread()
        _make_turn(thread, round_number=1)
        db_session.add(thread)
        await db_session.commit()

        # Second turn with same round_number for same thread
        dup = Turn(thread_id=thread.id, round_number=1, state="challenge")
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_decision_unique_turn(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        Decision(turn=turn, thread=thread, content="First", confidence=0.8)
        db_session.add(thread)
        await db_session.commit()

        # Second decision for same turn
        dup = Decision(
            turn_id=turn.id, thread_id=thread.id, content="Second", confidence=0.5
        )
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_turn_summary_unique_turn(self, db_session: AsyncSession):
        thread = _make_thread()
        turn = _make_turn(thread)
        TurnSummary(turn=turn, summary="First", model_ref="mock:m")
        db_session.add(thread)
        await db_session.commit()

        dup = TurnSummary(turn_id=turn.id, summary="Second", model_ref="mock:m")
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_thread_summary_unique_thread(self, db_session: AsyncSession):
        thread = _make_thread()
        ThreadSummary(thread=thread, summary="First", model_ref="mock:m")
        db_session.add(thread)
        await db_session.commit()

        dup = ThreadSummary(thread_id=thread.id, summary="Second", model_ref="mock:m")
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_turn_fk_requires_valid_thread(self, db_session: AsyncSession):
        turn = Turn(thread_id="nonexistent-id", round_number=1, state="propose")
        db_session.add(turn)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ── Indexes ──────────────────────────────────────────────────────


class TestIndexes:
    def test_thread_status_index(self) -> None:
        indexes = {idx.name for idx in Thread.__table__.indexes}
        assert "ix_threads_status" in indexes

    def test_thread_created_at_index(self) -> None:
        indexes = {idx.name for idx in Thread.__table__.indexes}
        assert "ix_threads_created_at" in indexes

    def test_turn_thread_round_unique_index(self) -> None:
        indexes = {idx.name for idx in Turn.__table__.indexes}
        assert "ix_turns_thread_round" in indexes
        idx = next(
            i for i in Turn.__table__.indexes if i.name == "ix_turns_thread_round"
        )
        assert idx.unique

    def test_turn_thread_id_index(self) -> None:
        assert any("thread_id" in str(idx.columns) for idx in Turn.__table__.indexes)

    def test_contribution_turn_id_index(self) -> None:
        col_names = {
            col.name for idx in Contribution.__table__.indexes for col in idx.columns
        }
        assert "turn_id" in col_names

    def test_contribution_model_ref_index(self) -> None:
        col_names = {
            col.name for idx in Contribution.__table__.indexes for col in idx.columns
        }
        assert "model_ref" in col_names

    def test_decision_thread_id_index(self) -> None:
        col_names = {
            col.name for idx in Decision.__table__.indexes for col in idx.columns
        }
        assert "thread_id" in col_names

    def test_all_tables_created(self) -> None:
        expected = {
            "threads",
            "turns",
            "contributions",
            "turn_summaries",
            "thread_summaries",
            "decisions",
            "outcomes",
            "subtasks",
            "votes",
            "api_keys",
        }
        assert expected == set(Base.metadata.tables.keys())


# ── Round-trip Persistence ───────────────────────────────────────


class TestRoundTrip:
    async def test_thread_round_trip(self, db_session: AsyncSession):
        thread = _make_thread(question="What is consciousness?")
        db_session.add(thread)
        await db_session.commit()
        tid = thread.id

        # Clear identity map, reload
        db_session.expunge_all()
        loaded = await db_session.get(Thread, tid)
        assert loaded is not None
        assert loaded.question == "What is consciousness?"
        assert loaded.status == "active"
        assert isinstance(loaded.created_at, datetime)

    async def test_full_consensus_round_trip(self, db_session: AsyncSession):
        """Save a complete consensus round and verify all relationships."""
        # Build the object graph
        thread = _make_thread(question="Should we use microservices?")
        turn = _make_turn(thread, round_number=1, state="commit")
        turn.completed_at = datetime.now(UTC)

        proposal = _make_contribution(
            turn,
            model_ref="anthropic:claude-opus-4-6",
            role="proposer",
            content="Yes, for these reasons...",
        )
        challenge = _make_contribution(
            turn,
            model_ref="openai:gpt-5.2",
            role="challenger",
            content="But consider...",
        )
        proposal.input_tokens = 500
        proposal.output_tokens = 200
        proposal.cost_usd = 0.0055
        proposal.latency_ms = 1234.5
        challenge.input_tokens = 600
        challenge.output_tokens = 150
        challenge.cost_usd = 0.0031
        challenge.latency_ms = 987.3

        TurnSummary(turn=turn, summary="Discussed microservices", model_ref="mock:m")
        ThreadSummary(
            thread=thread, summary="Architecture discussion", model_ref="mock:m"
        )
        Decision(
            turn=turn,
            thread=thread,
            content="Use microservices for auth only",
            confidence=0.85,
            dissent="Monolith might be simpler for MVP",
        )

        db_session.add(thread)
        await db_session.commit()
        tid = thread.id

        # Reload from scratch
        db_session.expunge_all()
        loaded = await db_session.get(Thread, tid)
        assert loaded is not None

        # Eagerly load relationships
        await db_session.refresh(loaded, ["turns", "summary", "decisions"])
        assert len(loaded.turns) == 1

        loaded_turn = loaded.turns[0]
        await db_session.refresh(loaded_turn, ["contributions", "summary", "decision"])

        assert loaded_turn.round_number == 1
        assert loaded_turn.state == "commit"
        assert loaded_turn.completed_at is not None

        assert len(loaded_turn.contributions) == 2
        proposer = next(c for c in loaded_turn.contributions if c.role == "proposer")
        assert proposer.model_ref == "anthropic:claude-opus-4-6"
        assert proposer.input_tokens == 500
        assert proposer.cost_usd == pytest.approx(0.0055)

        assert loaded_turn.summary is not None
        assert loaded_turn.summary.summary == "Discussed microservices"

        assert loaded_turn.decision is not None
        assert loaded_turn.decision.confidence == pytest.approx(0.85)
        assert loaded_turn.decision.dissent == "Monolith might be simpler for MVP"

        assert loaded.summary is not None
        assert loaded.summary.summary == "Architecture discussion"

        assert len(loaded.decisions) == 1

    async def test_cascade_delete_thread(self, db_session: AsyncSession):
        """Deleting a thread cascades to turns, contributions, summaries, decisions."""
        thread = _make_thread()
        turn = _make_turn(thread)
        _make_contribution(turn)
        TurnSummary(turn=turn, summary="s", model_ref="m:a")
        ThreadSummary(thread=thread, summary="s", model_ref="m:a")
        Decision(turn=turn, thread=thread, content="d", confidence=0.5)

        db_session.add(thread)
        await db_session.commit()
        tid = thread.id

        # Delete the thread
        await db_session.delete(thread)
        await db_session.commit()

        # Verify everything is gone
        assert await db_session.get(Thread, tid) is None
        # Verify via inspect that related tables are empty
        from sqlalchemy import func, select

        for model in [Turn, Contribution, TurnSummary, ThreadSummary, Decision]:
            result = await db_session.execute(select(func.count()).select_from(model))
            assert result.scalar() == 0, f"{model.__tablename__} should be empty"
