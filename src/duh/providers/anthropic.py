"""Anthropic (Claude) provider adapter."""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

import anthropic

from duh.core.errors import (
    ModelNotFoundError,
    ProviderAuthError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    ModelResponse,
    StreamChunk,
    TokenUsage,
    ToolCallData,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from duh.providers.base import PromptMessage

PROVIDER_ID = "anthropic"

# Known Claude models with metadata.
# Updated as new models release; list_models() returns these.
_KNOWN_MODELS: list[dict[str, Any]] = [
    {
        "model_id": "claude-opus-4-6",
        "display_name": "Claude Opus 4.6",
        "context_window": 200_000,
        "max_output_tokens": 128_000,
        "input_cost_per_mtok": 5.0,
        "output_cost_per_mtok": 25.0,
    },
    {
        "model_id": "claude-sonnet-4-6",
        "display_name": "Claude Sonnet 4.6",
        "context_window": 200_000,
        "max_output_tokens": 64_000,
        "input_cost_per_mtok": 3.0,
        "output_cost_per_mtok": 15.0,
    },
    {
        "model_id": "claude-sonnet-4-5-20250929",
        "display_name": "Claude Sonnet 4.5",
        "context_window": 200_000,
        "max_output_tokens": 64_000,
        "input_cost_per_mtok": 3.0,
        "output_cost_per_mtok": 15.0,
    },
    {
        "model_id": "claude-haiku-4-5-20251001",
        "display_name": "Claude Haiku 4.5",
        "context_window": 200_000,
        "max_output_tokens": 64_000,
        "input_cost_per_mtok": 1.0,
        "output_cost_per_mtok": 5.0,
    },
]

_DEFAULT_CAPS = (
    ModelCapability.TEXT
    | ModelCapability.STREAMING
    | ModelCapability.SYSTEM_PROMPT
    | ModelCapability.JSON_MODE
)


def _map_error(e: anthropic.APIError) -> Exception:
    """Map Anthropic SDK errors to duh error hierarchy."""
    if isinstance(e, anthropic.AuthenticationError):
        return ProviderAuthError(PROVIDER_ID, str(e))
    if isinstance(e, anthropic.RateLimitError):
        retry_after = None
        if hasattr(e, "response") and e.response is not None:
            raw = e.response.headers.get("retry-after")
            if raw is not None:
                with contextlib.suppress(ValueError):
                    retry_after = float(raw)
        return ProviderRateLimitError(PROVIDER_ID, retry_after=retry_after)
    if isinstance(e, anthropic.APITimeoutError):
        return ProviderTimeoutError(PROVIDER_ID, str(e))
    if isinstance(e, anthropic.InternalServerError):
        return ProviderOverloadedError(PROVIDER_ID, str(e))
    if isinstance(e, anthropic.NotFoundError):
        return ModelNotFoundError(PROVIDER_ID, str(e))
    # Fallback for unknown API errors
    return ProviderOverloadedError(PROVIDER_ID, str(e))


def _build_messages(
    messages: list[PromptMessage],
) -> tuple[str | anthropic.NotGiven, list[dict[str, str]]]:
    """Split PromptMessages into Anthropic's system + messages format."""
    system: str | anthropic.NotGiven = anthropic.NOT_GIVEN
    api_messages: list[dict[str, str]] = []

    for msg in messages:
        if msg.role == "system":
            system = msg.content
        else:
            api_messages.append({"role": msg.role, "content": msg.content})

    return system, api_messages


class AnthropicProvider:
    """Provider adapter for Anthropic's Claude models."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: anthropic.AsyncAnthropic | None = None,
    ) -> None:
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key)

    @property
    def provider_id(self) -> str:
        return PROVIDER_ID

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                provider_id=PROVIDER_ID,
                model_id=m["model_id"],
                display_name=m["display_name"],
                capabilities=_DEFAULT_CAPS,
                context_window=m["context_window"],
                max_output_tokens=m["max_output_tokens"],
                input_cost_per_mtok=m["input_cost_per_mtok"],
                output_cost_per_mtok=m["output_cost_per_mtok"],
            )
            for m in _KNOWN_MODELS
        ]

    async def send(
        self,
        messages: list[PromptMessage],
        model_id: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
        response_format: str | None = None,
        tools: list[dict[str, object]] | None = None,
    ) -> ModelResponse:
        system, api_messages = _build_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": api_messages,
        }
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences
        if tools:
            kwargs["tools"] = tools

        start = time.monotonic()
        try:
            response = await self._client.messages.create(**kwargs)
        except anthropic.APIError as e:
            raise _map_error(e) from e

        latency_ms = (time.monotonic() - start) * 1000

        # Extract text content and tool use blocks
        content = ""
        tool_calls_data: list[ToolCallData] = []
        for block in response.content:
            if hasattr(block, "text"):
                content = block.text
            elif hasattr(block, "type") and block.type == "tool_use":
                import json

                tool_calls_data.append(
                    ToolCallData(
                        id=block.id,
                        name=block.name,
                        arguments=json.dumps(block.input),
                    )
                )

        usage = TokenUsage(
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0)
            or 0,
            cache_write_tokens=getattr(response.usage, "cache_creation_input_tokens", 0)
            or 0,
        )

        # Find matching ModelInfo for this model_id
        model_info = self._resolve_model_info(model_id)

        return ModelResponse(
            content=content,
            model_info=model_info,
            usage=usage,
            finish_reason=response.stop_reason or "stop",
            latency_ms=latency_ms,
            raw_response=response,
            tool_calls=tool_calls_data if tool_calls_data else None,
        )

    async def stream(
        self,
        messages: list[PromptMessage],
        model_id: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        system, api_messages = _build_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system,
            "messages": api_messages,
        }
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences

        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    if hasattr(event, "type") and event.type == "content_block_delta":
                        text = getattr(event.delta, "text", "")
                        if text:
                            yield StreamChunk(text=text)

                # After stream completes, get final message for usage
                final = await stream.get_final_message()
                usage = TokenUsage(
                    input_tokens=final.usage.input_tokens,
                    output_tokens=final.usage.output_tokens,
                    cache_read_tokens=getattr(final.usage, "cache_read_input_tokens", 0)
                    or 0,
                    cache_write_tokens=getattr(
                        final.usage, "cache_creation_input_tokens", 0
                    )
                    or 0,
                )
                yield StreamChunk(text="", is_final=True, usage=usage)

        except anthropic.APIError as e:
            raise _map_error(e) from e

    async def health_check(self) -> bool:
        try:
            # A lightweight call to verify credentials
            await self._client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],
            )
        except Exception:
            return False
        return True

    def _resolve_model_info(self, model_id: str) -> ModelInfo:
        """Look up ModelInfo for a model_id, or create a generic one."""
        for m in _KNOWN_MODELS:
            if m["model_id"] == model_id:
                return ModelInfo(
                    provider_id=PROVIDER_ID,
                    model_id=model_id,
                    display_name=m["display_name"],
                    capabilities=_DEFAULT_CAPS,
                    context_window=m["context_window"],
                    max_output_tokens=m["max_output_tokens"],
                    input_cost_per_mtok=m["input_cost_per_mtok"],
                    output_cost_per_mtok=m["output_cost_per_mtok"],
                )
        # Unknown model — return generic info
        return ModelInfo(
            provider_id=PROVIDER_ID,
            model_id=model_id,
            display_name=f"Claude ({model_id})",
            capabilities=_DEFAULT_CAPS,
            context_window=200_000,
            max_output_tokens=4096,
            input_cost_per_mtok=0.0,
            output_cost_per_mtok=0.0,
        )
