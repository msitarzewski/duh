# 150215_memory-repository

## Objective
Implement the memory repository — async CRUD, keyword search, thread listing over SQLAlchemy models.

## Outcome
- 292 tests passing (+30 new)
- Ruff clean, mypy strict clean (19 source files)
- Build: successful

## Files Modified
- `src/duh/memory/repository.py` — **NEW** — MemoryRepository class (197 lines)
- `src/duh/memory/__init__.py` — Re-export MemoryRepository
- `tests/conftest.py` — Added shared `db_session` fixture (in-memory SQLite + FK enforcement)
- `tests/unit/test_models.py` — Removed duplicate `db_session` fixture (now uses shared one)
- `tests/unit/test_repository.py` — **NEW** — 30 tests (414 lines)

## New File Justification
`repository.py` is the data access layer over the models — distinct concern from the ORM model definitions in `models.py`. Cannot extend models.py (which is pure schema).

## API Surface
- `MemoryRepository(session: AsyncSession)` — constructor, session injected
- `create_thread(question)` → Thread
- `get_thread(thread_id)` → Thread | None (eager loads turns, contributions, decisions, summaries)
- `list_threads(status?, limit, offset)` → list[Thread] (recency order)
- `delete_thread(thread_id)` → None (raises StorageError if not found)
- `create_turn(thread_id, round_number, state)` → Turn
- `get_turn(turn_id)` → Turn | None (eager loads contributions, decision, summary)
- `add_contribution(turn_id, model_ref, role, content, ...)` → Contribution
- `save_decision(turn_id, thread_id, content, confidence, dissent?)` → Decision
- `get_decisions(thread_id)` → list[Decision] (chronological)
- `save_turn_summary(turn_id, summary, model_ref)` → TurnSummary (create-or-update)
- `save_thread_summary(thread_id, summary, model_ref)` → ThreadSummary (create-or-update)
- `search(query, limit)` → list[Thread] (keyword across questions + decisions, case-insensitive, deduplicated)

## Design Decisions
- All mutating methods flush but do NOT commit — caller controls transaction boundaries
- `get_thread` and `get_turn` use `selectinload` for eager loading (required for async SQLAlchemy)
- `list_threads` does NOT eager load (metadata-only listing, caller uses `get_thread` for details)
- Summary save methods are upserts (check for existing, update or create)
- Search uses `LIKE` with `ilike` for case-insensitive keyword matching (v1.0 will use vector search)
- Search deduplicates via `.distinct()` when a thread matches both question and decision content

## Patterns Applied
- Repository pattern with injected session (no commit responsibility)
- `selectinload` for async-safe eager loading
- `StorageError` for not-found on delete (from `core/errors.py`)
- Shared `db_session` fixture in `tests/conftest.py` for reuse across test modules

## Integration Points
- Consensus engine (task 12+) uses repo for persisting turns, contributions, decisions
- CLI `ask` command creates threads, `recall` uses search, `threads`/`show` use listing/get
- Context builder (task 17) uses `get_thread` + `get_decisions` for assembling model context
- Summary generator (task 18) uses `save_turn_summary` / `save_thread_summary`
