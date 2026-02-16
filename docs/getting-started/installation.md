# Installation

## Prerequisites

- **Python 3.11+**
- At least one API key: [Anthropic](https://console.anthropic.com/) or [OpenAI](https://platform.openai.com/)

## Install duh

=== "uv (recommended)"

    ```bash
    uv add duh
    ```

    Or install globally:

    ```bash
    uv tool install duh
    ```

=== "pip"

    ```bash
    pip install duh
    ```

=== "Docker"

    No Python installation needed. See the [Docker guide](../guides/docker.md) for full setup.

    ```bash
    docker compose run duh ask "your question"
    ```

## Set API keys

duh needs at least one provider API key. Set them as environment variables:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

!!! tip "Add to your shell profile"
    Add the export lines to `~/.bashrc`, `~/.zshrc`, or equivalent so they persist across sessions.

!!! warning "Both keys recommended"
    duh works best with multiple providers. Cross-model challenges (Claude vs GPT) produce stronger consensus than same-model self-critique.

## Verify installation

```bash
duh --version
duh models
```

The `models` command lists all available models grouped by provider. If you see models listed, you're ready to go.

!!! note "No models?"
    If `duh models` shows "No models available", check that your API keys are set correctly. See [Troubleshooting](../troubleshooting.md) for common issues.

## Next steps

- [Quickstart](quickstart.md) -- Run your first consensus query
- [Configuration](configuration.md) -- Customize duh's behavior
