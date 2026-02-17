"""Memory repository — CRUD, search, thread listing.

All mutating methods add objects to the session and flush, but do NOT
commit.  The caller controls transaction boundaries via
``session.commit()``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from duh.core.errors import StorageError
from duh.memory.models import (
    APIKey,
    Contribution,
    Decision,
    Outcome,
    Subtask,
    Thread,
    ThreadSummary,
    Turn,
    TurnSummary,
    Vote,
    _utcnow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class MemoryRepository:
    """Async repository for conversation memory."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Thread ───────────────────────────────────────────────────

    async def create_thread(self, question: str) -> Thread:
        """Create a new thread and return it with its generated ID."""
        thread = Thread(question=question)
        self._session.add(thread)
        await self._session.flush()
        return thread

    async def get_thread(self, thread_id: str) -> Thread | None:
        """Load a thread with its turns, contributions, decisions, and summaries."""
        stmt = (
            select(Thread)
            .where(Thread.id == thread_id)
            .options(
                selectinload(Thread.turns).selectinload(Turn.contributions),
                selectinload(Thread.turns).selectinload(Turn.decision),
                selectinload(Thread.turns).selectinload(Turn.summary),
                selectinload(Thread.summary),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_threads(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Thread]:
        """List threads ordered by most recent first."""
        stmt = select(Thread).order_by(Thread.created_at.desc())
        if status is not None:
            stmt = stmt.where(Thread.status == status)
        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def delete_thread(self, thread_id: str) -> None:
        """Delete a thread and all its related objects (via cascade).

        Raises StorageError if the thread does not exist.
        """
        thread = await self._session.get(Thread, thread_id)
        if thread is None:
            msg = f"Thread not found: {thread_id}"
            raise StorageError(msg)
        await self._session.delete(thread)
        await self._session.flush()

    # ── Turn ─────────────────────────────────────────────────────

    async def create_turn(self, thread_id: str, round_number: int, state: str) -> Turn:
        """Create a turn within a thread."""
        turn = Turn(thread_id=thread_id, round_number=round_number, state=state)
        self._session.add(turn)
        await self._session.flush()
        return turn

    async def get_turn(self, turn_id: str) -> Turn | None:
        """Load a turn with contributions, decision, and summary."""
        stmt = (
            select(Turn)
            .where(Turn.id == turn_id)
            .options(
                selectinload(Turn.contributions),
                selectinload(Turn.decision),
                selectinload(Turn.summary),
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    # ── Contribution ─────────────────────────────────────────────

    async def add_contribution(
        self,
        turn_id: str,
        model_ref: str,
        role: str,
        content: str,
        *,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        latency_ms: float = 0.0,
    ) -> Contribution:
        """Record a model's contribution to a turn."""
        contrib = Contribution(
            turn_id=turn_id,
            model_ref=model_ref,
            role=role,
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
        )
        self._session.add(contrib)
        await self._session.flush()
        return contrib

    # ── Decision ─────────────────────────────────────────────────

    async def save_decision(
        self,
        turn_id: str,
        thread_id: str,
        content: str,
        confidence: float,
        *,
        dissent: str | None = None,
        intent: str | None = None,
        category: str | None = None,
        genus: str | None = None,
    ) -> Decision:
        """Record the committed decision for a turn."""
        decision = Decision(
            turn_id=turn_id,
            thread_id=thread_id,
            content=content,
            confidence=confidence,
            dissent=dissent,
            intent=intent,
            category=category,
            genus=genus,
        )
        self._session.add(decision)
        await self._session.flush()
        return decision

    async def get_decisions(self, thread_id: str) -> list[Decision]:
        """Get all decisions for a thread, ordered chronologically."""
        stmt = (
            select(Decision)
            .where(Decision.thread_id == thread_id)
            .order_by(Decision.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Summaries ────────────────────────────────────────────────

    async def save_turn_summary(
        self, turn_id: str, summary: str, model_ref: str
    ) -> TurnSummary:
        """Create or update the summary for a turn."""
        stmt = select(TurnSummary).where(TurnSummary.turn_id == turn_id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.summary = summary
            existing.model_ref = model_ref
            await self._session.flush()
            return existing
        ts = TurnSummary(turn_id=turn_id, summary=summary, model_ref=model_ref)
        self._session.add(ts)
        await self._session.flush()
        return ts

    async def save_thread_summary(
        self, thread_id: str, summary: str, model_ref: str
    ) -> ThreadSummary:
        """Create or update the summary for a thread."""
        stmt = select(ThreadSummary).where(ThreadSummary.thread_id == thread_id)
        result = await self._session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.summary = summary
            existing.model_ref = model_ref
            await self._session.flush()
            return existing
        ts = ThreadSummary(thread_id=thread_id, summary=summary, model_ref=model_ref)
        self._session.add(ts)
        await self._session.flush()
        return ts

    # ── Search ───────────────────────────────────────────────────

    async def search(self, query: str, *, limit: int = 20) -> list[Thread]:
        """Keyword search across thread questions and decision content.

        Returns threads ordered by most recent first.
        """
        pattern = f"%{query}%"
        stmt = (
            select(Thread)
            .outerjoin(Decision, Decision.thread_id == Thread.id)
            .where(
                or_(
                    Thread.question.ilike(pattern),
                    Decision.content.ilike(pattern),
                )
            )
            .distinct()
            .order_by(Thread.created_at.desc())
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Outcome ──────────────────────────────────────────────────

    async def save_outcome(
        self,
        decision_id: str,
        thread_id: str,
        result_str: str,
        *,
        notes: str | None = None,
    ) -> Outcome:
        """Record an outcome for a decision."""
        outcome = Outcome(
            decision_id=decision_id,
            thread_id=thread_id,
            result=result_str,
            notes=notes,
        )
        self._session.add(outcome)
        await self._session.flush()
        return outcome

    async def get_outcome(self, decision_id: str) -> Outcome | None:
        """Get the outcome for a decision."""
        stmt = select(Outcome).where(Outcome.decision_id == decision_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_outcomes_for_thread(self, thread_id: str) -> list[Outcome]:
        """Get all outcomes for a thread."""
        stmt = (
            select(Outcome)
            .where(Outcome.thread_id == thread_id)
            .order_by(Outcome.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_decisions_with_outcomes(self, thread_id: str) -> list[Decision]:
        """Get decisions with eagerly loaded outcomes for a thread."""
        stmt = (
            select(Decision)
            .where(Decision.thread_id == thread_id)
            .options(selectinload(Decision.outcome))
            .order_by(Decision.created_at)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── Decision Space ──────────────────────────────────────────

    async def get_all_decisions_for_space(
        self,
        *,
        category: str | None = None,
        genus: str | None = None,
        outcome: str | None = None,
        confidence_min: float | None = None,
        confidence_max: float | None = None,
        since: str | None = None,
        until: str | None = None,
        search: str | None = None,
    ) -> list[Decision]:
        """Get decisions with outcomes for the Decision Space visualization.

        Returns decisions with eagerly loaded outcomes and thread questions,
        with optional filtering.
        """
        from datetime import datetime

        stmt = (
            select(Decision)
            .join(Thread, Decision.thread_id == Thread.id)
            .outerjoin(Outcome, Outcome.decision_id == Decision.id)
            .options(
                selectinload(Decision.outcome),
                selectinload(Decision.thread),
            )
            .order_by(Decision.created_at)
        )

        if category is not None:
            stmt = stmt.where(Decision.category == category)
        if genus is not None:
            stmt = stmt.where(Decision.genus == genus)
        if outcome is not None:
            stmt = stmt.where(Outcome.result == outcome)
        if confidence_min is not None:
            stmt = stmt.where(Decision.confidence >= confidence_min)
        if confidence_max is not None:
            stmt = stmt.where(Decision.confidence <= confidence_max)
        if since is not None:
            stmt = stmt.where(Decision.created_at >= datetime.fromisoformat(since))
        if until is not None:
            stmt = stmt.where(Decision.created_at <= datetime.fromisoformat(until))
        if search is not None:
            pattern = f"%{search}%"
            stmt = stmt.where(
                or_(
                    Thread.question.ilike(pattern),
                    Decision.content.ilike(pattern),
                )
            )

        result = await self._session.execute(stmt)
        return list(result.scalars().unique().all())

    # ── Subtask ──────────────────────────────────────────────────

    async def save_subtask(
        self,
        parent_thread_id: str,
        label: str,
        description: str,
        *,
        dependencies: str = "[]",
        sequence_order: int = 0,
        child_thread_id: str | None = None,
    ) -> Subtask:
        """Record a subtask for a thread."""
        subtask = Subtask(
            parent_thread_id=parent_thread_id,
            label=label,
            description=description,
            dependencies=dependencies,
            sequence_order=sequence_order,
            child_thread_id=child_thread_id,
        )
        self._session.add(subtask)
        await self._session.flush()
        return subtask

    async def get_subtasks(self, parent_thread_id: str) -> list[Subtask]:
        """Get all subtasks for a parent thread, ordered by sequence."""
        stmt = (
            select(Subtask)
            .where(Subtask.parent_thread_id == parent_thread_id)
            .order_by(Subtask.sequence_order)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_subtask_status(self, subtask_id: str, status: str) -> Subtask:
        """Update the status of a subtask.

        Raises StorageError if the subtask does not exist.
        """
        subtask = await self._session.get(Subtask, subtask_id)
        if subtask is None:
            msg = f"Subtask not found: {subtask_id}"
            raise StorageError(msg)
        subtask.status = status
        await self._session.flush()
        return subtask

    # ── Vote ──────────────────────────────────────────────────────

    async def save_vote(self, thread_id: str, model_ref: str, content: str) -> Vote:
        """Record a vote for a thread."""
        vote = Vote(
            thread_id=thread_id,
            model_ref=model_ref,
            content=content,
        )
        self._session.add(vote)
        await self._session.flush()
        return vote

    async def get_votes(self, thread_id: str) -> list[Vote]:
        """Get all votes for a thread, ordered chronologically."""
        stmt = select(Vote).where(Vote.thread_id == thread_id).order_by(Vote.created_at)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    # ── API Key ──────────────────────────────────────────────

    async def create_api_key(self, name: str, key_hash: str) -> APIKey:
        """Create a new API key record."""
        api_key = APIKey(name=name, key_hash=key_hash)
        self._session.add(api_key)
        await self._session.flush()
        return api_key

    async def validate_api_key(self, key_hash: str) -> APIKey | None:
        """Look up an API key by hash. Returns None if not found or revoked."""
        stmt = select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.revoked_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_api_key(self, key_id: str) -> APIKey:
        """Revoke an API key by ID.

        Raises StorageError if the key does not exist.
        """
        api_key = await self._session.get(APIKey, key_id)
        if api_key is None:
            msg = f"API key not found: {key_id}"
            raise StorageError(msg)
        api_key.revoked_at = _utcnow()
        await self._session.flush()
        return api_key

    async def list_api_keys(self) -> list[APIKey]:
        """List all API keys ordered by creation date."""
        stmt = select(APIKey).order_by(APIKey.created_at.desc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())
