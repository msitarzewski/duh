# 160216_convergence-detection

## Objective
Implement convergence detection — cross-round challenge comparison using word-overlap similarity to trigger early stopping when challenges stabilize.

## Outcome
- 475 tests passing (+22 new)
- Ruff clean, mypy strict clean (22 source files)
- Build: successful

## Files Modified
- `src/duh/consensus/convergence.py` — **NEW** — convergence detection module (90 lines)
- `src/duh/consensus/__init__.py` — Re-export `check_convergence`
- `tests/unit/test_convergence.py` — **NEW** — 22 tests (228 lines)

## New File Justification
`convergence.py`: Cross-round analysis is conceptually distinct from single-phase handlers in `handlers.py` (530 lines). Convergence operates on `round_history` comparing challenges across rounds, not within a single phase. Separate module keeps concerns clean.

## API Surface

### `_challenge_similarity(a, b) -> float` (internal)
- Jaccard similarity on word sets (case-insensitive)
- Returns 0.0 (no overlap) to 1.0 (identical word sets)

### `_rounds_converged(current, previous, *, threshold=0.7) -> bool` (internal)
- For each current challenge, finds max similarity to any previous challenge
- Converged if average of max similarities >= threshold

### `check_convergence(ctx, *, threshold=0.7) -> bool`
- Public function called after handle_commit, before state machine transition
- Round 1: always False (no history to compare)
- Compares current challenges against most recent archived round
- Sets `ctx.converged = True` if convergence detected
- Returns convergence boolean

## Design Decisions
- Jaccard word-overlap chosen: simple, no external deps, good enough for "same issues" detection
- Threshold default 0.7: requires substantial overlap, not just incidental word sharing
- Compares only against most recent round (not all history) — most relevant signal
- Does not call any model — pure computation on existing challenge text
- Separate module from handlers.py — different concern (cross-round vs single-phase)

## Patterns Applied
- TYPE_CHECKING block for ChallengeResult and ConsensusContext imports
- Pure function pattern (no IO, no side effects beyond ctx.converged)
- Tests cover: similarity math, threshold edges, convergence logic, ctx mutation, e2e with state machine

## Integration Points
- Called after `handle_commit` (task 16) sets decision/confidence/dissent
- Sets `ctx.converged` which gates state machine's COMMIT→PROPOSE (blocked) and COMMIT→COMPLETE (allowed)
- Threshold is configurable per call — consensus engine (task 20) can tune it
