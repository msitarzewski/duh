# 160216_commit-handler

## Objective
Implement the COMMIT handler — decision extraction from revision, confidence scoring based on challenge quality, dissent preservation from genuine challenges.

## Outcome
- 453 tests passing (+21 new)
- Ruff clean, mypy strict clean (21 source files)
- Build: successful

## Files Modified
- `src/duh/consensus/handlers.py` — Extended with COMMIT functions (+60 lines)
- `src/duh/consensus/__init__.py` — Re-export `handle_commit`
- `tests/unit/test_commit_handler.py` — **NEW** — 21 tests (303 lines)

## New File Justification
Test file only. Handler code extends existing `handlers.py`.

## API Surface

### `_compute_confidence(challenges) -> float`
- Internal helper for confidence scoring
- `genuine_ratio = non_sycophantic / total`
- Returns 0.5 (all sycophantic / empty) to 1.0 (all genuine)

### `_extract_dissent(challenges) -> str | None`
- Internal helper for dissent preservation
- Collects non-sycophantic challenges with `[model_ref]: content` format
- Returns None if no genuine dissent

### `handle_commit(ctx) -> None`
- Validates COMMIT state and revision presence
- Sets `ctx.decision = ctx.revision` (revision IS the final answer)
- Computes `ctx.confidence` via `_compute_confidence`
- Extracts `ctx.dissent` via `_extract_dissent`
- Returns None (no model call, no ModelResponse)
- Raises ConsensusError if state/data invalid

## Design Decisions
- No model call needed — COMMIT is pure extraction and scoring
- Decision = revision (the revision incorporates all challenge feedback)
- Confidence heuristic: genuine challenge ratio maps to [0.5, 1.0] range
- Dissent preserves minority viewpoints even after revision addressed them
- Handler is async for consistency with other handlers (caller can await uniformly)
- Persistence is caller's responsibility (tested via DB round-trip test)

## Patterns Applied
- Same validate-then-mutate pattern as other handlers
- Handler does NOT transition state — caller owns transitions
- Tests cover: helpers, handler, e2e state machine flow, DB round-trip

## Integration Points
- Reads `ctx.revision` from handle_revise (task 15) and `ctx.challenges` from handle_challenge (task 14)
- Sets `ctx.decision`/`ctx.confidence`/`ctx.dissent` consumed by convergence detection (task 17)
- State machine COMMIT->PROPOSE and COMMIT->COMPLETE guards use these fields
- DB persistence via `MemoryRepository.save_decision()` (task 11)
