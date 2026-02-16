# 150215_consensus-state-machine

## Objective
Implement the consensus state machine — states enum, transitions, ConsensusContext dataclass, guard conditions.

## Outcome
- 363 tests passing (+71 new)
- Ruff clean, mypy strict clean (20 source files)
- Build: successful

## Files Modified
- `src/duh/consensus/machine.py` — **NEW** — ConsensusState enum, data classes, ConsensusStateMachine (282 lines)
- `src/duh/consensus/__init__.py` — Re-export all public API
- `tests/unit/test_state_machine.py` — **NEW** — 71 tests (460 lines)

## New File Justification
`machine.py` is the state machine for the consensus protocol — pure logic (no IO). Distinct from handlers (tasks 13-16) which perform actual model calls. Cannot extend `__init__.py` (re-exports only).

## API Surface

### ConsensusState (enum)
`IDLE`, `PROPOSE`, `CHALLENGE`, `REVISE`, `COMMIT`, `COMPLETE`, `FAILED`

### ChallengeResult (frozen dataclass)
`model_ref: str`, `content: str`

### RoundResult (frozen dataclass)
`round_number`, `proposal`, `proposal_model`, `challenges` (tuple), `revision`, `decision`, `confidence`, `dissent`

### ConsensusContext (mutable dataclass)
- Identity: `thread_id`, `question`, `max_rounds`
- State: `state`, `current_round`
- Working data: `proposal`, `proposal_model`, `challenges`, `revision`, `revision_model`, `decision`, `confidence`, `dissent`, `converged`
- History: `round_history: list[RoundResult]`
- Error: `error: str | None`

### ConsensusStateMachine
- `__init__(context)` — wraps a ConsensusContext
- `state` property — current ConsensusState
- `is_terminal` property — True if COMPLETE or FAILED
- `can_transition(to)` → bool — check without raising
- `transition(to)` — execute with guard validation, raises ConsensusError
- `fail(error)` — transition to FAILED with message
- `valid_transitions()` → list — currently valid targets

## Design Decisions
- Pure logic, no IO — handlers do actual work
- FAILED reachable from any non-terminal state
- COMPLETE and FAILED are terminal (no transitions out)
- Guard conditions enforce data presence before transitions
- Context mutation on transition: IDLE→PROPOSE sets round=1 and clears; COMMIT→PROPOSE archives + increments + clears; COMMIT→COMPLETE archives
- Round history stored as frozen RoundResult tuples for immutability

## Valid Transitions
```
IDLE → PROPOSE (guard: question non-empty)
PROPOSE → CHALLENGE (guard: proposal set)
CHALLENGE → REVISE (guard: challenges non-empty)
REVISE → COMMIT (guard: revision set)
COMMIT → PROPOSE (guard: not converged, rounds remaining)
COMMIT → COMPLETE (guard: converged OR max rounds reached)
Any non-terminal → FAILED (always allowed)
```

## Integration Points
- Handlers (tasks 13-16) call `transition()` after completing their work
- Turn.state column (`memory/models.py:74`) stores ConsensusState.value strings
- ConsensusContext.thread_id links to MemoryRepository for persistence
- ProviderManager routes model calls; state machine doesn't touch providers

## Patterns Applied
- State machine pattern with explicit transition map and guard conditions
- Frozen dataclasses for immutable archived data (ChallengeResult, RoundResult)
- Mutable context dataclass for working state
- ConsensusError from `core/errors.py` for all validation failures
