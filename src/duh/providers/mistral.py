"""Mistral AI provider adapter."""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any

from mistralai import Mistral
from mistralai import models as mistral_models

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

PROVIDER_ID = "mistral"

_KNOWN_MODELS: list[dict[str, Any]] = [
    {
        "model_id": "mistral-large-latest",
        "display_name": "Mistral Large",
        "context_window": 128_000,
        "max_output_tokens": 32_000,
        "input_cost_per_mtok": 2.0,
        "output_cost_per_mtok": 6.0,
    },
    {
        "model_id": "mistral-medium-latest",
        "display_name": "Mistral Medium",
        "context_window": 128_000,
        "max_output_tokens": 32_000,
        "input_cost_per_mtok": 2.7,
        "output_cost_per_mtok": 8.1,
    },
    {
        "model_id": "mistral-small-latest",
        "display_name": "Mistral Small",
        "context_window": 128_000,
        "max_output_tokens": 32_000,
        "input_cost_per_mtok": 0.2,
        "output_cost_per_mtok": 0.6,
    },
    {
        "model_id": "codestral-latest",
        "display_name": "Codestral",
        "context_window": 256_000,
        "max_output_tokens": 32_000,
        "input_cost_per_mtok": 0.3,
        "output_cost_per_mtok": 0.9,
    },
]

_DEFAULT_CAPS = (
    ModelCapability.TEXT
    | ModelCapability.STREAMING
    | ModelCapability.SYSTEM_PROMPT
    | ModelCapability.JSON_MODE
)


def _map_error(e: Exception) -> Exception:
    """Map Mistral SDK errors to duh error hierarchy."""
    msg = str(e)
    lower = msg.lower()

    if isinstance(e, mistral_models.SDKError):
        status = getattr(e, "status_code", None)
        if status == 401 or "auth" in lower or "api key" in lower:
            return ProviderAuthError(PROVIDER_ID, msg)
        if status == 429 or "rate" in lower:
            return ProviderRateLimitError(PROVIDER_ID)
        if status == 408 or "timeout" in lower:
            return ProviderTimeoutError(PROVIDER_ID, msg)
        if status == 404 or "not found" in lower:
            return ModelNotFoundError(PROVIDER_ID, msg)
        return ProviderOverloadedError(PROVIDER_ID, msg)

    if isinstance(e, mistral_models.HTTPValidationError):
        return ProviderOverloadedError(PROVIDER_ID, msg)

    return ProviderOverloadedError(PROVIDER_ID, msg)


def _build_messages(
    messages: list[PromptMessage],
) -> list[dict[str, str]]:
    """Convert PromptMessages to Mistral chat message format.

    Mistral accepts system messages directly in the messages array,
    same as OpenAI.
    """
    return [{"role": msg.role, "content": msg.content} for msg in messages]


class MistralProvider:
    """Provider adapter for Mistral AI models."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: Mistral | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            kwargs: dict[str, Any] = {}
            if api_key is not None:
                kwargs["api_key"] = api_key
            self._client = Mistral(**kwargs)

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
        api_messages = _build_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": api_messages,
        }
        if stop_sequences:
            kwargs["stop"] = stop_sequences
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = tools

        start = time.monotonic()
        try:
            response = await self._client.chat.complete_async(**kwargs)
        except (
            mistral_models.SDKError,
            mistral_models.HTTPValidationError,
        ) as e:
            raise _map_error(e) from e

        latency_ms = (time.monotonic() - start) * 1000

        tool_calls_data: list[ToolCallData] | None = None
        if response and response.choices:
            raw_content = response.choices[0].message.content
            content = raw_content if isinstance(raw_content, str) else ""
            finish_reason = response.choices[0].finish_reason or "stop"
            # Parse tool calls from response
            msg_tool_calls = response.choices[0].message.tool_calls
            if msg_tool_calls:
                tool_calls_data = [
                    ToolCallData(
                        id=tc.id or "",
                        name=tc.function.name,
                        arguments=(
                            tc.function.arguments
                            if isinstance(tc.function.arguments, str)
                            else json.dumps(tc.function.arguments)
                        ),
                    )
                    for tc in msg_tool_calls
                ]
        else:
            content = ""
            finish_reason = "stop"

        if response and response.usage:
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens or 0,
                output_tokens=response.usage.completion_tokens or 0,
            )
        else:
            usage = TokenUsage(input_tokens=0, output_tokens=0)

        model_info = self._resolve_model_info(model_id)

        return ModelResponse(
            content=content,
            model_info=model_info,
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            raw_response=response,
            tool_calls=tool_calls_data,
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
        api_messages = _build_messages(messages)

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": api_messages,
        }
        if stop_sequences:
            kwargs["stop"] = stop_sequences

        try:
            response = await self._client.chat.stream_async(**kwargs)
            usage = None
            async for event in response:
                chunk = event.data
                # Usage arrives in the final chunk
                if chunk.usage is not None:
                    usage = TokenUsage(
                        input_tokens=chunk.usage.prompt_tokens,
                        output_tokens=chunk.usage.completion_tokens,
                    )

                if chunk.choices and chunk.choices[0].delta.content:
                    yield StreamChunk(
                        text=chunk.choices[0].delta.content,
                    )

            yield StreamChunk(text="", is_final=True, usage=usage)

        except (
            mistral_models.SDKError,
            mistral_models.HTTPValidationError,
        ) as e:
            raise _map_error(e) from e

    async def health_check(self) -> bool:
        try:
            await self._client.chat.complete_async(
                model="mistral-small-latest",
                max_tokens=1,
                messages=[{"role": "user", "content": "ping"}],  # type: ignore[arg-type]
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
            display_name=f"Mistral ({model_id})",
            capabilities=_DEFAULT_CAPS,
            context_window=128_000,
            max_output_tokens=4096,
            input_cost_per_mtok=0.0,
            output_cost_per_mtok=0.0,
        )
