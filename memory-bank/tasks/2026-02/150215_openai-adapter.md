# 150215_openai-adapter

## Objective
v0.1 Task 7: Create OpenAI provider adapter covering GPT + Ollama via base_url.

## Outcome
- 172/172 unit tests passing (32 new + 140 existing)
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (15 source files)
- Format: clean

## Files Created/Modified
- `src/duh/providers/openai.py` — OpenAIProvider + error mapping + message building
- `tests/unit/test_providers_openai.py` — 32 tests (mocked SDK client)
- `src/duh/providers/anthropic.py` — Fixed pricing and max output tokens to match current official rates

## OpenAIProvider Features
- Implements ModelProvider protocol
- `list_models()` — returns 3 known models (GPT-5.2, GPT-5 mini, o3)
- `send()` — full request/response with latency tracking
- `stream()` — async generator with `stream_options={"include_usage": True}` for usage in final chunk
- `health_check()` — lightweight ping with gpt-5-mini
- Accepts injected `client` for testing (dependency injection)
- `base_url` constructor param for Ollama/Azure/LM Studio/vLLM
- Auto-sets placeholder API key for local endpoints (no OPENAI_API_KEY needed)

## Error Mapping
- AuthenticationError -> ProviderAuthError
- RateLimitError -> ProviderRateLimitError (with retry-after header parsing)
- APITimeoutError -> ProviderTimeoutError
- InternalServerError -> ProviderOverloadedError
- NotFoundError -> ModelNotFoundError
- Unknown APIError -> ProviderOverloadedError (fallback)

## Message Building
- `_build_messages()` passes all messages (including system) directly in the array
- Simpler than Anthropic's split — OpenAI accepts system role in messages

## Key Differences from Anthropic Adapter
- `chat.completions.create()` instead of `messages.create()`
- `stop` param instead of `stop_sequences`
- `response.choices[0].message.content` / `.usage.prompt_tokens` / `.completion_tokens`
- Streaming via `stream=True` returns async iterable directly (no context manager)
- `stream_options={"include_usage": True}` for usage data in final chunk

## Model Pricing Update (both providers)
- Anthropic: Opus 4.6 $5/$25 (was $15/$75), Haiku 4.5 $1/$5 (was $0.80/$4), max output tokens updated
- OpenAI: GPT-5.2 $1.75/$14, GPT-5 mini $0.25/$2, o3 $2/$8

## Notes
- OpenAI SDK overloads on `stream` param — pass `stream=True` as keyword (not in dict) for correct type resolution
- OpenAI `APITimeoutError` inherits from `APIConnectionError`, not `APIStatusError` — different branch than Anthropic
- For local endpoints (Ollama), `api_key="not-required"` satisfies SDK requirement without needing env var
