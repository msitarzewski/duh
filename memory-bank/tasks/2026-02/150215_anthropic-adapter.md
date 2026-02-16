# 150215_anthropic-adapter

## Objective
v0.1 Task 6: Create Anthropic (Claude) provider adapter.

## Outcome
- 140/140 unit tests passing (27 new + 113 existing)
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (14 source files)
- Format: clean

## Files Created/Modified
- `src/duh/providers/anthropic.py` — AnthropicProvider + error mapping + message building
- `tests/unit/test_providers_anthropic.py` — 27 tests (mocked SDK client)

## AnthropicProvider Features
- Implements ModelProvider protocol
- `list_models()` — returns 3 known Claude models (Opus 4.6, Sonnet 4.5, Haiku 4.5)
- `send()` — full request/response with latency tracking, cache token extraction
- `stream()` — async generator yielding StreamChunks, final chunk has usage
- `health_check()` — lightweight ping with haiku
- Accepts injected `client` for testing (dependency injection)

## Error Mapping
- AuthenticationError -> ProviderAuthError
- RateLimitError -> ProviderRateLimitError (with retry-after header parsing)
- APITimeoutError -> ProviderTimeoutError
- InternalServerError -> ProviderOverloadedError
- NotFoundError -> ModelNotFoundError
- Unknown APIError -> ProviderOverloadedError (fallback)

## Message Building
- `_build_messages()` splits PromptMessages into Anthropic's system + messages format
- System messages extracted separately (Anthropic uses `system` parameter, not messages array)

## Notes
- Streaming uses `getattr(event.delta, "text", "")` to handle union type (TextDelta | InputJSONDelta | etc.) cleanly for mypy strict
- `contextlib.suppress(ValueError)` for retry-after header parsing per ruff SIM105
- Base `anthropic.APIError` has different constructor than `APIStatusError` subclasses (takes `request` not `response`)
