"""Perplexity provider adapter (OpenAI-compatible API)."""

from __future__ import annotations

import contextlib
import time
from typing import TYPE_CHECKING, Any

import openai

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
from duh.providers.catalog import MODEL_CATALOG, PROVIDER_CAPS

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from duh.providers.base import PromptMessage

PROVIDER_ID = "perplexity"
_KNOWN_MODELS = MODEL_CATALOG[PROVIDER_ID]
_DEFAULT_CAPS = PROVIDER_CAPS[PROVIDER_ID]


def _map_error(e: openai.APIError) -> Exception:
    """Map OpenAI SDK errors to duh error hierarchy."""
    if isinstance(e, openai.AuthenticationError):
        return ProviderAuthError(PROVIDER_ID, str(e))
    if isinstance(e, openai.RateLimitError):
        retry_after = None
        if hasattr(e, "response") and e.response is not None:
            raw = e.response.headers.get("retry-after")
            if raw is not None:
                with contextlib.suppress(ValueError):
                    retry_after = float(raw)
        return ProviderRateLimitError(PROVIDER_ID, retry_after=retry_after)
    if isinstance(e, openai.APITimeoutError):
        return ProviderTimeoutError(PROVIDER_ID, str(e))
    if isinstance(e, openai.InternalServerError):
        return ProviderOverloadedError(PROVIDER_ID, str(e))
    if isinstance(e, openai.NotFoundError):
        return ModelNotFoundError(PROVIDER_ID, str(e))
    # Fallback for unknown API errors
    return ProviderOverloadedError(PROVIDER_ID, str(e))


def _build_messages(
    messages: list[PromptMessage],
) -> list[dict[str, str]]:
    """Convert PromptMessages to OpenAI chat message format."""
    return [{"role": msg.role, "content": msg.content} for msg in messages]


class PerplexityProvider:
    """Provider adapter for Perplexity's OpenAI-compatible API.

    Perplexity uses the OpenAI SDK with a custom base_url.
    Responses may include citations which are captured in raw_response.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: openai.AsyncOpenAI | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            kwargs: dict[str, Any] = {
                "base_url": "https://api.perplexity.ai",
            }
            if api_key is not None:
                kwargs["api_key"] = api_key
            self._client = openai.AsyncOpenAI(**kwargs)

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
                proposer_eligible=False,
            )
            for m in _KNOWN_MODELS
        ]

    def _max_output_for(self, model_id: str) -> int:
        """Return the max output tokens for a model, defaulting to 8192."""
        for m in _KNOWN_MODELS:
            if m["model_id"] == model_id:
                return int(m["max_output_tokens"])
        return 8_192

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
        api_messages = _build_messages(messages)
        clamped = min(max_tokens, self._max_output_for(model_id))

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": clamped,
            "messages": api_messages,
            "temperature": temperature,
        }
        if stop_sequences:
            kwargs["stop"] = stop_sequences
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}
        if tools:
            kwargs["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters") or t.get("input_schema", {}),
                    },
                }
                for t in tools
            ]

        start = time.monotonic()
        try:
            response = await self._client.chat.completions.create(**kwargs)
        except openai.APIError as e:
            raise _map_error(e) from e

        latency_ms = (time.monotonic() - start) * 1000

        tool_calls_data: list[ToolCallData] | None = None
        if response.choices:
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason or "stop"
            # Parse tool calls from response
            msg_tool_calls = response.choices[0].message.tool_calls
            if msg_tool_calls:
                tool_calls_data = [
                    ToolCallData(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=tc.function.arguments,
                    )
                    for tc in msg_tool_calls
                ]
        else:
            content = ""
            finish_reason = "stop"

        if response.usage:
            usage = TokenUsage(
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )
        else:
            usage = TokenUsage(input_tokens=0, output_tokens=0)

        model_info = self._resolve_model_info(model_id)

        # Capture citations from Perplexity response if present
        raw_citations = getattr(response, "citations", None)
        raw = response
        if raw_citations is not None:
            raw = {"response": response, "citations": raw_citations}

        citations_data: list[Citation] = []
        if isinstance(raw_citations, list):
            for c in raw_citations:
                if isinstance(c, str):
                    citations_data.append(Citation(url=c))
                elif hasattr(c, "url"):
                    citations_data.append(
                        Citation(url=c.url, title=getattr(c, "title", None))
                    )

        return ModelResponse(
            content=content,
            model_info=model_info,
            usage=usage,
            finish_reason=finish_reason,
            latency_ms=latency_ms,
            raw_response=raw,
            tool_calls=tool_calls_data,
            citations=citations_data if citations_data else None,
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
        clamped = min(max_tokens, self._max_output_for(model_id))

        kwargs: dict[str, Any] = {
            "model": model_id,
            "max_tokens": clamped,
            "messages": api_messages,
            "temperature": temperature,
            "stream_options": {"include_usage": True},
        }
        if stop_sequences:
            kwargs["stop"] = stop_sequences

        try:
            response = await self._client.chat.completions.create(
                stream=True,
                **kwargs,
            )
            usage = None
            async for chunk in response:
                # Usage arrives in the final chunk (choices empty)
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

        except openai.APIError as e:
            raise _map_error(e) from e

    async def health_check(self) -> bool:
        try:
            await self._client.chat.completions.create(
                model="sonar",
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
                    proposer_eligible=False,
                )
        # Unknown model -- return generic info
        return ModelInfo(
            provider_id=PROVIDER_ID,
            model_id=model_id,
            display_name=f"Perplexity ({model_id})",
            capabilities=_DEFAULT_CAPS,
            context_window=128_000,
            max_output_tokens=8_192,
            input_cost_per_mtok=0.0,
            output_cost_per_mtok=0.0,
            proposer_eligible=False,
        )
