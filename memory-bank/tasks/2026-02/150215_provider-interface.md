# 150215_provider-interface

## Objective
v0.1 Task 3: Create provider adapter interface and data classes.

## Outcome
- 48/48 unit tests passing (27 new + 21 existing)
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (11 source files)
- Format: clean

## Files Created/Modified
- `src/duh/providers/base.py` — 6 data classes + ModelProvider protocol
- `src/duh/providers/__init__.py` — Re-exports all public types
- `tests/unit/test_providers_base.py` — 27 tests (capabilities, data classes, protocol conformance)

## Data Classes
- `ModelCapability` — Flag enum: TEXT, STREAMING, TOOL_USE, VISION, JSON_MODE, SYSTEM_PROMPT
- `ModelInfo` — Frozen. Provider/model metadata, costs, capabilities. Added `model_ref` property.
- `TokenUsage` — Frozen. Token counts with cache fields. Added `total_tokens` property.
- `ModelResponse` — Mutable (content can be updated). Content, model info, usage, latency.
- `StreamChunk` — Frozen. Text chunk with optional final usage.
- `PromptMessage` — Frozen. Role + content.

## Protocol
`ModelProvider` — runtime_checkable Protocol with:
- `provider_id` property
- `list_models()` -> list[ModelInfo]
- `send(messages, model_id, **kwargs)` -> ModelResponse
- `stream(messages, model_id, **kwargs)` -> AsyncIterator[StreamChunk]
- `health_check()` -> bool

## Patterns Applied
- `tmp-systems-architecture.md#2` — Provider interface specification
- `tmp-systems-architecture.md:353-359` — Design rationale (frozen ModelInfo, send vs stream split)

## Notes
- `AsyncIterator` import moved to TYPE_CHECKING block per ruff TCH003 rule
- `raw_response` excluded from repr to avoid noise in logs
