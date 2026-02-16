# 150215_provider-manager

## Objective
Implement the provider manager — central registry for provider adapters with model discovery, routing by model_ref, and cost tracking.

## Outcome
- 226 tests passing (+25 new)
- Ruff clean, mypy strict clean (17 source files)
- Build: successful

## Files Modified
- `src/duh/providers/manager.py` — **NEW** — ProviderManager class (133 lines)
- `src/duh/providers/__init__.py` — Re-export ProviderManager
- `tests/unit/test_provider_manager.py` — **NEW** — 25 tests (258 lines)

## New File Justification
`manager.py` is a cross-provider orchestration layer. Cannot extend individual adapter files (`anthropic.py`, `openai.py`) or `base.py` (protocol definitions only). The manager aggregates across all providers — fundamentally different responsibility.

## API Surface
- `ProviderManager(cost_hard_limit=0.0)` — constructor
- `await register(provider)` — register + index models (raises ValueError on duplicate)
- `unregister(provider_id)` — remove provider + its models (raises KeyError if missing)
- `list_all_models()` → `list[ModelInfo]` — aggregate across all providers
- `get_model_info(model_ref)` → `ModelInfo` — lookup by `provider_id:model_id`
- `get_provider(model_ref)` → `(ModelProvider, model_id)` — routing
- `record_usage(model_info, usage)` → `float` — cost accumulation, raises CostLimitExceededError
- `total_cost` / `cost_by_provider` / `reset_cost()` — cost introspection

## Patterns Applied
- Extends `errors.py` error hierarchy (ModelNotFoundError, CostLimitExceededError)
- Uses `base.py` data classes (ModelInfo.model_ref, TokenUsage)
- Tests use MockProvider from `tests/fixtures/providers.py`
- `cost_by_provider` returns a copy (defensive)

## Integration Points
- Consensus engine (task 12+) will use `get_provider(model_ref)` to route calls
- CLI `models` command will use `list_all_models()` for display
- CLI `cost` command will use `total_cost` / `cost_by_provider`
- Config loader (task 4) provides `CostConfig.hard_limit` for constructor
