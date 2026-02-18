# Providers and Models

## What's a provider?

A provider is an adapter that connects duh to an LLM API. Each provider implements a common protocol (`ModelProvider`) that handles:

- Listing available models with metadata (context window, pricing, capabilities)
- Sending prompts and receiving responses
- Streaming responses chunk-by-chunk
- Health checks to verify credentials

duh ships with five built-in providers:

| Provider | API | Models |
|----------|-----|--------|
| **Anthropic** | `api.anthropic.com` | Claude Opus 4.6, Claude Sonnet 4.6, Claude Sonnet 4.5, Claude Haiku 4.5 |
| **OpenAI** | `api.openai.com` | GPT-5.2, GPT-5 mini, o3 |
| **Google** | `generativelanguage.googleapis.com` | Gemini 3 Pro Preview, Gemini 3 Flash Preview, Gemini 2.5 Flash |
| **Mistral** | `api.mistral.ai` | Mistral Large, Mistral Medium, Mistral Small, Codestral |
| **Perplexity** | `api.perplexity.ai` | Sonar Pro, Sonar (challenger-only) |

## Supported models

### Anthropic (Claude)

| Model | Context | Max Output | Input $/Mtok | Output $/Mtok |
|-------|---------|------------|-------------|---------------|
| Claude Opus 4.6 | 200K | 128K | $5.00 | $25.00 |
| Claude Sonnet 4.6 | 200K | 64K | $3.00 | $15.00 |
| Claude Sonnet 4.5 | 200K | 64K | $3.00 | $15.00 |
| Claude Haiku 4.5 | 200K | 64K | $1.00 | $5.00 |

### OpenAI (GPT)

| Model | Context | Max Output | Input $/Mtok | Output $/Mtok |
|-------|---------|------------|-------------|---------------|
| GPT-5.2 | 400K | 128K | $1.75 | $14.00 |
| GPT-5 mini | 400K | 128K | $0.25 | $2.00 |
| o3 | 200K | 100K | $2.00 | $8.00 |

### Google (Gemini)

| Model | Context | Max Output | Input $/Mtok | Output $/Mtok |
|-------|---------|------------|-------------|---------------|
| Gemini 3 Pro Preview | 1M | 65K | $2.00 | $12.00 |
| Gemini 3 Flash Preview | 1M | 65K | $0.50 | $3.00 |
| Gemini 2.5 Flash | 1M | 65K | $0.15 | $0.60 |

### Mistral

| Model | Context | Max Output | Input $/Mtok | Output $/Mtok |
|-------|---------|------------|-------------|---------------|
| Mistral Large | 128K | 32K | $2.00 | $6.00 |
| Mistral Medium | 128K | 32K | $2.70 | $8.10 |
| Mistral Small | 128K | 32K | $0.20 | $0.60 |
| Codestral | 256K | 32K | $0.30 | $0.90 |

### Perplexity (challenger-only)

All Perplexity models are search-grounded and marked as **challenger-only** -- they participate in the CHALLENGE phase but are never selected as proposers.

| Model | Context | Max Output | Input $/Mtok | Output $/Mtok |
|-------|---------|------------|-------------|---------------|
| Sonar Pro | 200K | 8K | $3.00 | $15.00 |
| Sonar | 128K | 8K | $1.00 | $1.00 |

## Model selection strategy

duh automatically selects models for each phase:

**Proposer selection**: The model with the highest output cost per million tokens is chosen as the proposer, using cost as a proxy for capability. Models marked as `proposer_eligible=False` (e.g. Perplexity's search-grounded models) are excluded from proposer selection. With default models, this means Claude Opus 4.6 proposes.

**Challenger selection**: Models different from the proposer are preferred (cross-model challenges are more effective). Challengers are sorted by output cost (strongest first) and the top N are selected (default: 2). If not enough different models exist, the proposer model fills remaining slots for same-model ensemble. All models (including challenger-only models) can participate as challengers.

**Reviser**: Always the same model that proposed, since it's revising its own work.

## Controlling model selection

You can control which models participate in consensus:

**Panel** -- Restrict to a subset of models. Only models in the panel are considered for both proposer and challenger roles:

```bash
duh ask --panel anthropic:claude-opus-4-6,openai:gpt-5.2 "Your question"
```

Or in config:

```toml
[consensus]
panel = ["anthropic:claude-opus-4-6", "openai:gpt-5.2", "google:gemini-3-pro-preview"]
```

**Proposer override** -- Force a specific model as proposer:

```bash
duh ask --proposer openai:gpt-5.2 "Your question"
```

**Challenger override** -- Force specific challenger models:

```bash
duh ask --challengers google:gemini-3-pro-preview,perplexity:sonar-pro "Your question"
```

These options are also available in the REST API and WebSocket interface.

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
