# Providers and Models

## What's a provider?

A provider is an adapter that connects duh to an LLM API. Each provider implements a common protocol (`ModelProvider`) that handles:

- Listing available models with metadata (context window, pricing, capabilities)
- Sending prompts and receiving responses
- Streaming responses chunk-by-chunk
- Health checks to verify credentials

duh ships with two built-in providers:

| Provider | API | Models |
|----------|-----|--------|
| **Anthropic** | `api.anthropic.com` | Claude Opus 4.6, Claude Sonnet 4.5, Claude Haiku 4.5 |
| **OpenAI** | `api.openai.com` | GPT-5.2, GPT-5 mini, o3 |

## Supported models

### Anthropic (Claude)

| Model | Context | Max Output | Input $/Mtok | Output $/Mtok |
|-------|---------|------------|-------------|---------------|
| Claude Opus 4.6 | 200K | 128K | $5.00 | $25.00 |
| Claude Sonnet 4.5 | 200K | 64K | $3.00 | $15.00 |
| Claude Haiku 4.5 | 200K | 64K | $1.00 | $5.00 |

### OpenAI (GPT)

| Model | Context | Max Output | Input $/Mtok | Output $/Mtok |
|-------|---------|------------|-------------|---------------|
| GPT-5.2 | 400K | 128K | $1.75 | $14.00 |
| GPT-5 mini | 400K | 128K | $0.25 | $2.00 |
| o3 | 200K | 100K | $2.00 | $8.00 |

## Model selection strategy

duh automatically selects models for each phase:

**Proposer selection**: The model with the highest output cost per million tokens is chosen as the proposer, using cost as a proxy for capability. With default models, this means Claude Opus 4.6 proposes.

**Challenger selection**: Models different from the proposer are preferred (cross-model challenges are more effective). Challengers are sorted by output cost (strongest first) and the top N are selected (default: 2). If not enough different models exist, the proposer model fills remaining slots for same-model ensemble.

**Reviser**: Always the same model that proposed, since it's revising its own work.

## Model capabilities

All built-in models support:

- **TEXT** -- Text generation
- **STREAMING** -- Incremental response delivery
- **SYSTEM_PROMPT** -- System message support
- **JSON_MODE** -- Structured JSON output

Additional capability flags exist for future use: **TOOL_USE** and **VISION**.

## OpenAI-compatible providers

The OpenAI provider supports any API that implements the OpenAI chat completions interface. This includes:

- **Ollama** -- Local models via `http://localhost:11434/v1`
- **LM Studio** -- Local models via `http://localhost:1234/v1`
- **vLLM** -- Self-hosted inference
- **Azure OpenAI** -- Microsoft's hosted OpenAI models
- **Any OpenAI-compatible API**

Configure via `base_url` in the provider config:

```toml
[providers.openai]
base_url = "http://localhost:11434/v1"
```

See the [Local Models guide](../guides/local-models.md) for detailed setup instructions.

## Model references

Throughout duh, models are identified by their **model reference** (`model_ref`): a `provider_id:model_id` string.

Examples:

- `anthropic:claude-opus-4-6`
- `openai:gpt-5.2`
- `openai:llama3.1:70b` (Ollama model via OpenAI provider)

Model references appear in CLI output, cost tracking, thread history, and the Python API.

## Next steps

- [Local Models](../guides/local-models.md) -- Set up Ollama or LM Studio
- [How Consensus Works](how-consensus-works.md) -- How models are used in the protocol
- [Cost Management](cost-management.md) -- Per-model cost tracking
