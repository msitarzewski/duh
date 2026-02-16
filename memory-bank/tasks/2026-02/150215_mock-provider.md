# 150215_mock-provider

## Objective
v0.1 Task 5: Create MockProvider and test fixtures for deterministic testing.

## Outcome
- 113/113 unit tests passing (34 new + 79 existing)
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (13 source files)
- Format: clean

## Files Created/Modified
- `tests/fixtures/providers.py` — MockProvider class
- `tests/fixtures/responses.py` — 4 canned response sets
- `tests/conftest.py` — Shared fixtures (mock_provider, make_model_info, make_usage)
- `tests/unit/test_mock_provider.py` — 34 tests

## MockProvider Features
- Satisfies `ModelProvider` protocol (runtime-checkable)
- Returns canned responses keyed by model_id
- Records all calls in `call_log` for assertion
- Configurable health (healthy=True/False)
- Streaming splits content into word-by-word chunks
- Final chunk has is_final=True with usage

## Canned Response Library
- `CONSENSUS_BASIC` — proposer, 2 challengers, reviser (PostgreSQL vs SQLite scenario)
- `CONSENSUS_AGREEMENT` — challengers validate proposal (Timsort scenario)
- `CONSENSUS_DISAGREEMENT` — challengers find real issues (microservices scenario)
- `MINIMAL` — 2 simple models for quick tests

## Conftest Fixtures
- `mock_provider` — MockProvider with CONSENSUS_BASIC responses
- `mock_provider_minimal` — MockProvider with MINIMAL responses
- `make_model_info` — Factory with sensible defaults + overrides
- `make_usage` — Factory with sensible defaults + overrides

## Notes
- `stream()` is an async generator (yields directly), not an awaitable returning an iterator
- Tests use `[c async for c in provider.stream(...)]` (no await)
