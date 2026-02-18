"""Consensus state machine — states, context, transitions, guards.

Pure logic module. No IO (no provider calls, no DB writes).
Handlers (tasks 13-16) perform actual work; this module manages
valid transitions and context mutation.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from duh.core.errors import ConsensusError

if TYPE_CHECKING:
    from collections.abc import Sequence


class ConsensusState(enum.Enum):
    """States in the consensus protocol."""

    IDLE = "idle"
    DECOMPOSE = "decompose"
    PROPOSE = "propose"
    CHALLENGE = "challenge"
    REVISE = "revise"
    COMMIT = "commit"
    COMPLETE = "complete"
    FAILED = "failed"


# ── Data classes ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class ChallengeResult:
    """A single model's challenge to the proposal."""

    model_ref: str
    content: str
    sycophantic: bool = False
    framing: str = ""


@dataclass(frozen=True, slots=True)
class RoundResult:
    """Archived summary of one complete consensus round."""

    round_number: int
    proposal: str
    proposal_model: str
    challenges: tuple[ChallengeResult, ...]
    revision: str
    decision: str
    confidence: float
    rigor: float = 0.0
    dissent: str | None = None


@dataclass(frozen=True, slots=True)
class SubtaskSpec:
    """Specification for a single subtask in a decomposed question."""

    label: str
    description: str
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ConsensusContext:
    """Mutable state for one consensus session.

    Created once per thread, mutated by the state machine as
    handlers complete their work.
    """

    thread_id: str
    question: str
    max_rounds: int = 3

    # Current state
    state: ConsensusState = ConsensusState.IDLE
    current_round: int = 0

    # Current round working data (cleared between rounds)
    proposal: str | None = None
    proposal_model: str | None = None
    challenges: list[ChallengeResult] = field(default_factory=list)
    revision: str | None = None
    revision_model: str | None = None
    decision: str | None = None
    confidence: float = 0.0
    rigor: float = 0.0
    dissent: str | None = None
    converged: bool = False

    # History
    round_history: list[RoundResult] = field(default_factory=list)

    # Decomposition (set by DECOMPOSE handler)
    subtasks: list[SubtaskSpec] = field(default_factory=list)

    # Taxonomy (set by COMMIT handler if classification enabled)
    taxonomy: dict[str, str] | None = None

    # Tool usage log (set by handlers when tool_registry is provided)
    tool_calls_log: list[dict[str, str]] = field(default_factory=list)

    # Error
    error: str | None = None

    def _clear_round_data(self) -> None:
        """Reset working data for a new round."""
        self.proposal = None
        self.proposal_model = None
        self.challenges = []
        self.revision = None
        self.revision_model = None
        self.decision = None
        self.confidence = 0.0
        self.rigor = 0.0
        self.dissent = None
        self.converged = False

    def _archive_round(self) -> None:
        """Archive current round data to history."""
        self.round_history.append(
            RoundResult(
                round_number=self.current_round,
                proposal=self.proposal or "",
                proposal_model=self.proposal_model or "",
                challenges=tuple(self.challenges),
                revision=self.revision or "",
                decision=self.decision or "",
                confidence=self.confidence,
                rigor=self.rigor,
                dissent=self.dissent,
            )
        )


# ── State machine ─────────────────────────────────────────────

# Transitions allowed from non-terminal states.
# FAILED can be reached from any non-terminal state (handled separately).
_VALID_TRANSITIONS: dict[ConsensusState, frozenset[ConsensusState]] = {
    ConsensusState.IDLE: frozenset({ConsensusState.PROPOSE, ConsensusState.DECOMPOSE}),
    ConsensusState.DECOMPOSE: frozenset({ConsensusState.PROPOSE}),
    ConsensusState.PROPOSE: frozenset({ConsensusState.CHALLENGE}),
    ConsensusState.CHALLENGE: frozenset({ConsensusState.REVISE}),
    ConsensusState.REVISE: frozenset({ConsensusState.COMMIT}),
    ConsensusState.COMMIT: frozenset({ConsensusState.PROPOSE, ConsensusState.COMPLETE}),
    ConsensusState.COMPLETE: frozenset(),
    ConsensusState.FAILED: frozenset(),
}

_TERMINAL_STATES: frozenset[ConsensusState] = frozenset(
    {ConsensusState.COMPLETE, ConsensusState.FAILED}
)


class ConsensusStateMachine:
    """Manages consensus state transitions with guard validation.

    Pure logic — no IO. Validates that transitions are legal and
    that guard conditions are met, then mutates the context.
    """

    def __init__(self, context: ConsensusContext) -> None:
        self._ctx = context

    @property
    def context(self) -> ConsensusContext:
        """The consensus context managed by this machine."""
        return self._ctx

    @property
    def state(self) -> ConsensusState:
        """Current state."""
        return self._ctx.state

    @property
    def is_terminal(self) -> bool:
        """Whether the machine is in a terminal state."""
        return self._ctx.state in _TERMINAL_STATES

    def can_transition(self, to: ConsensusState) -> bool:
        """Check if a transition is valid without raising."""
        if self._ctx.state in _TERMINAL_STATES:
            return False
        if to == ConsensusState.FAILED:
            return True
        if to not in _VALID_TRANSITIONS.get(self._ctx.state, frozenset()):
            return False
        return self._check_guard(to) is None

    def transition(self, to: ConsensusState) -> None:
        """Execute a state transition with guard validation.

        Raises:
            ConsensusError: If the transition is invalid or a guard
                condition is not met.
        """
        self._validate_transition(to)
        self._apply_transition(to)

    def fail(self, error: str) -> None:
        """Transition to FAILED state with an error message.

        Raises:
            ConsensusError: If already in a terminal state.
        """
        self.transition(ConsensusState.FAILED)
        self._ctx.error = error

    # ── Internals ─────────────────────────────────────────────

    def _validate_transition(self, to: ConsensusState) -> None:
        """Raise ConsensusError if the transition is not allowed."""
        current = self._ctx.state

        if current in _TERMINAL_STATES:
            msg = f"Cannot transition from terminal state {current.value}"
            raise ConsensusError(msg)

        # FAILED is always reachable from non-terminal states
        if to == ConsensusState.FAILED:
            return

        valid = _VALID_TRANSITIONS.get(current, frozenset())
        if to not in valid:
            msg = f"Invalid transition: {current.value} -> {to.value}"
            raise ConsensusError(msg)

        guard_error = self._check_guard(to)
        if guard_error is not None:
            raise ConsensusError(guard_error)

    def _check_guard(self, to: ConsensusState) -> str | None:
        """Return an error message if a guard condition fails, else None."""
        ctx = self._ctx

        if to == ConsensusState.DECOMPOSE:
            if not ctx.question.strip():
                return "Cannot decompose: question is empty"

        elif to == ConsensusState.PROPOSE and ctx.state in {
            ConsensusState.IDLE,
            ConsensusState.DECOMPOSE,
        }:
            if not ctx.question.strip():
                return "Cannot propose: question is empty"

        elif to == ConsensusState.PROPOSE and ctx.state == ConsensusState.COMMIT:
            if ctx.converged:
                return "Cannot start new round: consensus already converged"
            if ctx.current_round >= ctx.max_rounds:
                return f"Cannot start new round: max rounds ({ctx.max_rounds}) reached"

        elif to == ConsensusState.CHALLENGE:
            if ctx.proposal is None:
                return "Cannot challenge: no proposal set"

        elif to == ConsensusState.REVISE:
            if not ctx.challenges:
                return "Cannot revise: no challenges received"

        elif to == ConsensusState.COMMIT:
            if ctx.revision is None:
                return "Cannot commit: no revision set"

        elif (
            to == ConsensusState.COMPLETE
            and ctx.state == ConsensusState.COMMIT
            and not ctx.converged
            and ctx.current_round < ctx.max_rounds
        ):
            return "Cannot complete: not converged and rounds remaining"

        return None

    def _apply_transition(self, to: ConsensusState) -> None:
        """Mutate context for the transition."""
        current = self._ctx.state

        if to == ConsensusState.PROPOSE and current in {
            ConsensusState.IDLE,
            ConsensusState.DECOMPOSE,
        }:
            self._ctx.current_round = 1
            self._ctx._clear_round_data()

        elif to == ConsensusState.PROPOSE and current == ConsensusState.COMMIT:
            self._ctx._archive_round()
            self._ctx.current_round += 1
            self._ctx._clear_round_data()

        elif to == ConsensusState.COMPLETE:
            self._ctx._archive_round()

        self._ctx.state = to

    def valid_transitions(self) -> Sequence[ConsensusState]:
        """Return the list of currently valid transitions."""
        if self._ctx.state in _TERMINAL_STATES:
            return []
        candidates = list(_VALID_TRANSITIONS.get(self._ctx.state, frozenset()))
        # Always include FAILED for non-terminal
        if ConsensusState.FAILED not in candidates:
            candidates.append(ConsensusState.FAILED)
        return [t for t in candidates if self.can_transition(t)]
