# 150215_configuration

## Objective
v0.1 Task 4: Configuration loading with TOML + Pydantic validation.

## Outcome
- 79/79 unit tests passing (31 new + 48 existing)
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (13 source files)
- Format: clean

## Files Created/Modified
- `src/duh/config/schema.py` — 7 Pydantic models for config validation
- `src/duh/config/loader.py` — TOML loading, file discovery, deep merge, env var resolution
- `src/duh/config/__init__.py` — Re-exports
- `tests/unit/test_config.py` — 31 tests (defaults, validation, TOML loading, env vars, file discovery)

## Config Schema
- `DuhConfig` — top-level, contains all sections
- `GeneralConfig` — max_rounds, decomposer/summary models, stream_output
- `DatabaseConfig` — SQLAlchemy URL
- `CostConfig` — warn_threshold, hard_limit, show_running_cost
- `ProviderConfig` — enabled, api_key/api_key_env, base_url, models
- `ConsensusConfig` — panel, proposer_strategy, challenge_types, min_challengers
- `LoggingConfig` — level, file, structured

## Config Loading
- File discovery: `~/.config/duh/config.toml` < `./duh.toml` < `$DUH_CONFIG`
- XDG_CONFIG_HOME respected
- Deep merge (nested dicts merge, scalars override)
- `load_config(path=, overrides=)` for explicit path and programmatic overrides
- API keys resolved from env vars via `api_key_env` field
- All errors raised as `ConfigError`

## Patterns Applied
- `tmp-systems-architecture.md#7` — Configuration format specification
- `tomllib` (stdlib 3.11+) for TOML parsing
- Pydantic `model_validate()` for dict -> validated config
