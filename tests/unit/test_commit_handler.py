"""Tests for the COMMIT handler: confidence, dissent, context."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from duh.consensus.handlers import (
    _compute_confidence,
    _extract_dissent,
    handle_commit,
)
from duh.consensus.machine import (
    ChallengeResult,
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
)
from duh.core.errors import ConsensusError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    defaults: dict[str, object] = {
        "thread_id": "t-1",
        "question": "What is the best database for a CLI tool?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _commit_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context in COMMIT state with proposal + challenges + revision set."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.PROPOSE)
    ctx.proposal = "We should use PostgreSQL for everything."
    ctx.proposal_model = "mock:proposer"
    sm.transition(ConsensusState.CHALLENGE)
    ctx.challenges = [
        ChallengeResult("mock:challenger-1", "PostgreSQL adds complexity."),
        ChallengeResult("mock:challenger-2", "SQLite is simpler for CLI."),
    ]
    sm.transition(ConsensusState.REVISE)
    ctx.revision = (
        "Use SQLite for v0.1 behind a repository abstraction, "
        "preserving the option to migrate to PostgreSQL later."
    )
    ctx.revision_model = "mock:proposer"
    sm.transition(ConsensusState.COMMIT)
    return ctx


# ── Confidence computation ───────────────────────────────────────


class TestComputeConfidence:
    def test_all_genuine(self) -> None:
        challenges = [
            ChallengeResult("m1", "real issue"),
            ChallengeResult("m2", "another issue"),
        ]
        assert _compute_confidence(challenges) == 1.0

    def test_all_sycophantic(self) -> None:
        challenges = [
            ChallengeResult("m1", "great answer", sycophantic=True),
            ChallengeResult("m2", "looks good", sycophantic=True),
        ]
        assert _compute_confidence(challenges) == 0.5

    def test_mixed(self) -> None:
        challenges = [
            ChallengeResult("m1", "real issue"),
            ChallengeResult("m2", "great answer", sycophantic=True),
        ]
        assert _compute_confidence(challenges) == 0.75

    def test_empty(self) -> None:
        assert _compute_confidence([]) == 0.5


# ── Dissent extraction ───────────────────────────────────────────


class TestExtractDissent:
    def test_genuine_challenges_included(self) -> None:
        challenges = [
            ChallengeResult("mock:c1", "PostgreSQL adds complexity."),
            ChallengeResult("mock:c2", "SQLite is simpler."),
        ]
        dissent = _extract_dissent(challenges)
        assert dissent is not None
        assert "[mock:c1]: PostgreSQL adds complexity." in dissent
        assert "[mock:c2]: SQLite is simpler." in dissent

    def test_sycophantic_excluded(self) -> None:
        challenges = [
            ChallengeResult("mock:c1", "Real issue here."),
            ChallengeResult("mock:c2", "Great answer!", sycophantic=True),
        ]
        dissent = _extract_dissent(challenges)
        assert dissent is not None
        assert "Real issue" in dissent
        assert "Great answer" not in dissent

    def test_all_sycophantic_returns_none(self) -> None:
        challenges = [
            ChallengeResult("m1", "Looks good", sycophantic=True),
            ChallengeResult("m2", "No issues", sycophantic=True),
        ]
        assert _extract_dissent(challenges) is None

    def test_empty_returns_none(self) -> None:
        assert _extract_dissent([]) is None

    def test_model_ref_attribution(self) -> None:
        challenges = [ChallengeResult("anthropic:opus", "A real concern.")]
        dissent = _extract_dissent(challenges)
        assert dissent is not None
        assert dissent.startswith("[anthropic:opus]:")


# ── Handler execution ────────────────────────────────────────────


class TestHandleCommit:
    async def test_happy_path(self) -> None:
        ctx = _commit_ctx()
        await handle_commit(ctx)

        assert ctx.decision is not None
        assert ctx.confidence > 0
        assert ctx.dissent is not None

    async def test_decision_equals_revision(self) -> None:
        ctx = _commit_ctx()
        revision = ctx.revision
        await handle_commit(ctx)

        assert ctx.decision == revision

    async def test_confidence_computed(self) -> None:
        ctx = _commit_ctx()
        # Default challenges are all genuine
        await handle_commit(ctx)

        assert ctx.confidence == 1.0

    async def test_confidence_with_sycophantic(self) -> None:
        ctx = _commit_ctx()
        ctx.challenges = [
            ChallengeResult("m1", "real issue"),
            ChallengeResult("m2", "great answer", sycophantic=True),
        ]
        await handle_commit(ctx)

        assert ctx.confidence == 0.75

    async def test_dissent_preserved(self) -> None:
        ctx = _commit_ctx()
        await handle_commit(ctx)

        assert ctx.dissent is not None
        assert "mock:challenger-1" in ctx.dissent
        assert "mock:challenger-2" in ctx.dissent

    async def test_dissent_excludes_sycophantic(self) -> None:
        ctx = _commit_ctx()
        ctx.challenges = [
            ChallengeResult("m1", "genuine concern"),
            ChallengeResult("m2", "great work", sycophantic=True),
        ]
        await handle_commit(ctx)

        assert ctx.dissent is not None
        assert "genuine concern" in ctx.dissent
        assert "great work" not in ctx.dissent

    async def test_wrong_state_raises(self) -> None:
        ctx = _make_ctx()  # IDLE state

        with pytest.raises(ConsensusError, match="requires COMMIT state"):
            await handle_commit(ctx)

    async def test_no_revision_raises(self) -> None:
        ctx = _make_ctx()
        ctx.state = ConsensusState.COMMIT
        ctx.revision = None

        with pytest.raises(ConsensusError, match="requires a revision"):
            await handle_commit(ctx)

    async def test_returns_none(self) -> None:
        ctx = _commit_ctx()
        result = await handle_commit(ctx)

        assert result is None


# ── End-to-end with state machine ────────────────────────────────


class TestCommitEndToEnd:
    async def test_full_commit_flow(self) -> None:
        """PROPOSE -> CHALLENGE -> REVISE -> COMMIT -> ready for COMPLETE."""
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        # PROPOSE
        sm.transition(ConsensusState.PROPOSE)
        ctx.proposal = "Use PostgreSQL"
        ctx.proposal_model = "mock:proposer"

        # CHALLENGE
        sm.transition(ConsensusState.CHALLENGE)
        ctx.challenges = [
            ChallengeResult("mock:c1", "Too complex for CLI"),
        ]

        # REVISE
        sm.transition(ConsensusState.REVISE)
        ctx.revision = "Use SQLite instead"
        ctx.revision_model = "mock:proposer"

        # COMMIT
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        assert ctx.decision == "Use SQLite instead"
        assert ctx.confidence == 1.0
        assert ctx.dissent is not None
        assert "Too complex" in ctx.dissent

        # max_rounds=1, current_round=1 → COMPLETE available
        # (not converged but no rounds remaining)
        assert sm.can_transition(ConsensusState.COMPLETE)
        sm.transition(ConsensusState.COMPLETE)
        assert sm.state == ConsensusState.COMPLETE

    async def test_multi_round_commit_to_propose(self) -> None:
        """COMMIT -> PROPOSE (new round) when not converged and rounds remain."""
        ctx = _make_ctx(max_rounds=3)
        sm = ConsensusStateMachine(ctx)

        # Round 1
        sm.transition(ConsensusState.PROPOSE)
        ctx.proposal = "Use PostgreSQL"
        ctx.proposal_model = "mock:proposer"
        sm.transition(ConsensusState.CHALLENGE)
        ctx.challenges = [ChallengeResult("mock:c1", "Issue found")]
        sm.transition(ConsensusState.REVISE)
        ctx.revision = "Use SQLite"
        ctx.revision_model = "mock:proposer"
        sm.transition(ConsensusState.COMMIT)

        await handle_commit(ctx)

        assert ctx.decision == "Use SQLite"

        # Can go to PROPOSE for another round (not converged, rounds remain)
        assert sm.can_transition(ConsensusState.PROPOSE)
        sm.transition(ConsensusState.PROPOSE)
        assert ctx.current_round == 2


# ── DB round-trip ────────────────────────────────────────────────


class TestCommitPersistence:
    async def test_decision_db_round_trip(self, db_session: AsyncSession) -> None:
        """Verify handle_commit output persists correctly via save_decision."""
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(db_session)

        # Create thread + turn
        thread = await repo.create_thread("What database to use?")
        turn = await repo.create_turn(thread.id, round_number=1, state="commit")

        # Run handle_commit
        ctx = _commit_ctx()
        await handle_commit(ctx)

        # Persist via repository
        await repo.save_decision(
            turn_id=turn.id,
            thread_id=thread.id,
            content=ctx.decision or "",
            confidence=ctx.confidence,
            dissent=ctx.dissent,
        )
        await db_session.commit()

        # Reload and verify
        decisions = await repo.get_decisions(thread.id)
        assert len(decisions) == 1
        loaded = decisions[0]
        assert loaded.content == ctx.decision
        assert loaded.confidence == ctx.confidence
        assert loaded.dissent == ctx.dissent
        assert loaded.turn_id == turn.id
        assert loaded.thread_id == thread.id
