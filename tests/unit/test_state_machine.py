"""Tests for ConsensusStateMachine: transitions, guards, context mutation."""

from __future__ import annotations

import pytest

from duh.consensus.machine import (
    ChallengeResult,
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
    RoundResult,
)
from duh.core.errors import ConsensusError

# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context with sensible defaults."""
    defaults: dict[str, object] = {
        "thread_id": "t-1",
        "question": "What is AI?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _advance_to_propose(sm: ConsensusStateMachine) -> None:
    """Move from IDLE to PROPOSE."""
    sm.transition(ConsensusState.PROPOSE)


def _advance_to_challenge(sm: ConsensusStateMachine) -> None:
    """Move from IDLE through PROPOSE to CHALLENGE."""
    _advance_to_propose(sm)
    sm.context.proposal = "AI is a field of computer science."
    sm.context.proposal_model = "anthropic:opus"
    sm.transition(ConsensusState.CHALLENGE)


def _advance_to_revise(sm: ConsensusStateMachine) -> None:
    """Move from IDLE through CHALLENGE to REVISE."""
    _advance_to_challenge(sm)
    sm.context.challenges = [
        ChallengeResult(model_ref="openai:gpt-5.2", content="Too narrow"),
    ]
    sm.transition(ConsensusState.REVISE)


def _advance_to_commit(sm: ConsensusStateMachine) -> None:
    """Move from IDLE through REVISE to COMMIT."""
    _advance_to_revise(sm)
    sm.context.revision = "AI encompasses many approaches."
    sm.context.revision_model = "anthropic:opus"
    sm.transition(ConsensusState.COMMIT)


# ── ConsensusState enum ─────────────────────────────────────────


class TestConsensusState:
    def test_all_states_exist(self) -> None:
        names = {s.name for s in ConsensusState}
        assert names == {
            "IDLE",
            "DECOMPOSE",
            "PROPOSE",
            "CHALLENGE",
            "REVISE",
            "COMMIT",
            "COMPLETE",
            "FAILED",
        }

    def test_state_values_are_lowercase(self) -> None:
        for state in ConsensusState:
            assert state.value == state.name.lower()


# ── Data classes ─────────────────────────────────────────────────


class TestChallengeResult:
    def test_creation(self) -> None:
        cr = ChallengeResult(model_ref="openai:gpt-5.2", content="Disagree")
        assert cr.model_ref == "openai:gpt-5.2"
        assert cr.content == "Disagree"

    def test_frozen(self) -> None:
        cr = ChallengeResult(model_ref="m", content="c")
        with pytest.raises(AttributeError):
            cr.content = "new"  # type: ignore[misc]


class TestRoundResult:
    def test_creation(self) -> None:
        rr = RoundResult(
            round_number=1,
            proposal="P",
            proposal_model="anthropic:opus",
            challenges=(ChallengeResult(model_ref="openai:gpt-5.2", content="C"),),
            revision="R",
            decision="D",
            confidence=0.85,
            dissent="Minority view",
        )
        assert rr.round_number == 1
        assert len(rr.challenges) == 1
        assert rr.dissent == "Minority view"

    def test_frozen(self) -> None:
        rr = RoundResult(
            round_number=1,
            proposal="P",
            proposal_model="m",
            challenges=(),
            revision="R",
            decision="D",
            confidence=0.8,
        )
        with pytest.raises(AttributeError):
            rr.decision = "new"  # type: ignore[misc]

    def test_dissent_defaults_to_none(self) -> None:
        rr = RoundResult(
            round_number=1,
            proposal="P",
            proposal_model="m",
            challenges=(),
            revision="R",
            decision="D",
            confidence=0.8,
        )
        assert rr.dissent is None


# ── ConsensusContext ─────────────────────────────────────────────


class TestConsensusContext:
    def test_defaults(self) -> None:
        ctx = _make_ctx()
        assert ctx.state == ConsensusState.IDLE
        assert ctx.current_round == 0
        assert ctx.max_rounds == 3
        assert ctx.proposal is None
        assert ctx.challenges == []
        assert ctx.round_history == []
        assert ctx.error is None

    def test_clear_round_data(self) -> None:
        ctx = _make_ctx()
        ctx.proposal = "something"
        ctx.proposal_model = "m"
        ctx.challenges = [ChallengeResult("m", "c")]
        ctx.revision = "rev"
        ctx.revision_model = "m"
        ctx.decision = "dec"
        ctx.confidence = 0.9
        ctx.dissent = "d"
        ctx.converged = True

        ctx._clear_round_data()

        assert ctx.proposal is None
        assert ctx.proposal_model is None
        assert ctx.challenges == []
        assert ctx.revision is None
        assert ctx.revision_model is None
        assert ctx.decision is None
        assert ctx.confidence == 0.0
        assert ctx.dissent is None
        assert ctx.converged is False

    def test_archive_round(self) -> None:
        ctx = _make_ctx()
        ctx.current_round = 1
        ctx.proposal = "P"
        ctx.proposal_model = "anthropic:opus"
        ctx.challenges = [ChallengeResult("openai:gpt-5.2", "C")]
        ctx.revision = "R"
        ctx.decision = "D"
        ctx.confidence = 0.85
        ctx.dissent = "dissent"

        ctx._archive_round()

        assert len(ctx.round_history) == 1
        rr = ctx.round_history[0]
        assert rr.round_number == 1
        assert rr.proposal == "P"
        assert rr.proposal_model == "anthropic:opus"
        assert len(rr.challenges) == 1
        assert rr.revision == "R"
        assert rr.decision == "D"
        assert rr.confidence == pytest.approx(0.85)
        assert rr.dissent == "dissent"


# ── Valid transitions ────────────────────────────────────────────


class TestValidTransitions:
    def test_idle_to_propose(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        sm.transition(ConsensusState.PROPOSE)
        assert sm.state == ConsensusState.PROPOSE

    def test_propose_to_challenge(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_propose(sm)
        sm.context.proposal = "Answer"
        sm.transition(ConsensusState.CHALLENGE)
        assert sm.state == ConsensusState.CHALLENGE

    def test_challenge_to_revise(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_challenge(sm)
        sm.context.challenges = [ChallengeResult("m", "c")]
        sm.transition(ConsensusState.REVISE)
        assert sm.state == ConsensusState.REVISE

    def test_revise_to_commit(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_revise(sm)
        sm.context.revision = "Revised answer"
        sm.transition(ConsensusState.COMMIT)
        assert sm.state == ConsensusState.COMMIT

    def test_commit_to_propose_new_round(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=3))
        _advance_to_commit(sm)
        assert sm.context.current_round == 1
        sm.transition(ConsensusState.PROPOSE)
        assert sm.state == ConsensusState.PROPOSE
        assert sm.context.current_round == 2

    def test_commit_to_complete_converged(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_commit(sm)
        sm.context.converged = True
        sm.transition(ConsensusState.COMPLETE)
        assert sm.state == ConsensusState.COMPLETE

    def test_commit_to_complete_max_rounds(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=1))
        _advance_to_commit(sm)
        sm.transition(ConsensusState.COMPLETE)
        assert sm.state == ConsensusState.COMPLETE


# ── Invalid transitions ──────────────────────────────────────────


class TestInvalidTransitions:
    @pytest.mark.parametrize(
        ("from_state", "to_state"),
        [
            (ConsensusState.IDLE, ConsensusState.CHALLENGE),
            (ConsensusState.IDLE, ConsensusState.REVISE),
            (ConsensusState.IDLE, ConsensusState.COMMIT),
            (ConsensusState.IDLE, ConsensusState.COMPLETE),
            (ConsensusState.PROPOSE, ConsensusState.IDLE),
            (ConsensusState.PROPOSE, ConsensusState.REVISE),
            (ConsensusState.PROPOSE, ConsensusState.COMMIT),
            (ConsensusState.PROPOSE, ConsensusState.COMPLETE),
            (ConsensusState.PROPOSE, ConsensusState.PROPOSE),
            (ConsensusState.CHALLENGE, ConsensusState.IDLE),
            (ConsensusState.CHALLENGE, ConsensusState.PROPOSE),
            (ConsensusState.CHALLENGE, ConsensusState.COMMIT),
            (ConsensusState.CHALLENGE, ConsensusState.COMPLETE),
            (ConsensusState.CHALLENGE, ConsensusState.CHALLENGE),
            (ConsensusState.REVISE, ConsensusState.IDLE),
            (ConsensusState.REVISE, ConsensusState.PROPOSE),
            (ConsensusState.REVISE, ConsensusState.CHALLENGE),
            (ConsensusState.REVISE, ConsensusState.COMPLETE),
            (ConsensusState.REVISE, ConsensusState.REVISE),
            (ConsensusState.COMMIT, ConsensusState.IDLE),
            (ConsensusState.COMMIT, ConsensusState.CHALLENGE),
            (ConsensusState.COMMIT, ConsensusState.REVISE),
            (ConsensusState.COMMIT, ConsensusState.COMMIT),
            (ConsensusState.DECOMPOSE, ConsensusState.IDLE),
            (ConsensusState.DECOMPOSE, ConsensusState.CHALLENGE),
            (ConsensusState.DECOMPOSE, ConsensusState.REVISE),
            (ConsensusState.DECOMPOSE, ConsensusState.COMMIT),
            (ConsensusState.DECOMPOSE, ConsensusState.COMPLETE),
            (ConsensusState.DECOMPOSE, ConsensusState.DECOMPOSE),
            (ConsensusState.PROPOSE, ConsensusState.DECOMPOSE),
            (ConsensusState.CHALLENGE, ConsensusState.DECOMPOSE),
            (ConsensusState.REVISE, ConsensusState.DECOMPOSE),
            (ConsensusState.COMMIT, ConsensusState.DECOMPOSE),
        ],
    )
    def test_invalid_transition_raises(
        self, from_state: ConsensusState, to_state: ConsensusState
    ) -> None:
        ctx = _make_ctx()
        ctx.state = from_state
        # Set minimal data so guards don't mask the transition error
        ctx.current_round = 1
        ctx.proposal = "P"
        ctx.challenges = [ChallengeResult("m", "c")]
        ctx.revision = "R"
        sm = ConsensusStateMachine(ctx)
        with pytest.raises(ConsensusError, match="Invalid transition"):
            sm.transition(to_state)


# ── Terminal states ──────────────────────────────────────────────


class TestTerminalStates:
    def test_complete_is_terminal(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_commit(sm)
        sm.context.converged = True
        sm.transition(ConsensusState.COMPLETE)
        assert sm.is_terminal
        with pytest.raises(ConsensusError, match="terminal state"):
            sm.transition(ConsensusState.PROPOSE)

    def test_failed_is_terminal(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_propose(sm)
        sm.fail("Something broke")
        assert sm.is_terminal
        assert sm.context.error == "Something broke"
        with pytest.raises(ConsensusError, match="terminal state"):
            sm.transition(ConsensusState.PROPOSE)

    def test_cannot_transition_from_complete(self) -> None:
        ctx = _make_ctx()
        ctx.state = ConsensusState.COMPLETE
        sm = ConsensusStateMachine(ctx)
        assert sm.is_terminal
        assert not sm.can_transition(ConsensusState.PROPOSE)
        assert not sm.can_transition(ConsensusState.FAILED)

    def test_cannot_transition_from_failed(self) -> None:
        ctx = _make_ctx()
        ctx.state = ConsensusState.FAILED
        sm = ConsensusStateMachine(ctx)
        assert sm.is_terminal
        assert not sm.can_transition(ConsensusState.PROPOSE)


# ── FAILED from any non-terminal ─────────────────────────────────


class TestFailedTransition:
    @pytest.mark.parametrize(
        "from_state",
        [
            ConsensusState.IDLE,
            ConsensusState.DECOMPOSE,
            ConsensusState.PROPOSE,
            ConsensusState.CHALLENGE,
            ConsensusState.REVISE,
            ConsensusState.COMMIT,
        ],
    )
    def test_can_fail_from_any_non_terminal(self, from_state: ConsensusState) -> None:
        ctx = _make_ctx()
        ctx.state = from_state
        ctx.current_round = 1
        sm = ConsensusStateMachine(ctx)
        sm.fail("error")
        assert sm.state == ConsensusState.FAILED
        assert ctx.error == "error"


# ── Guard conditions ─────────────────────────────────────────────


class TestGuardConditions:
    def test_idle_to_propose_empty_question(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(question=""))
        with pytest.raises(ConsensusError, match="question is empty"):
            sm.transition(ConsensusState.PROPOSE)

    def test_idle_to_propose_whitespace_question(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(question="   "))
        with pytest.raises(ConsensusError, match="question is empty"):
            sm.transition(ConsensusState.PROPOSE)

    def test_propose_to_challenge_no_proposal(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_propose(sm)
        # Don't set proposal
        with pytest.raises(ConsensusError, match="no proposal set"):
            sm.transition(ConsensusState.CHALLENGE)

    def test_challenge_to_revise_no_challenges(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_challenge(sm)
        # challenges is empty by default after transition
        assert sm.context.challenges == []
        with pytest.raises(ConsensusError, match="no challenges received"):
            sm.transition(ConsensusState.REVISE)

    def test_revise_to_commit_no_revision(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_revise(sm)
        # Don't set revision
        with pytest.raises(ConsensusError, match="no revision set"):
            sm.transition(ConsensusState.COMMIT)

    def test_commit_to_propose_already_converged(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_commit(sm)
        sm.context.converged = True
        with pytest.raises(ConsensusError, match="already converged"):
            sm.transition(ConsensusState.PROPOSE)

    def test_commit_to_propose_max_rounds_reached(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=1))
        _advance_to_commit(sm)
        with pytest.raises(ConsensusError, match=r"max rounds.*reached"):
            sm.transition(ConsensusState.PROPOSE)

    def test_commit_to_complete_not_converged_rounds_remaining(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=3))
        _advance_to_commit(sm)
        # Not converged, round 1 of 3
        with pytest.raises(ConsensusError, match="not converged"):
            sm.transition(ConsensusState.COMPLETE)


# ── Context mutation on transition ───────────────────────────────


class TestContextMutation:
    def test_idle_to_propose_sets_round_1(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        assert sm.context.current_round == 0
        sm.transition(ConsensusState.PROPOSE)
        assert sm.context.current_round == 1

    def test_idle_to_propose_clears_data(self) -> None:
        ctx = _make_ctx()
        ctx.proposal = "stale"
        ctx.challenges = [ChallengeResult("m", "c")]
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.PROPOSE)
        assert ctx.proposal is None
        assert ctx.challenges == []

    def test_commit_to_propose_archives_and_increments(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=3))
        _advance_to_commit(sm)
        sm.context.decision = "First decision"
        sm.context.confidence = 0.7

        sm.transition(ConsensusState.PROPOSE)

        assert sm.context.current_round == 2
        assert len(sm.context.round_history) == 1
        assert sm.context.round_history[0].round_number == 1
        # Working data cleared
        assert sm.context.proposal is None
        assert sm.context.challenges == []

    def test_commit_to_complete_archives_round(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=1))
        _advance_to_commit(sm)
        sm.context.decision = "Final"
        sm.context.confidence = 0.9

        sm.transition(ConsensusState.COMPLETE)

        assert len(sm.context.round_history) == 1
        assert sm.context.round_history[0].decision == "Final"

    def test_multi_round_history(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=3))

        # Round 1
        _advance_to_commit(sm)
        sm.context.decision = "R1"
        sm.transition(ConsensusState.PROPOSE)

        # Round 2
        sm.context.proposal = "P2"
        sm.context.proposal_model = "m"
        sm.transition(ConsensusState.CHALLENGE)
        sm.context.challenges = [ChallengeResult("m", "c2")]
        sm.transition(ConsensusState.REVISE)
        sm.context.revision = "Rev2"
        sm.transition(ConsensusState.COMMIT)
        sm.context.decision = "R2"
        sm.context.converged = True
        sm.transition(ConsensusState.COMPLETE)

        assert len(sm.context.round_history) == 2
        assert sm.context.round_history[0].round_number == 1
        assert sm.context.round_history[1].round_number == 2
        assert sm.context.round_history[1].decision == "R2"


# ── can_transition ───────────────────────────────────────────────


class TestCanTransition:
    def test_can_transition_true(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        assert sm.can_transition(ConsensusState.PROPOSE) is True

    def test_can_transition_false_invalid(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        assert sm.can_transition(ConsensusState.COMMIT) is False

    def test_can_transition_false_guard_failure(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(question=""))
        assert sm.can_transition(ConsensusState.PROPOSE) is False

    def test_can_transition_failed_always_true_non_terminal(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        assert sm.can_transition(ConsensusState.FAILED) is True

    def test_can_transition_false_from_terminal(self) -> None:
        ctx = _make_ctx()
        ctx.state = ConsensusState.COMPLETE
        sm = ConsensusStateMachine(ctx)
        assert sm.can_transition(ConsensusState.FAILED) is False


# ── valid_transitions ────────────────────────────────────────────


class TestValidTransitionsList:
    def test_idle_valid_transitions(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        valid = sm.valid_transitions()
        assert ConsensusState.PROPOSE in valid
        assert ConsensusState.DECOMPOSE in valid
        assert ConsensusState.FAILED in valid

    def test_commit_valid_transitions_not_converged(self) -> None:
        sm = ConsensusStateMachine(_make_ctx(max_rounds=3))
        _advance_to_commit(sm)
        valid = sm.valid_transitions()
        assert ConsensusState.PROPOSE in valid
        assert ConsensusState.FAILED in valid
        # Can't complete — not converged, rounds remaining
        assert ConsensusState.COMPLETE not in valid

    def test_commit_valid_transitions_converged(self) -> None:
        sm = ConsensusStateMachine(_make_ctx())
        _advance_to_commit(sm)
        sm.context.converged = True
        valid = sm.valid_transitions()
        assert ConsensusState.COMPLETE in valid
        # Can't start new round — converged
        assert ConsensusState.PROPOSE not in valid

    def test_terminal_no_valid_transitions(self) -> None:
        ctx = _make_ctx()
        ctx.state = ConsensusState.COMPLETE
        sm = ConsensusStateMachine(ctx)
        assert sm.valid_transitions() == []
