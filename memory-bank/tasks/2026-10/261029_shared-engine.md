# 261029_shared-engine

## Objective
Consolidate consensus orchestration behind one typed public API, isolate execution-level usage and hard budgets, and preserve existing consumer contracts through incremental adapters.

## Outcome
- User approved implementation completion and rollout on 2026-10-29.
- Approved source revision: `0a4dc9ffd070897f5cc68e4b23730e5480ddbd79`.
- State: approved public source rollout complete. PR #25 is merged; public CI passed and the installed engine source hash/public exports match the immutable revision.
- Validation: 1,745 Python tests passed: 1,733 core tests and the 12 additional load tests. Mypy passed for 65 source files; Ruff and changed-file formatting passed.
- The public Docker image passed smoke checks on its advertised Python 3.11 runtime.
- Frontend source is unchanged by this batch. Coverage was not remeasured; existing test warnings remain. No live provider behavior is inferred from the offline regression suite.

## Files Modified and Integration Points
- `src/duh/consensus/engine.py:35`: immutable EngineOptions preserves explicit panel, proposer, challenger, round, search, and optional-output choices without mutating caller configuration.
- `src/duh/consensus/engine.py:64`: frozen typed result replaces internal tuple unpacking. Typed phase/challenge/round/completion events provide the public orchestration contract.
- `src/duh/consensus/engine.py:237`: the single consensus loop owns phase transitions, selected models, concurrent challenges, convergence, overview/follow-up generation, and execution totals. Awaited sinks provide backpressure and propagate failures.
- `src/duh/consensus/engine.py:422`: bounded async event iteration cancels and drains the owned worker when closed; fatal errors reach the consumer.
- `src/duh/cli/app.py:276`: retain the eight-element `_run_consensus` compatibility result while rendering typed events through the existing display.
- `src/duh/api/routes/ask.py:113`, `src/duh/api/routes/ws.py:120`, and `src/duh/mcp/server.py:103`: REST, WebSocket, and MCP consume the shared engine and preserve their existing response/message formats.
- `src/duh/memory/persist.py:37`: share the existing incremental persister adapter across public command and transport consumers. Thread-created callback failures propagate instead of being mistaken for optional database-start failures.
- `src/duh/consensus/scheduler.py:36`: subtasks use the same core, with separate measured child totals and the owning request's hard budget.
- `src/duh/providers/manager.py:165`: ContextVar scopes isolate independent executions. Child tasks inherit the active ledger; explicit child scopes also charge the parent. `record_usage` at line 218 enforces the outer hard limit and retains separate aggregate telemetry.
- `src/duh/cli/app.py:595`: refinement and every execution protocol share one event loop, manager, and budget, so preliminary spend appears in the full result and cannot reset the limit.
- `src/duh/config/schema.py:30` and `src/duh/consensus/handlers.py:515`: constrain configured framing keys and reject unsupported execution overrides before provider work.
- `src/duh/consensus/machine.py:37` and `src/duh/consensus/engine.py:50`: preserve repeated model/framing call identity through occurrence metadata. New rounds also clear prior taxonomy state.
- Existing provider-manager, API, command, scheduler, storage, state-machine, and MCP test files were extended; the new engine contract test exercises the new public API directly.

## Reuse Strategy
- Reused existing phase handlers, state machine, provider manager, incremental persister, displays, routes, and protocol implementations. Removed orchestration copies from consumers instead of creating another independent execution path.
- A public engine module is necessary because command and endpoint modules bind UI/transport responsibilities. Extending those modules as the reusable API would preserve those dependencies and duplicate-loop drift.
- Existing technical context, decisions, progress, quick-start, monthly log, and index are extended. A separate task record is required because this is a separately approved implementation batch; the earlier security task retains its historical scope and validation.

## Patterns Applied
- `memory-bank/techContext.md#shared-engine-and-run-scoped-usage-2026-10-29`
- `memory-bank/techContext.md#key-technical-patterns`
- `memory-bank/decisions.md#2026-10-29-one-public-engine-and-run-scoped-usage`

## Compatibility and Validation
- Legacy command tuple and existing WebSocket/HTTP response formats remain compatible; the typed public API is additive.
- Supported configured challenge keys are flaw, alternative, risk, and devils_advocate. Unknown keys now fail validation instead of silently producing a different prompt label.
- Aggregate usage remains explicitly available; execution-level totals and budgets do not include unrelated concurrent requests. Resetting active-run usage is rejected.
- Regression coverage includes simultaneous runs, inherited child-task usage, shared subtask budgets, full refinement costs, hard-limit failures, result immutability, callback aborts, iterator cleanup, occurrence metadata, and retained round history.
- Provider deadlines, fatal sibling cancellation, selected model panels, incremental writes, and existing optional protocol flows remain covered by the test suite.
- Migration convergence, provider/platform upgrades, package boundaries, frontend accessibility, and later delivery work remain separate.

## Artifacts and Rollout
- Approved source commit: `0a4dc9f`; review branch: `codex/recovery-engine`.
- Merged in [PR #25](https://github.com/msitarzewski/duh/pull/25), merge commit `3efe8ea4fb3f40cd071d1282ade2b608e7f855aa`. Installed source hash and public engine exports were verified against `0a4dc9ffd070897f5cc68e4b23730e5480ddbd79`. Package metadata remains unchanged; no new registry release was assigned.
- Prior task: [261029_security-foundation.md](./261029_security-foundation.md).
