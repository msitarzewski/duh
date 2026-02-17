# Config Reference

Complete reference for all configuration fields in duh's TOML config files.

## `[general]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_rounds` | int | `3` | Maximum consensus rounds per query (1-10). |
| `protocol` | str | `"consensus"` | Default decision protocol: `consensus`, `voting`, or `auto`. Override per-query with `--protocol`. |
| `decompose` | bool | `false` | Decompose questions into subtasks by default. Override per-query with `--decompose`. |
| `decomposer_model` | str | `""` | Model for question decomposition. Uses cheapest model by input cost if empty. |
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

Provider configuration is a dictionary keyed by provider name. Default providers are `anthropic`, `openai`, `google`, and `mistral`.

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

## `[tools]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable tool-augmented reasoning. Models can call tools during PROPOSE and CHALLENGE phases. Override per-query with `--tools` / `--no-tools`. |
| `max_rounds` | int | `5` | Maximum tool call iterations per phase. Prevents runaway tool loops. |

### `[tools.web_search]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `backend` | str | `"duckduckgo"` | Search backend. Currently supports `duckduckgo`. |
| `api_key` | str \| null | `null` | API key for the search backend (if required). |
| `max_results` | int | `5` | Maximum search results returned per query. |

### `[tools.code_execution]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable code execution tool. Requires explicit opt-in for safety. |
| `timeout` | int | `30` | Maximum execution time in seconds. |
| `max_output` | int | `10000` | Maximum output characters captured from execution. |

!!! warning "Code execution safety"
    Code execution runs in the local environment. Enable only when you trust the models' tool use. Consider using Docker for isolation.

## `[voting]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Enable voting protocol availability. |
| `aggregation` | str | `"majority"` | Aggregation strategy: `majority` (meta-judge picks best) or `weighted` (synthesis weighted by model capability). |

## `[decompose]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `max_subtasks` | int | `7` | Maximum number of subtasks per decomposition (range: 2-7). |
| `parallel` | bool | `true` | Execute independent subtasks in parallel. |

## `[taxonomy]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `false` | Auto-classify decisions with intent, category, and genus during COMMIT. |
| `model_ref` | str | `""` | Model to use for classification. Empty = cheapest available model. |

## `[api]`

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `host` | str | `"127.0.0.1"` | Host to bind the API server to. Use `"0.0.0.0"` to listen on all interfaces. |
| `port` | int | `8080` | Port to bind the API server to. |
| `cors_origins` | list[str] | `["http://localhost:3000"]` | Allowed CORS origins. |
| `rate_limit` | int | `60` | Max requests per API key per window. |
| `rate_limit_window` | int | `60` | Rate limit window in seconds. |

## Config file locations

Loaded in this order (later overrides earlier):

1. Built-in defaults (values in the Default column above)
2. User config: `~/.config/duh/config.toml`
3. Project config: `./duh.toml`
4. `$DUH_CONFIG` environment variable
5. `--config` CLI option
6. Programmatic overrides (library use)

See [Configuration](../getting-started/configuration.md) for merge behavior details.
