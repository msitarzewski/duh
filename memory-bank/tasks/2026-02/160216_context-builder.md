# 160216_context-builder

## Objective
Implement the context builder — assemble thread summary and past decisions into a token-budgeted context string for model prompts.

## Outcome
- 491 tests passing (+16 new)
- Ruff clean, mypy strict clean (23 source files)
- Build: successful

## Files Modified
- `src/duh/memory/context.py` — **NEW** — context builder module (89 lines)
- `src/duh/memory/__init__.py` — Re-export `build_context`, `estimate_tokens`
- `tests/unit/test_context_builder.py` — **NEW** — 16 tests (207 lines)

## New File Justification
`context.py`: Context builder reads from DB models (Thread, Decision, ThreadSummary) — a memory concern, not a consensus handler concern. Handlers work with in-memory ConsensusContext; context builder works with persisted DB objects. Separate module keeps the boundary clean.

## API Surface

### `estimate_tokens(text) -> int`
- Simple ~4 chars/token heuristic (no external tokenizer dependency)
- Returns 0 for empty, minimum 1 for non-empty

### `build_context(thread, decisions, *, max_tokens=2000) -> str`
- Pure function — caller provides data, no DB access
- Priority: thread summary first, then decisions (most recent first)
- Decisions formatted with confidence percentage and optional dissent
- Truncates to stay within token budget
- Returns empty string if no history

## Design Decisions
- Pure functions (no DB access) — testable with fake objects, no DB fixture needed for most tests
- Token estimation via char heuristic — avoids tiktoken/tokenizer dependency for v0.1
- Conservative 4 chars/token to avoid exceeding real limits
- Thread summary gets priority over decisions (most relevant context)
- Decisions include confidence and dissent for model awareness of certainty

## Patterns Applied
- TYPE_CHECKING block for DB model imports
- Fake model classes in tests for pure-function testing (no DB overhead)
- DB integration test uses real ORM objects via shared `db_session` fixture

## Integration Points
- Caller fetches Thread via `MemoryRepository.get_thread()` (task 11)
- Caller fetches decisions via `MemoryRepository.get_decisions()` (task 11)
- Output string injected into model prompts by consensus engine (task 20)
- Summary generator (task 19) creates ThreadSummary consumed by this builder
