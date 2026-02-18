"""Provider adapter interface and data classes.

All provider adapters implement the ``ModelProvider`` protocol.
Data classes are immutable where possible (frozen dataclasses with slots).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class ModelCapability(enum.Flag):
    """Capabilities a model may or may not support."""

    TEXT = enum.auto()
    STREAMING = enum.auto()
    TOOL_USE = enum.auto()
    VISION = enum.auto()
    JSON_MODE = enum.auto()
    SYSTEM_PROMPT = enum.auto()


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Static metadata about a model available through a provider."""

    provider_id: str  # e.g. "anthropic", "openai", "ollama"
    model_id: str  # e.g. "claude-opus-4-6", "gpt-5.2"
    display_name: str  # Human-readable: "Claude Opus 4.6"
    capabilities: ModelCapability
    context_window: int  # Max tokens (input + output)
    max_output_tokens: int  # Max output tokens
    input_cost_per_mtok: float  # USD per million input tokens (0.0 for local)
    output_cost_per_mtok: float  # USD per million output tokens (0.0 for local)
    is_local: bool = False
    proposer_eligible: bool = True  # False = challenger-only (e.g. search-grounded)

    @property
    def model_ref(self) -> str:
        """Canonical reference: ``provider_id:model_id``."""
        return f"{self.provider_id}:{self.model_id}"


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token counts from a single model call."""

    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (input + output)."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True, slots=True)
class ToolCallData:
    """A tool call from a model response."""

    id: str
    name: str
    arguments: str  # JSON string of arguments


@dataclass(slots=True)
class ModelResponse:
    """Complete response from a model call."""

    content: str
    model_info: ModelInfo
    usage: TokenUsage
    finish_reason: str  # "stop", "max_tokens", "tool_use"
    latency_ms: float  # Wall-clock time for the call
    raw_response: object = field(default=None, repr=False)
    tool_calls: list[ToolCallData] | None = None


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """A single chunk from a streaming response."""

    text: str
    is_final: bool = False
    usage: TokenUsage | None = None  # Only populated on final chunk


@dataclass(frozen=True, slots=True)
class PromptMessage:
    """A single message in a prompt sequence."""

    role: str  # "system", "user", "assistant"
    content: str


@runtime_checkable
class ModelProvider(Protocol):
    """Protocol that all provider adapters must satisfy.

    Implementations are stateless — they hold connection config but no
    conversation state. The consensus engine manages all state.
    """

    @property
    def provider_id(self) -> str:
        """Unique identifier for this provider (e.g. 'anthropic', 'openai')."""
        ...

    async def list_models(self) -> list[ModelInfo]:
        """Return metadata for all models available through this provider.

        Should be cached after first call (models don't change mid-session).
        """
        ...

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
        """Send a prompt and wait for complete response.

        Args:
            messages: Prompt messages.
            model_id: Model to use.
            max_tokens: Max output tokens.
            temperature: Sampling temperature.
            stop_sequences: Sequences that stop generation.
            response_format: If ``"json"``, request JSON output mode.
            tools: Tool definitions for function calling.

        Raises ProviderError on failure.
        """
        ...

    async def stream(
        self,
        messages: list[PromptMessage],
        model_id: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Send a prompt and yield response chunks as they arrive.

        Final chunk has ``is_final=True`` and includes usage.
        Raises ProviderError on failure.
        """
        ...

    async def health_check(self) -> bool:
        """Verify the provider is reachable and credentials are valid.

        Returns True if healthy, False otherwise. Must not raise.
        """
        ...
