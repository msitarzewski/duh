"""Incremental consensus persistence.

Writes a consensus thread to the database progressively — the thread is
created up front (status ``active``), each round is committed as soon as it
finishes, and the thread is finalized (status ``complete``) at the end. A
crash mid-run therefore leaves a real, partial thread instead of nothing.

The per-round write logic lives in :meth:`IncrementalPersister.persist_round`
so every caller (CLI loop, WebSocket loop, and the batch
:func:`persist_consensus` convenience) shares one implementation.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from duh.memory.repository import MemoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from duh.consensus.machine import RoundResult

logger = logging.getLogger(__name__)


def _citations_json(citations: object) -> str | None:
    """Serialize a list of citation dicts to JSON, or None if empty."""
    if not citations:
        return None
    return json.dumps(
        [{"url": c["url"], "title": c.get("title")} for c in citations]  # type: ignore[attr-defined]
    )


class IncrementalPersister:
    """Persist a consensus thread one round at a time.

    Each method opens its own session and commits independently, so a round
    that has been persisted survives a later crash.
    """

    def __init__(
        self, db_factory: async_sessionmaker[AsyncSession], question: str
    ) -> None:
        self._db_factory = db_factory
        self._question = question
        self.thread_id: str | None = None

    async def start(self) -> str:
        """Create the thread (status ``active``) and return its ID."""
        async with self._db_factory() as session:
            repo = MemoryRepository(session)
            thread = await repo.create_thread(self._question)
            thread.status = "active"
            await session.commit()
            self.thread_id = str(thread.id)
            return self.thread_id

    async def persist_round(self, rr: RoundResult) -> None:
        """Write a single finished round (turn + contributions + decision)."""
        if self.thread_id is None:
            msg = "persist_round called before start()"
            raise RuntimeError(msg)
        async with self._db_factory() as session:
            repo = MemoryRepository(session)
            turn = await repo.create_turn(self.thread_id, rr.round_number, "COMMIT")
            await repo.add_contribution(
                turn.id,
                rr.proposal_model,
                "proposer",
                rr.proposal,
                citations_json=_citations_json(rr.proposal_citations),
            )
            for ch in rr.challenges:
                await repo.add_contribution(
                    turn.id,
                    ch.model_ref,
                    "challenger",
                    ch.content,
                    citations_json=_citations_json(ch.citations),
                )
            await repo.add_contribution(
                turn.id,
                rr.proposal_model,
                "reviser",
                rr.revision,
                citations_json=_citations_json(rr.revision_citations),
            )
            await repo.save_decision(
                turn.id,
                self.thread_id,
                rr.decision,
                rr.confidence,
                rigor=rr.rigor,
                dissent=rr.dissent,
            )
            await session.commit()

    async def finalize(
        self,
        *,
        overview: str | None = None,
        followups: list[str] | None = None,
        usage: dict[str, float] | None = None,
    ) -> None:
        """Mark the thread complete and attach overview/followups/usage."""
        if self.thread_id is None:
            msg = "finalize called before start()"
            raise RuntimeError(msg)
        async with self._db_factory() as session:
            repo = MemoryRepository(session)
            thread = await repo.get_thread(self.thread_id)
            if thread is None:
                logger.warning("finalize: thread %s vanished", self.thread_id)
                return
            thread.status = "complete"
            if overview:
                await repo.save_thread_summary(thread.id, overview, "overview")
            if followups:
                thread.followups_json = json.dumps(followups)
            if usage:
                thread.usage_json = json.dumps(usage)
            await session.commit()


async def persist_consensus(
    db_factory: async_sessionmaker[AsyncSession],
    question: str,
    round_history: list[RoundResult],
    *,
    overview: str | None = None,
    followups: list[str] | None = None,
    usage: dict[str, float] | None = None,
) -> str:
    """Persist a full round history at once and return the thread ID.

    Convenience wrapper over :class:`IncrementalPersister` for callers that
    already hold the complete history (batch runs, tests). Internally this is
    still the same incremental path: start -> persist each round -> finalize.
    """
    persister = IncrementalPersister(db_factory, question)
    thread_id = await persister.start()
    for rr in round_history:
        await persister.persist_round(rr)
    await persister.finalize(overview=overview, followups=followups, usage=usage)
    return thread_id
