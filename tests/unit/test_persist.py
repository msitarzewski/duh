"""Tests for incremental consensus persistence (duh.memory.persist)."""

from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.consensus.machine import ChallengeResult, RoundResult
from duh.memory.models import Base
from duh.memory.persist import IncrementalPersister, persist_consensus
from duh.memory.repository import MemoryRepository


async def _make_factory() -> async_sessionmaker:
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _fks(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


def _round(n: int = 1) -> RoundResult:
    return RoundResult(
        round_number=n,
        proposal=f"Proposal {n}",
        proposal_model="anthropic:claude-opus-4-8",
        challenges=(
            ChallengeResult(
                model_ref="openai:gpt-5.5",
                content=f"Challenge {n}",
                citations=({"url": "https://ex.com", "title": "Ex"},),
            ),
        ),
        revision=f"Revision {n}",
        decision=f"Decision {n}",
        confidence=0.8,
        rigor=0.7,
        dissent="Some dissent",
        proposal_citations=({"url": "https://p.com", "title": "P"},),
        revision_citations=(),
    )


class TestIncrementalPersister:
    async def test_start_creates_active_thread(self) -> None:
        factory = await _make_factory()
        p = IncrementalPersister(factory, "Q?")
        tid = await p.start()
        assert tid
        async with factory() as session:
            thread = await MemoryRepository(session).get_thread(tid)
            assert thread is not None
            assert thread.status == "active"

    async def test_round_visible_before_finalize(self) -> None:
        """A persisted round is durable even if finalize never runs (crash)."""
        factory = await _make_factory()
        p = IncrementalPersister(factory, "Q?")
        tid = await p.start()
        await p.persist_round(_round(1))
        # Simulate a crash here — no finalize.
        async with factory() as session:
            thread = await MemoryRepository(session).get_thread(tid)
            assert thread is not None
            assert thread.status == "active"  # not yet complete
            assert len(thread.turns) == 1
            turn = thread.turns[0]
            roles = sorted(c.role for c in turn.contributions)
            assert roles == ["challenger", "proposer", "reviser"]
            assert turn.decision is not None
            assert turn.decision.content == "Decision 1"
            # Citations persisted on the proposer contribution
            prop = next(c for c in turn.contributions if c.role == "proposer")
            assert prop.citations_json is not None
            assert "p.com" in prop.citations_json

    async def test_finalize_completes_and_attaches_usage(self) -> None:
        factory = await _make_factory()
        p = IncrementalPersister(factory, "Q?")
        tid = await p.start()
        await p.persist_round(_round(1))
        await p.finalize(
            overview="Overview text",
            followups=["next?"],
            usage={"input_tokens": 100, "output_tokens": 50, "cost_usd": 0.01},
        )
        async with factory() as session:
            thread = await MemoryRepository(session).get_thread(tid)
            assert thread is not None
            assert thread.status == "complete"
            assert thread.usage_json is not None
            assert "100" in thread.usage_json
            assert thread.followups_json is not None
            assert "next?" in thread.followups_json

    async def test_persist_round_before_start_raises(self) -> None:
        factory = await _make_factory()
        p = IncrementalPersister(factory, "Q?")
        try:
            await p.persist_round(_round(1))
            raise AssertionError("expected RuntimeError")
        except RuntimeError:
            pass

    async def test_multiple_rounds_accumulate(self) -> None:
        factory = await _make_factory()
        p = IncrementalPersister(factory, "Q?")
        tid = await p.start()
        await p.persist_round(_round(1))
        await p.persist_round(_round(2))
        await p.finalize()
        async with factory() as session:
            thread = await MemoryRepository(session).get_thread(tid)
            assert thread is not None
            assert len(thread.turns) == 2
            assert {t.round_number for t in thread.turns} == {1, 2}


class TestPersistConsensusConvenience:
    async def test_batch_wrapper_matches_incremental(self) -> None:
        factory = await _make_factory()
        tid = await persist_consensus(
            factory,
            "Q?",
            [_round(1), _round(2)],
            overview="ov",
            followups=["f1"],
            usage={"input_tokens": 9, "output_tokens": 3, "cost_usd": 0.001},
        )
        async with factory() as session:
            thread = await MemoryRepository(session).get_thread(tid)
            assert thread is not None
            assert thread.status == "complete"
            assert len(thread.turns) == 2
            assert thread.usage_json is not None and "9" in thread.usage_json
