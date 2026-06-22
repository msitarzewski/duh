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
    Citation,
    ModelInfo,
    ModelResponse,
    StreamChunk,
    TokenUsage,
    ToolCallData,
)
from duh.providers.catalog import (
    ANTHROPIC_NO_TEMPERATURE_MODELS,
    MODEL_CATALOG,
    PROVIDER_CAPS,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from duh.providers.base import PromptMessage

PROVIDER_ID = "anthropic"
_KNOWN_MODELS = MODEL_CATALOG[PROVIDER_ID]
_DEFAULT_CAPS = PROVIDER_CAPS[PROVIDER_ID]


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
        web_search: bool = False,
    ) -> ModelResponse:
        system, api_messages = _build_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "system": system,
            "messages": api_messages,
        }
        # Newest thinking models reject temperature; older ones accept it.
        if model_id not in ANTHROPIC_NO_TEMPERATURE_MODELS:
            kwargs["temperature"] = temperature
        if stop_sequences:
            kwargs["stop_sequences"] = stop_sequences
        if tools:
            kwargs["tools"] = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema") or t.get("parameters", {}),
                }
                for t in tools
            ]
        if web_search:
            native_tool: dict[str, object] = {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": 5,
            }
            if "tools" in kwargs:
                kwargs["tools"].insert(0, native_tool)
            else:
                kwargs["tools"] = [native_tool]

        start = time.monotonic()
        try:
            # Use streaming internally to avoid Anthropic's 10-minute
            # timeout on non-streaming requests with large max_tokens.
            response = await self._collect_stream(kwargs)
        except anthropic.APIError as e:
            raise _map_error(e) from e

        latency_ms = (time.monotonic() - start) * 1000

        # Extract text content and tool use blocks.
        # With server tools (e.g. web_search), there may be multiple text
        # blocks interleaved with tool-use/result blocks — concatenate them.
        text_parts: list[str] = []
        tool_calls_data: list[ToolCallData] = []
        citations_data: list[Citation] = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            elif hasattr(block, "type") and block.type == "tool_use":
                import json

                tool_calls_data.append(
                    ToolCallData(
                        id=block.id,
                        name=block.name,
                        arguments=json.dumps(block.input),
                    )
                )
            elif hasattr(block, "type") and block.type == "web_search_tool_result":
                # Extract citations from server-side web search results
                search_content = getattr(block, "content", None)
                if isinstance(search_content, list):
                    for entry in search_content:
                        entry_type = getattr(entry, "type", None)
                        if entry_type == "web_search_result":
                            url = getattr(entry, "url", None)
                            if url:
                                citations_data.append(
                                    Citation(
                                        url=url,
                                        title=getattr(entry, "title", None),
                                        snippet=getattr(
                                            entry, "encrypted_content", None
                                        ),
                                    )
                                )

        content = "\n\n".join(text_parts)

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
            citations=citations_data if citations_data else None,
        )

    async def _collect_stream(self, kwargs: dict[str, Any]) -> anthropic.types.Message:
        """Stream a request and return the final Message.

        Streaming avoids Anthropic's 10-minute timeout for large
        max_tokens values while still returning a complete Message
        object compatible with non-streaming response parsing.
        """
        async with self._client.messages.stream(**kwargs) as s:
            return await s.get_final_message()

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
            "system": system,
            "messages": api_messages,
        }
        if model_id not in ANTHROPIC_NO_TEMPERATURE_MODELS:
            kwargs["temperature"] = temperature
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
