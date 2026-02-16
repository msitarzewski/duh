# Local Models

Run duh with local models for privacy, offline use, or free operation. duh connects to any OpenAI-compatible API via the `base_url` config option.

## Why local models?

- **Privacy** -- Your data never leaves your machine
- **Offline** -- Works without internet access
- **Free** -- No per-token costs (local models report $0.00/Mtok)
- **Mixed mode** -- Use a cloud model for proposing and local models for challenging

## Ollama

[Ollama](https://ollama.ai) is the easiest way to run local models.

### 1. Install Ollama

```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh
```

### 2. Pull a model

```bash
ollama pull llama3.1:70b
```

### 3. Start the Ollama server

```bash
ollama serve
```

Ollama serves an OpenAI-compatible API at `http://localhost:11434/v1`.

### 4. Configure duh

```toml
[providers.openai]
base_url = "http://localhost:11434/v1"
```

!!! note "API key not required"
    When `base_url` is set and no `api_key` is provided, the OpenAI provider automatically uses a placeholder key. Local endpoints don't need authentication.

### 5. Verify

```bash
duh models
```

You should see your Ollama models listed under the `openai` provider.

## LM Studio

[LM Studio](https://lmstudio.ai) provides a graphical interface for running local models.

### 1. Install LM Studio

Download from [lmstudio.ai](https://lmstudio.ai) and install.

### 2. Load a model

Open LM Studio, download a model from the built-in catalog, and load it.

### 3. Start the server

In LM Studio, go to the "Server" tab and click "Start Server". Default port: 1234.

### 4. Configure duh

```toml
[providers.openai]
base_url = "http://localhost:1234/v1"
```

## Mixed mode: cloud + local

The most cost-effective setup uses a powerful cloud model for proposing and free local models for challenging:

```toml
# Cloud provider for proposing (strongest model proposes)
[providers.anthropic]
api_key_env = "ANTHROPIC_API_KEY"

# Local provider for challenging (free)
[providers.openai]
base_url = "http://localhost:11434/v1"
```

In this setup:

- Claude (highest output cost) is automatically selected as proposer
- Ollama models (zero cost) serve as challengers
- You get cross-model diversity at minimal cost

!!! tip "Best of both worlds"
    This gives you the quality of a frontier model's proposal with the cost savings of local challengers. Challenges don't need to be from the strongest model -- they just need to find genuine flaws.

## Limitations

Local models may have:

- **Smaller context windows** -- Many local models support 4K-8K tokens vs 200K+ for cloud models
- **Slower inference** -- Depends on your hardware (GPU vs CPU)
- **Lower quality challenges** -- Smaller models may produce weaker or more sycophantic challenges
- **No streaming metadata** -- Some local servers don't report token usage accurately

## Connecting from Docker

If running duh in Docker and Ollama on the host:

```toml
[providers.openai]
base_url = "http://host.docker.internal:11434/v1"
```

`host.docker.internal` resolves to the host machine's IP from inside Docker containers (macOS and Windows). On Linux, use `--network host` or the host's actual IP.

## Next steps

- [Providers and Models](../concepts/providers-and-models.md) -- How providers work
- [Cost Management](../concepts/cost-management.md) -- Local models and cost tracking
