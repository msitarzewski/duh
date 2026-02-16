"""Tests for convergence detection: similarity, threshold, early stop."""

from __future__ import annotations

from duh.consensus.convergence import (
    _challenge_similarity,
    _rounds_converged,
    check_convergence,
)
from duh.consensus.machine import (
    ChallengeResult,
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
    RoundResult,
)

# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    defaults: dict[str, object] = {
        "thread_id": "t-1",
        "question": "What database should we use?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _make_round(
    round_number: int,
    challenges: list[ChallengeResult],
) -> RoundResult:
    return RoundResult(
        round_number=round_number,
        proposal="proposal",
        proposal_model="mock:proposer",
        challenges=tuple(challenges),
        revision="revision",
        decision="decision",
        confidence=1.0,
    )


# ── Challenge similarity ─────────────────────────────────────────


class TestChallengeSimilarity:
    def test_identical_strings(self) -> None:
        assert _challenge_similarity("hello world", "hello world") == 1.0

    def test_no_overlap(self) -> None:
        assert _challenge_similarity("foo bar", "baz qux") == 0.0

    def test_partial_overlap(self) -> None:
        sim = _challenge_similarity(
            "PostgreSQL adds complexity",
            "PostgreSQL adds operational overhead",
        )
        # shared: {"postgresql", "adds"} = 2
        # union: {"postgresql", "adds", "complexity", "operational", "overhead"} = 5
        assert sim == 2 / 5

    def test_case_insensitive(self) -> None:
        assert _challenge_similarity("Hello World", "hello world") == 1.0

    def test_both_empty(self) -> None:
        assert _challenge_similarity("", "") == 1.0

    def test_one_empty(self) -> None:
        assert _challenge_similarity("hello", "") == 0.0


# ── Rounds converged ─────────────────────────────────────────────


class TestRoundsConverged:
    def test_similar_challenges_converge(self) -> None:
        current = [
            ChallengeResult("m1", "PostgreSQL adds complexity"),
        ]
        previous = [
            ChallengeResult("m2", "PostgreSQL adds operational complexity"),
        ]
        # high overlap → converged
        assert _rounds_converged(current, previous, threshold=0.5)

    def test_different_challenges_do_not_converge(self) -> None:
        current = [
            ChallengeResult("m1", "The API design is inconsistent"),
        ]
        previous = [
            ChallengeResult("m2", "PostgreSQL adds complexity"),
        ]
        assert not _rounds_converged(current, previous, threshold=0.5)

    def test_threshold_edge_equal(self) -> None:
        """Exactly at threshold should converge."""
        current = [ChallengeResult("m1", "a b c d")]
        previous = [ChallengeResult("m2", "a b c d")]
        # similarity = 1.0, threshold = 1.0
        assert _rounds_converged(current, previous, threshold=1.0)

    def test_threshold_edge_below(self) -> None:
        current = [ChallengeResult("m1", "a b")]
        previous = [ChallengeResult("m2", "a c")]
        # shared: {"a"}, union: {"a", "b", "c"} → 1/3 ≈ 0.33
        assert not _rounds_converged(current, previous, threshold=0.5)

    def test_empty_current_does_not_converge(self) -> None:
        previous = [ChallengeResult("m1", "issue")]
        assert not _rounds_converged([], previous)

    def test_empty_previous_does_not_converge(self) -> None:
        current = [ChallengeResult("m1", "issue")]
        assert not _rounds_converged(current, [])

    def test_multiple_challenges_averaged(self) -> None:
        """Average of max similarities across all current challenges."""
        current = [
            ChallengeResult("m1", "PostgreSQL adds complexity"),
            ChallengeResult("m2", "totally new unrelated issue"),
        ]
        previous = [
            ChallengeResult("m3", "PostgreSQL adds operational complexity"),
        ]
        # challenge 1 vs prev: high similarity
        # challenge 2 vs prev: low similarity
        # average: moderate → not converged at 0.7
        assert not _rounds_converged(current, previous, threshold=0.7)


# ── check_convergence ────────────────────────────────────────────


class TestCheckConvergence:
    def test_round_1_returns_false(self) -> None:
        """No history to compare against → not converged."""
        ctx = _make_ctx()
        ctx.challenges = [ChallengeResult("m1", "some issue")]
        assert check_convergence(ctx) is False

    def test_round_2_similar_converges(self) -> None:
        ctx = _make_ctx()
        ctx.round_history = [
            _make_round(1, [ChallengeResult("m1", "PostgreSQL adds complexity")]),
        ]
        ctx.challenges = [
            ChallengeResult("m2", "PostgreSQL adds operational complexity"),
        ]
        assert check_convergence(ctx, threshold=0.5) is True

    def test_round_2_different_does_not_converge(self) -> None:
        ctx = _make_ctx()
        ctx.round_history = [
            _make_round(1, [ChallengeResult("m1", "PostgreSQL adds complexity")]),
        ]
        ctx.challenges = [
            ChallengeResult("m2", "The API design is inconsistent"),
        ]
        assert check_convergence(ctx) is False

    def test_sets_ctx_converged(self) -> None:
        ctx = _make_ctx()
        ctx.round_history = [
            _make_round(1, [ChallengeResult("m1", "same issue here")]),
        ]
        ctx.challenges = [ChallengeResult("m2", "same issue here")]
        assert not ctx.converged

        check_convergence(ctx)

        assert ctx.converged is True

    def test_does_not_set_converged_when_false(self) -> None:
        ctx = _make_ctx()
        ctx.round_history = [
            _make_round(1, [ChallengeResult("m1", "issue alpha")]),
        ]
        ctx.challenges = [ChallengeResult("m2", "totally different concern")]

        check_convergence(ctx)

        assert ctx.converged is False

    def test_high_threshold_harder_to_converge(self) -> None:
        ctx = _make_ctx()
        ctx.round_history = [
            _make_round(1, [ChallengeResult("m1", "a b c d e")]),
        ]
        ctx.challenges = [ChallengeResult("m2", "a b c x y")]
        # shared: {a, b, c} union: {a, b, c, d, e, x, y} → 3/7 ≈ 0.43
        assert check_convergence(ctx, threshold=0.3) is True
        ctx.converged = False  # reset
        assert check_convergence(ctx, threshold=0.5) is False

    def test_empty_current_challenges(self) -> None:
        ctx = _make_ctx()
        ctx.round_history = [
            _make_round(1, [ChallengeResult("m1", "issue")]),
        ]
        ctx.challenges = []
        assert check_convergence(ctx) is False

    def test_compares_most_recent_round(self) -> None:
        """Should compare against the last round, not earlier ones."""
        ctx = _make_ctx()
        ctx.round_history = [
            _make_round(1, [ChallengeResult("m1", "old unrelated issue")]),
            _make_round(2, [ChallengeResult("m2", "same concern here")]),
        ]
        ctx.challenges = [ChallengeResult("m3", "same concern here")]

        assert check_convergence(ctx) is True


# ── End-to-end with state machine ────────────────────────────────


class TestConvergenceEndToEnd:
    def test_convergence_triggers_complete(self) -> None:
        """Multi-round: round 2 converges → COMPLETE."""
        ctx = _make_ctx(max_rounds=3)
        sm = ConsensusStateMachine(ctx)

        # Round 1
        sm.transition(ConsensusState.PROPOSE)
        ctx.proposal = "Use PostgreSQL"
        ctx.proposal_model = "mock:proposer"
        sm.transition(ConsensusState.CHALLENGE)
        ctx.challenges = [
            ChallengeResult("mock:c1", "PostgreSQL adds complexity"),
        ]
        sm.transition(ConsensusState.REVISE)
        ctx.revision = "Use SQLite instead"
        ctx.revision_model = "mock:proposer"
        ctx.decision = ctx.revision
        ctx.confidence = 1.0
        sm.transition(ConsensusState.COMMIT)

        # Not converged yet (no history)
        assert not check_convergence(ctx)

        # Go to round 2
        sm.transition(ConsensusState.PROPOSE)
        ctx.proposal = "Use SQLite with migrations"
        ctx.proposal_model = "mock:proposer"
        sm.transition(ConsensusState.CHALLENGE)
        # Same challenge as round 1 → should converge
        ctx.challenges = [
            ChallengeResult("mock:c1", "PostgreSQL adds complexity"),
        ]
        sm.transition(ConsensusState.REVISE)
        ctx.revision = "Use SQLite with repo abstraction"
        ctx.revision_model = "mock:proposer"
        ctx.decision = ctx.revision
        ctx.confidence = 1.0
        sm.transition(ConsensusState.COMMIT)

        assert check_convergence(ctx) is True
        assert ctx.converged is True

        # Converged → can go to COMPLETE
        assert sm.can_transition(ConsensusState.COMPLETE)
        sm.transition(ConsensusState.COMPLETE)
        assert sm.state == ConsensusState.COMPLETE
