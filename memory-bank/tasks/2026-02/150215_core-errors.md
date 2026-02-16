# 150215_core-errors

## Objective
v0.1 Task 2: Create core error hierarchy and base types used by all modules.

## Outcome
- 21/21 unit tests passing (17 new + 4 smoke)
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (10 source files)
- Format: clean

## Files Created/Modified
- `src/duh/core/errors.py` — 11 exception classes in hierarchy
- `src/duh/core/__init__.py` — Re-exports all error classes
- `tests/unit/test_errors.py` — 17 tests (hierarchy, attributes, formatting, catch-all)

## Error Hierarchy
```
DuhError
├── ProviderError(provider_id, message)
│   ├── ProviderAuthError
│   ├── ProviderRateLimitError(retry_after)
│   ├── ProviderTimeoutError
│   ├── ProviderOverloadedError
│   └── ModelNotFoundError
├── ConsensusError
│   ├── InsufficientModelsError
│   └── CostLimitExceededError(limit, current)
├── ConfigError
└── StorageError
```

## Patterns Applied
- `tmp-systems-architecture.md#8` — Error hierarchy specification
- Renamed `MemoryError` -> `StorageError` to avoid shadowing Python built-in

## Architectural Decisions
- `StorageError` instead of `MemoryError`: Python built-in `MemoryError` is for out-of-memory conditions. Naming ours `StorageError` avoids confusion and accidental catches.
