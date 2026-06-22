# 260622_incremental-persistence

## Objective
Replace the fragile "write everything once at COMPLETE" persistence with
durable, incremental per-round persistence, and unify all three entry points
(CLI, WebSocket, REST) onto one shared path. (PR #16 persist portion, PR #17.)

## Problem
Every path built the full thread in memory and did a single write at the end.
A crash mid-run lost the entire consensus. Three separate implementations
existed (`ws._persist_consensus`, `cli.persist_consensus`, `ask._persist_result`
— the last a "lite" path that saved only the decision).

## Outcome
- **New `src/duh/memory/persist.py`** with `IncrementalPersister`:
  - `start(question) → thread_id` — create the thread as `status="active"` up front
  - `persist_round(RoundResult)` — write that round's turn + contributions
    (+ citations) + decision, each in its own committed transaction
  - `finalize(overview, followups, usage)` — flip to `complete`, attach summary/
    followups/usage
  - plus a `persist_consensus(...)` convenience that does start → rounds → finalize
- A crash in round 2 of 3 now leaves a real `active` thread with 2 rounds, not nothing.
- `ConsensusContext.snapshot_round()` (extracted from `_archive_round`) lets the
  loop persist a finished round before it's archived to `round_history`.
- **WebSocket** streams a `thread_started` event with the real thread ID up front,
  so the client can deep-link mid-run.
- **REST `/api/ask` unified (PR #17)**: now persists the *full* debate via the
  same `IncrementalPersister` (was the lite decision-only path). `_run_consensus`
  gained an additive `on_thread_created` callback so REST surfaces the thread ID
  without changing the 8-tuple return (the other 7 callers untouched). The dead
  `_persist_result` was removed.
- The old `ws._persist_consensus` and `cli.persist_consensus` now delegate to the
  one shared module (DRY — net negative lines in the affected files).

## Files
- Created: `src/duh/memory/persist.py`, `tests/unit/test_persist.py`
- Modified: `src/duh/consensus/machine.py` (`snapshot_round`), `src/duh/cli/app.py`,
  `src/duh/api/routes/ws.py`, `src/duh/api/routes/ask.py`, `tests/unit/test_api_ask.py`

## Patterns
- Persister methods each open their own session and commit independently → a
  persisted round survives a later crash.
- Final DB state is identical to the old single-write path, just written
  progressively — so state-asserting tests stayed green.
- Scope note: REST `/api/ask` is now on the full incremental path; CLI and WS too.

## Outcome Metrics
1663 → 1675 Python tests across the work (6 new persistence tests), mypy + ruff
clean. Live-validated.
