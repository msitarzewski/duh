"""Mock provider for deterministic testing."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    ModelResponse,
    StreamChunk,
    TokenUsage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from duh.providers.base import PromptMessage


class MockProvider:
    """Deterministic provider for tests.

    Returns canned responses keyed by model_id.
    Records all calls for assertion.
    """

    def __init__(
        self,
        provider_id: str = "mock",
        responses: dict[str, str] | None = None,
        *,
        healthy: bool = True,
        input_cost: float = 0.0,
        output_cost: float = 0.0,
    ) -> None:
        self._provider_id = provider_id
        self._responses = responses or {}
        self._healthy = healthy
        self._input_cost = input_cost
        self._output_cost = output_cost
        self.call_log: list[dict[str, Any]] = []

    @property
    def provider_id(self) -> str:
        return self._provider_id

    def _model_info(self, model_id: str) -> ModelInfo:
        return ModelInfo(
            provider_id=self._provider_id,
            model_id=model_id,
            display_name=f"Mock {model_id}",
            capabilities=ModelCapability.TEXT | ModelCapability.STREAMING,
            context_window=128_000,
            max_output_tokens=4096,
            input_cost_per_mtok=self._input_cost,
            output_cost_per_mtok=self._output_cost,
            is_local=True,
        )

    async def list_models(self) -> list[ModelInfo]:
        return [self._model_info(mid) for mid in self._responses]

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
        self.call_log.append(
            {
                "method": "send",
                "model_id": model_id,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "response_format": response_format,
                "tools": tools,
            }
        )
        content = self._responses.get(model_id, "Mock response")
        return ModelResponse(
            content=content,
            model_info=self._model_info(model_id),
            usage=TokenUsage(input_tokens=100, output_tokens=len(content.split())),
            finish_reason="stop",
            latency_ms=1.0,
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
        self.call_log.append(
            {
                "method": "stream",
                "model_id": model_id,
                "messages": messages,
            }
        )
        content = self._responses.get(model_id, "Mock response")
        words = content.split()
        for i, word in enumerate(words):
            is_final = i == len(words) - 1
            yield StreamChunk(
                text=word + (" " if not is_final else ""),
                is_final=is_final,
                usage=(
                    TokenUsage(input_tokens=100, output_tokens=len(words))
                    if is_final
                    else None
                ),
            )

    async def health_check(self) -> bool:
        return self._healthy
