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
    Contribution,
    Decision,
    Thread,
    ThreadSummary,
    Turn,
    TurnSummary,
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
    ) -> Decision:
        """Record the committed decision for a turn."""
        decision = Decision(
            turn_id=turn_id,
            thread_id=thread_id,
            content=content,
            confidence=confidence,
            dissent=dissent,
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
