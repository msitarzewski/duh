# 150215_sqlalchemy-models

## Objective
Implement SQLAlchemy models for conversation memory — Layer 1 (operational) and Layer 2 (institutional: Decision).

## Outcome
- 262 tests passing (+36 new)
- Ruff clean, mypy strict clean (18 source files)
- Build: successful

## Files Modified
- `src/duh/memory/models.py` — **NEW** — Base + 6 ORM models (165 lines)
- `src/duh/memory/__init__.py` — Re-export models
- `alembic/env.py` — Wired `target_metadata = Base.metadata`
- `tests/unit/test_models.py` — **NEW** — 36 tests (491 lines)

## New File Justification
`models.py` defines ORM models — distinct from the empty `__init__.py` placeholder. Cannot extend any existing file.

## Models
- **Thread** — Conversation/consensus session (question, status, timestamps)
- **Turn** — One consensus round (thread_id FK, round_number, state)
- **Contribution** — Single model's output (turn_id FK, model_ref, role, content, tokens, cost, latency)
- **TurnSummary** — LLM summary of a turn (turn_id FK unique, summary, model_ref)
- **ThreadSummary** — LLM summary of a thread (thread_id FK unique, summary, model_ref)
- **Decision** — Committed decision (turn_id FK unique, thread_id FK, content, confidence, dissent)

## Design Decisions
- UUID string PKs (String(36)) — SQLite compatible, no native UUID needed
- `from __future__ import annotations` — works with SQLAlchemy 2.0 Mapped style
- `viewonly=True` on Thread.decisions — avoids cascade conflicts (deletions flow through Turn)
- Cascade chain: Thread → Turn → (Contribution, TurnSummary, Decision) via delete-orphan
- FK enforcement via PRAGMA in test fixture (SQLite doesn't enforce by default)
- `order_by="Turn.round_number"` on Thread.turns for natural ordering

## Indexes
- `ix_threads_status`, `ix_threads_created_at` — thread filtering/sorting
- `ix_turns_thread_round` — composite unique (thread_id + round_number)
- turn_id index on Contribution, model_ref index on Contribution
- thread_id index on Decision, thread_id index on Turn

## Patterns Applied
- SQLAlchemy 2.0 Mapped annotation style (no legacy Column())
- DeclarativeBase (modern, no need for declarative_base() factory)
- async_sessionmaker + aiosqlite for async test fixture

## Integration Points
- Memory repository (task 11) will use these models for CRUD
- Consensus state machine (task 12+) creates Thread/Turn/Contribution/Decision records
- CLI `recall`/`threads`/`show` commands query these models
- Alembic can now generate migrations from Base.metadata
