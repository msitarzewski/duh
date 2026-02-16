"""Google (Gemini) provider adapter."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from google import genai
from google.genai import errors as genai_errors

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

PROVIDER_ID = "google"

_KNOWN_MODELS: list[dict[str, Any]] = [
    {
        "model_id": "gemini-3-pro-preview",
        "display_name": "Gemini 3 Pro (Preview)",
        "context_window": 1_048_576,
        "max_output_tokens": 65_536,
        "input_cost_per_mtok": 2.00,
        "output_cost_per_mtok": 12.00,
    },
    {
        "model_id": "gemini-3-flash-preview",
        "display_name": "Gemini 3 Flash (Preview)",
        "context_window": 1_048_576,
        "max_output_tokens": 65_536,
        "input_cost_per_mtok": 0.50,
        "output_cost_per_mtok": 3.00,
    },
    {
        "model_id": "gemini-2.5-pro",
        "display_name": "Gemini 2.5 Pro",
        "context_window": 1_048_576,
        "max_output_tokens": 65_536,
        "input_cost_per_mtok": 1.25,
        "output_cost_per_mtok": 10.00,
    },
    {
        "model_id": "gemini-2.5-flash",
        "display_name": "Gemini 2.5 Flash",
        "context_window": 1_048_576,
        "max_output_tokens": 65_536,
        "input_cost_per_mtok": 0.30,
        "output_cost_per_mtok": 2.50,
    },
]

_DEFAULT_CAPS = (
    ModelCapability.TEXT
    | ModelCapability.STREAMING
    | ModelCapability.SYSTEM_PROMPT
    | ModelCapability.JSON_MODE
)


def _map_error(e: Exception) -> Exception:
    """Map Google GenAI errors to duh error hierarchy."""
    msg = str(e)
    if isinstance(e, genai_errors.ClientError):
        lower = msg.lower()
        if "api key" in lower or "auth" in lower or "permission" in lower:
            return ProviderAuthError(PROVIDER_ID, msg)
        if "not found" in lower or "404" in lower:
            return ModelNotFoundError(PROVIDER_ID, msg)
        if "429" in lower or "rate" in lower:
            return ProviderRateLimitError(PROVIDER_ID)
        return ProviderTimeoutError(PROVIDER_ID, msg)
    if isinstance(e, genai_errors.ServerError):
        return ProviderOverloadedError(PROVIDER_ID, msg)
    return ProviderOverloadedError(PROVIDER_ID, msg)


def _build_contents(
    messages: list[PromptMessage],
) -> tuple[str | None, list[dict[str, str]]]:
    """Split PromptMessages into system instruction + contents."""
    system: str | None = None
    contents: list[dict[str, Any]] = []

    for msg in messages:
        if msg.role == "system":
            system = msg.content
        else:
            role = "model" if msg.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

    return system, contents


class GoogleProvider:
    """Provider adapter for Google Gemini models."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        client: genai.Client | None = None,
    ) -> None:
        self._client = client or genai.Client(api_key=api_key)

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
        system, contents = _build_contents(messages)

        config_kwargs: dict[str, Any] = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
            "stop_sequences": stop_sequences or [],
            "system_instruction": system,
        }
        if response_format == "json":
            config_kwargs["response_mime_type"] = "application/json"
        if tools:
            config_kwargs["tools"] = tools

        config = genai.types.GenerateContentConfig(**config_kwargs)

        start = time.monotonic()
        try:
            response = await self._client.aio.models.generate_content(
                model=model_id,
                contents=contents,
                config=config,
            )
        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            raise _map_error(e) from e

        latency_ms = (time.monotonic() - start) * 1000

        # Extract text and function calls
        content = response.text or ""
        tool_calls_data: list[ToolCallData] = []
        if response.candidates:
            cand_content = response.candidates[0].content
            parts = cand_content.parts if cand_content else None
            if parts:
                for part in parts:
                    fc = getattr(part, "function_call", None)
                    if fc and fc.name:
                        import json

                        args = dict(fc.args) if fc.args else {}
                        tool_calls_data.append(
                            ToolCallData(
                                id=f"google-{fc.name}",
                                name=str(fc.name),
                                arguments=json.dumps(args),
                            )
                        )

        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0

        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        model_info = self._resolve_model_info(model_id)

        return ModelResponse(
            content=content,
            model_info=model_info,
            usage=usage,
            finish_reason="stop",
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
        system, contents = _build_contents(messages)

        config = genai.types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            stop_sequences=stop_sequences or [],
            system_instruction=system,
        )

        try:
            response = await self._client.aio.models.generate_content_stream(
                model=model_id,
                contents=contents,
                config=config,
            )
            usage = None
            async for chunk in response:
                if chunk.usage_metadata:
                    usage = TokenUsage(
                        input_tokens=chunk.usage_metadata.prompt_token_count or 0,
                        output_tokens=chunk.usage_metadata.candidates_token_count or 0,
                    )
                text = chunk.text or ""
                if text:
                    yield StreamChunk(text=text)

            yield StreamChunk(text="", is_final=True, usage=usage)

        except (genai_errors.ClientError, genai_errors.ServerError) as e:
            raise _map_error(e) from e

    async def health_check(self) -> bool:
        try:
            await self._client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents="ping",
                config=genai.types.GenerateContentConfig(max_output_tokens=1),
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
        return ModelInfo(
            provider_id=PROVIDER_ID,
            model_id=model_id,
            display_name=f"Gemini ({model_id})",
            capabilities=_DEFAULT_CAPS,
            context_window=1_048_576,
            max_output_tokens=8192,
            input_cost_per_mtok=0.0,
            output_cost_per_mtok=0.0,
        )
