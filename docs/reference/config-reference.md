# Config Reference

Complete reference for all configuration fields in duh's TOML config files.

## `[general]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_rounds` | int | `3` | Maximum consensus rounds per query (1-10). |
| `decomposer_model` | str | `""` | Model for question decomposition (reserved for future use). |
| `summary_model` | str | `""` | Model for generating summaries. Uses cheapest model by input cost if empty. |
| `stream_output` | bool | `true` | Stream model responses incrementally. |

## `[database]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `url` | str | `"sqlite+aiosqlite:///~/.local/share/duh/duh.db"` | SQLAlchemy async database URL. `~` is expanded to the home directory. Parent directories are created automatically for SQLite. |

## `[cost]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `warn_threshold` | float | `1.00` | Display a warning when cumulative cost exceeds this value (USD). |
| `hard_limit` | float | `10.00` | Stop execution when cumulative cost exceeds this value (USD). Set to `0` to disable. |
| `show_running_cost` | bool | `true` | Display running cost after each consensus round. |

## `[providers.<name>]`

Provider configuration is a dictionary keyed by provider name. Default providers are `anthropic` and `openai`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Whether this provider is active. |
| `api_key` | str \| null | `null` | API key (set directly -- not recommended, use `api_key_env`). |
| `api_key_env` | str \| null | Varies | Environment variable name to read the API key from. Default: `"ANTHROPIC_API_KEY"` for anthropic, `"OPENAI_API_KEY"` for openai. |
| `base_url` | str \| null | `null` | Custom API base URL (for Ollama, LM Studio, Azure, etc.). |
| `default_model` | str \| null | `null` | Reserved for future use. |
| `models` | list[str] | `[]` | Reserved for future use. |
| `display_name` | str \| null | `null` | Reserved for future use. |

## `[consensus]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `panel` | list[str] | `[]` | Reserved for future use. |
| `proposer_strategy` | str | `"round_robin"` | Strategy for selecting the proposer model. |
| `challenge_types` | list[str] | `["flaw", "alternative", "risk", "devils_advocate"]` | Types of challenges to generate. |
| `min_challengers` | int | `2` | Minimum number of challenger models per round. |

## `[logging]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `level` | str | `"INFO"` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `file` | str | `""` | Path to log file. Empty = stderr only. |
| `structured` | bool | `false` | Use structured (JSON) log format. |

## Config file locations

Loaded in this order (later overrides earlier):

1. Built-in defaults (values in the Default column above)
2. User config: `~/.config/duh/config.toml`
3. Project config: `./duh.toml`
4. `$DUH_CONFIG` environment variable
5. `--config` CLI option
6. Programmatic overrides (library use)

See [Configuration](../getting-started/configuration.md) for merge behavior details.
