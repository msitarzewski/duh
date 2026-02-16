# Configuration

duh uses TOML configuration files with a layered merge system. You can configure providers, cost limits, consensus behavior, and more.

## Config file locations

Configuration is loaded in this order (later overrides earlier):

1. **Built-in defaults** -- Sensible defaults from the Pydantic schema
2. **User config** -- `~/.config/duh/config.toml` (or `$XDG_CONFIG_HOME/duh/config.toml`)
3. **Project config** -- `./duh.toml` in the current directory
4. **`$DUH_CONFIG`** -- Explicit path via environment variable
5. **CLI `--config`** -- Path passed to any command
6. **Programmatic overrides** -- When using duh as a library

Each layer deep-merges into the previous. You only need to specify the values you want to change.

## Minimal config

Create `~/.config/duh/config.toml`:

```toml
[providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"

[providers.openai]
api_key_env = "OPENAI_API_KEY"
```

!!! tip "This is the default"
    duh ships with this exact config as defaults. If your API keys are set as environment variables, you don't need a config file at all.

## Full config example

```toml
[general]
max_rounds = 3           # Maximum consensus rounds (1-10)
stream_output = true     # Stream model responses

[database]
url = "sqlite+aiosqlite:///~/.local/share/duh/duh.db"

[cost]
warn_threshold = 1.00    # Warn when cumulative cost exceeds this (USD)
hard_limit = 10.00       # Stop when cumulative cost exceeds this (USD)
show_running_cost = true # Display cost after each round

[providers.anthropic]
enabled = true
api_key_env = "ANTHROPIC_API_KEY"
# api_key = "sk-ant-..."   # Or set directly (not recommended)

[providers.openai]
enabled = true
api_key_env = "OPENAI_API_KEY"
# base_url = "http://localhost:11434/v1"  # For Ollama / local models

[consensus]
min_challengers = 2
proposer_strategy = "round_robin"
challenge_types = ["flaw", "alternative", "risk", "devils_advocate"]

[logging]
level = "INFO"
structured = false
```

## Environment variables

Provider API keys are resolved from environment variables when `api_key_env` is set and `api_key` is not provided directly.

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_API_KEY` | Anthropic (Claude) API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `DUH_CONFIG` | Path to config file (overrides discovery) |
| `XDG_CONFIG_HOME` | Base directory for user config (default: `~/.config`) |

## Override config per command

Every command accepts `--config` to use a specific config file:

```bash
duh --config ./my-config.toml ask "question"
```

The `ask` command also accepts `--rounds` to override `max_rounds`:

```bash
duh ask --rounds 5 "question requiring deeper debate"
```

## Next steps

- [Config Reference](../reference/config-reference.md) -- Full schema with all fields, types, and defaults
- [Local Models](../guides/local-models.md) -- Configure Ollama via `base_url`
