"""Tests for tool-augmented send."""

from __future__ import annotations

import json
from typing import Any

from duh.providers.base import (
    ModelInfo,
    ModelResponse,
    PromptMessage,
    TokenUsage,
    ToolCallData,
)
from duh.tools.augmented_send import tool_augmented_send
from duh.tools.registry import ToolRegistry

# ── Mock provider for tool use ──────────────────────────────────────


class _ToolMockProvider:
    """Provider that returns tool calls then a final text response."""

    def __init__(self, responses: list[ModelResponse]) -> None:
        self._responses = list(responses)
        self._call_idx = 0
        self.call_log: list[dict[str, Any]] = []

    @property
    def provider_id(self) -> str:
        return "tool-mock"

    async def list_models(self) -> list[ModelInfo]:
        return []

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
            {"messages": messages, "tools": tools, "model_id": model_id}
        )
        idx = min(self._call_idx, len(self._responses) - 1)
        self._call_idx += 1
        return self._responses[idx]

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


def _model_info() -> ModelInfo:
    from duh.providers.base import ModelCapability

    return ModelInfo(
        provider_id="tool-mock",
        model_id="m1",
        display_name="Mock",
        capabilities=ModelCapability.TEXT,
        context_window=128_000,
        max_output_tokens=4096,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
    )


def _text_response(text: str) -> ModelResponse:
    return ModelResponse(
        content=text,
        model_info=_model_info(),
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        finish_reason="stop",
        latency_ms=1.0,
    )


def _tool_response(tool_name: str, args: dict[str, Any]) -> ModelResponse:
    return ModelResponse(
        content="",
        model_info=_model_info(),
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        finish_reason="tool_use",
        latency_ms=1.0,
        tool_calls=[
            ToolCallData(
                id="tc-1",
                name=tool_name,
                arguments=json.dumps(args),
            )
        ],
    )


# ── Mock tool ───────────────────────────────────────────────────────


class _EchoTool:
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "Echoes input"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
        }

    async def execute(self, **kwargs: Any) -> str:
        return f"Echo: {kwargs.get('text', '')}"


# ── Tests ───────────────────────────────────────────────────────────


class TestToolAugmentedSend:
    async def test_no_tool_calls_passthrough(self) -> None:
        """When response has no tool calls, return it directly."""
        provider = _ToolMockProvider([_text_response("Hello")])
        registry = ToolRegistry()
        registry.register(_EchoTool())

        result = await tool_augmented_send(
            provider,
            "m1",
            [PromptMessage(role="user", content="Hi")],
            registry,
        )

        assert result.content == "Hello"
        assert len(provider.call_log) == 1

    async def test_tool_call_then_text(self) -> None:
        """Tool call executed, result fed back, final text returned."""
        provider = _ToolMockProvider(
            [
                _tool_response("echo", {"text": "world"}),
                _text_response("Done: Echo: world"),
            ]
        )
        registry = ToolRegistry()
        registry.register(_EchoTool())

        result = await tool_augmented_send(
            provider,
            "m1",
            [PromptMessage(role="user", content="Echo test")],
            registry,
        )

        assert result.content == "Done: Echo: world"
        assert len(provider.call_log) == 2
        # Second call should include tool result
        second_msgs = provider.call_log[1]["messages"]
        assert any("Echo: world" in m.content for m in second_msgs)

    async def test_max_rounds_limit(self) -> None:
        """Stops after max_tool_rounds even if still getting tool calls."""
        # Always returns tool calls
        provider = _ToolMockProvider([_tool_response("echo", {"text": "loop"})] * 5)
        registry = ToolRegistry()
        registry.register(_EchoTool())

        await tool_augmented_send(
            provider,
            "m1",
            [PromptMessage(role="user", content="Loop test")],
            registry,
            max_tool_rounds=3,
        )

        # Should have made exactly 3 calls
        assert len(provider.call_log) == 3

    async def test_empty_registry_passthrough(self) -> None:
        """With no tools registered, no tool defs sent, text returned."""
        provider = _ToolMockProvider([_text_response("No tools")])
        registry = ToolRegistry()

        result = await tool_augmented_send(
            provider,
            "m1",
            [PromptMessage(role="user", content="Hi")],
            registry,
        )

        assert result.content == "No tools"
        # Tools param should be None when registry is empty
        assert provider.call_log[0]["tools"] is None

    async def test_tool_definitions_passed(self) -> None:
        """Tool definitions are passed to the provider."""
        provider = _ToolMockProvider([_text_response("Ok")])
        registry = ToolRegistry()
        registry.register(_EchoTool())

        await tool_augmented_send(
            provider,
            "m1",
            [PromptMessage(role="user", content="Hi")],
            registry,
        )

        tools = provider.call_log[0]["tools"]
        assert tools is not None
        assert len(tools) == 1
        assert tools[0]["name"] == "echo"

    async def test_missing_tool_error_handled(self) -> None:
        """Tool call for non-existent tool returns error result."""
        provider = _ToolMockProvider(
            [
                _tool_response("nonexistent", {}),
                _text_response("Handled error"),
            ]
        )
        registry = ToolRegistry()
        registry.register(_EchoTool())

        result = await tool_augmented_send(
            provider,
            "m1",
            [PromptMessage(role="user", content="Bad tool")],
            registry,
        )

        assert result.content == "Handled error"
        # Second call should include error message
        second_msgs = provider.call_log[1]["messages"]
        assert any("not found" in m.content for m in second_msgs)

    async def test_multiple_tool_calls(self) -> None:
        """Multiple tool calls in a single response."""
        multi_response = ModelResponse(
            content="",
            model_info=_model_info(),
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            finish_reason="tool_use",
            latency_ms=1.0,
            tool_calls=[
                ToolCallData(
                    id="tc-1",
                    name="echo",
                    arguments=json.dumps({"text": "a"}),
                ),
                ToolCallData(
                    id="tc-2",
                    name="echo",
                    arguments=json.dumps({"text": "b"}),
                ),
            ],
        )
        provider = _ToolMockProvider([multi_response, _text_response("Both done")])
        registry = ToolRegistry()
        registry.register(_EchoTool())

        result = await tool_augmented_send(
            provider,
            "m1",
            [PromptMessage(role="user", content="Multi")],
            registry,
        )

        assert result.content == "Both done"
        second_msgs = provider.call_log[1]["messages"]
        tool_result_msg = [m for m in second_msgs if "Echo: a" in m.content]
        assert len(tool_result_msg) == 1
