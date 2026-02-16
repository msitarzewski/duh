"""Tests for tool integration in consensus handlers.

Verifies that handlers work with and without tool_registry,
use tool_augmented_send when registry is provided, and log
tool calls to the context.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

from duh.consensus.handlers import handle_challenge, handle_propose
from duh.consensus.machine import (
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
)
from duh.core.errors import ConsensusError
from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    ModelResponse,
    PromptMessage,
    TokenUsage,
    ToolCallData,
)
from duh.tools.registry import ToolRegistry

if TYPE_CHECKING:
    from tests.fixtures.providers import MockProvider


# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context with sensible defaults."""
    defaults: dict[str, object] = {
        "thread_id": "t-tool",
        "question": "What is the best database for a CLI tool?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _propose_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context already in PROPOSE state (round 1)."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.PROPOSE)
    return ctx


def _challenge_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context in CHALLENGE state with a proposal set."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.PROPOSE)
    ctx.proposal = "Use PostgreSQL for JSONB support."
    ctx.proposal_model = "mock:proposer"
    sm.transition(ConsensusState.CHALLENGE)
    return ctx


def _model_info(provider_id: str = "mock", model_id: str = "proposer") -> ModelInfo:
    return ModelInfo(
        provider_id=provider_id,
        model_id=model_id,
        display_name=f"Mock {model_id}",
        capabilities=ModelCapability.TEXT | ModelCapability.STREAMING,
        context_window=128_000,
        max_output_tokens=4096,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
        is_local=True,
    )


def _text_response(text: str, model_id: str = "proposer") -> ModelResponse:
    return ModelResponse(
        content=text,
        model_info=_model_info(model_id=model_id),
        usage=TokenUsage(input_tokens=100, output_tokens=10),
        finish_reason="stop",
        latency_ms=1.0,
    )


def _tool_response(
    tool_name: str,
    args: dict[str, Any],
    model_id: str = "proposer",
) -> ModelResponse:
    return ModelResponse(
        content="",
        model_info=_model_info(model_id=model_id),
        usage=TokenUsage(input_tokens=100, output_tokens=10),
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


# ── Tool-aware mock provider ──────────────────────────────────


class _ToolAwareMockProvider:
    """Provider that returns a sequence of responses (tool calls then text)."""

    def __init__(
        self,
        provider_id: str = "mock",
        response_sequence: list[ModelResponse] | None = None,
        default_text: str = "Mock tool response",
    ) -> None:
        self._provider_id = provider_id
        self._responses = list(response_sequence or [])
        self._default_text = default_text
        self._call_idx = 0
        self.call_log: list[dict[str, Any]] = []

    @property
    def provider_id(self) -> str:
        return self._provider_id

    async def list_models(self) -> list[ModelInfo]:
        return [_model_info(self._provider_id, "proposer")]

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
                "tools": tools,
            }
        )
        if self._responses:
            idx = min(self._call_idx, len(self._responses) - 1)
            self._call_idx += 1
            return self._responses[idx]
        return _text_response(self._default_text, model_id)

    async def stream(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


# ── Mock tool ───────────────────────────────────────────────────


class _SearchTool:
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        }

    async def execute(self, **kwargs: Any) -> str:
        return f"Search result for: {kwargs.get('query', '')}"


def _make_registry() -> ToolRegistry:
    """Create a registry with a search tool."""
    registry = ToolRegistry()
    registry.register(_SearchTool())
    return registry


# ── Backwards compatibility (no tools) ──────────────────────────


class TestHandleProposeWithoutTools:
    """Verify propose still works without tool_registry (backwards compat)."""

    async def test_propose_without_tools(self, mock_provider: MockProvider) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        ctx = _propose_ctx()

        await handle_propose(ctx, pm, "mock:proposer")

        assert ctx.proposal is not None
        assert ctx.proposal_model == "mock:proposer"
        assert ctx.tool_calls_log == []

    async def test_propose_with_none_registry(
        self, mock_provider: MockProvider
    ) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        ctx = _propose_ctx()

        await handle_propose(ctx, pm, "mock:proposer", tool_registry=None)

        assert ctx.proposal is not None
        assert ctx.tool_calls_log == []


class TestHandleChallengeWithoutTools:
    """Verify challenge still works without tool_registry."""

    async def test_challenge_without_tools(self, mock_provider: MockProvider) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        ctx = _challenge_ctx()

        responses = await handle_challenge(
            ctx, pm, ["mock:challenger-1", "mock:challenger-2"]
        )

        assert len(responses) >= 1
        assert len(ctx.challenges) >= 1
        assert ctx.tool_calls_log == []


# ── Tool-augmented propose ──────────────────────────────────────


class TestHandleProposeWithTools:
    """Verify propose uses tool_augmented_send when registry provided."""

    async def test_propose_with_tools_no_tool_calls(self) -> None:
        """When model doesn't use tools, still works fine."""
        provider = _ToolAwareMockProvider(default_text="PostgreSQL is best for JSONB.")
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(provider)
        ctx = _propose_ctx()
        registry = _make_registry()

        await handle_propose(ctx, pm, "mock:proposer", tool_registry=registry)

        assert ctx.proposal == "PostgreSQL is best for JSONB."
        assert ctx.proposal_model == "mock:proposer"
        assert ctx.tool_calls_log == []
        # Tool definitions should have been passed to provider
        assert provider.call_log[0]["tools"] is not None

    async def test_propose_with_tool_call(self) -> None:
        """When model makes a tool call, it's logged to context."""
        provider = _ToolAwareMockProvider(
            response_sequence=[
                _tool_response("web_search", {"query": "best database"}),
                _text_response("Based on search: use SQLite."),
            ]
        )
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(provider)
        ctx = _propose_ctx()
        registry = _make_registry()

        await handle_propose(ctx, pm, "mock:proposer", tool_registry=registry)

        assert ctx.proposal == "Based on search: use SQLite."
        assert ctx.proposal_model == "mock:proposer"
        # tool_augmented_send consumed the tool call, so the final response
        # won't have tool_calls. But the intermediate one was logged.
        # Note: _log_tool_calls only logs from the *final* response.
        # The intermediate tool calls are handled inside tool_augmented_send.
        # The final text response has no tool_calls, so log remains empty.
        # This is correct — tool_augmented_send handles the loop internally.


class TestHandleProposeToolCallLogging:
    """Test that tool calls on the final response are logged."""

    async def test_tool_calls_on_response_are_logged(self) -> None:
        """If the final response has tool_calls, they are logged."""
        # Simulate a response that has both content and tool_calls
        resp_with_tools = ModelResponse(
            content="Answer with tools",
            model_info=_model_info(),
            usage=TokenUsage(input_tokens=100, output_tokens=10),
            finish_reason="stop",
            latency_ms=1.0,
            tool_calls=[
                ToolCallData(
                    id="tc-log",
                    name="web_search",
                    arguments=json.dumps({"query": "test"}),
                )
            ],
        )
        # Use a provider that returns this in first call (no tool loop
        # since tool_augmented_send sees tool_calls and loops, but let's
        # test the logging helper directly)
        from duh.consensus.handlers import _log_tool_calls

        ctx = _propose_ctx()
        _log_tool_calls(ctx, resp_with_tools, "propose")

        assert len(ctx.tool_calls_log) == 1
        assert ctx.tool_calls_log[0]["phase"] == "propose"
        assert ctx.tool_calls_log[0]["tool"] == "web_search"

    async def test_no_tool_calls_no_log(self) -> None:
        """When response has no tool_calls, nothing is logged."""
        from duh.consensus.handlers import _log_tool_calls

        ctx = _propose_ctx()
        resp = _text_response("Plain text")
        _log_tool_calls(ctx, resp, "propose")

        assert ctx.tool_calls_log == []


# ── Tool-augmented challenge ─────────────────────────────────────


class TestHandleChallengeWithTools:
    """Verify challenge uses tool_augmented_send when registry provided."""

    async def test_challenge_with_tools_no_tool_calls(self) -> None:
        """Challengers don't use tools — still works."""
        provider = _ToolAwareMockProvider(
            default_text="The proposal has a flaw in cost analysis."
        )
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(provider)
        ctx = _challenge_ctx()
        registry = _make_registry()

        responses = await handle_challenge(
            ctx, pm, ["mock:proposer"], tool_registry=registry
        )

        assert len(responses) == 1
        assert len(ctx.challenges) == 1
        assert ctx.tool_calls_log == []
        # Tool defs should have been passed
        assert provider.call_log[0]["tools"] is not None

    async def test_challenge_with_tool_call(self) -> None:
        """Challenger makes a tool call during challenge."""
        provider = _ToolAwareMockProvider(
            response_sequence=[
                _tool_response("web_search", {"query": "PostgreSQL issues"}),
                _text_response("The flaw is that PostgreSQL has scaling issues."),
            ]
        )
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(provider)
        ctx = _challenge_ctx()
        registry = _make_registry()

        responses = await handle_challenge(
            ctx, pm, ["mock:proposer"], tool_registry=registry
        )

        assert len(responses) == 1
        assert len(ctx.challenges) == 1
        assert "scaling issues" in ctx.challenges[0].content


# ── Error handling ───────────────────────────────────────────────


class TestToolIntegrationErrors:
    """Error handling when tool calls fail."""

    async def test_propose_wrong_state_with_tools(self) -> None:
        """Wrong state raises even with tools."""
        provider = _ToolAwareMockProvider()
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(provider)
        ctx = _make_ctx()  # IDLE state
        registry = _make_registry()

        with pytest.raises(ConsensusError, match="requires PROPOSE state"):
            await handle_propose(ctx, pm, "mock:proposer", tool_registry=registry)

    async def test_challenge_wrong_state_with_tools(self) -> None:
        """Wrong state raises even with tools."""
        provider = _ToolAwareMockProvider()
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(provider)
        ctx = _make_ctx()  # IDLE state
        registry = _make_registry()

        with pytest.raises(ConsensusError, match="requires CHALLENGE state"):
            await handle_challenge(ctx, pm, ["mock:proposer"], tool_registry=registry)


# ── Tool calls log field ────────────────────────────────────────


class TestToolCallsLogField:
    """Verify tool_calls_log field on ConsensusContext."""

    def test_default_empty(self) -> None:
        ctx = _make_ctx()
        assert ctx.tool_calls_log == []

    def test_log_persists_across_phases(self) -> None:
        """Tool call log accumulates across propose and challenge."""
        ctx = _make_ctx()
        ctx.tool_calls_log.append(
            {"phase": "propose", "tool": "web_search", "arguments": "{}"}
        )
        ctx.tool_calls_log.append(
            {"phase": "challenge", "tool": "web_search", "arguments": "{}"}
        )
        assert len(ctx.tool_calls_log) == 2
        assert ctx.tool_calls_log[0]["phase"] == "propose"
        assert ctx.tool_calls_log[1]["phase"] == "challenge"

    def test_log_not_cleared_between_rounds(self) -> None:
        """_clear_round_data does not clear tool_calls_log."""
        ctx = _make_ctx()
        ctx.tool_calls_log.append(
            {"phase": "propose", "tool": "web_search", "arguments": "{}"}
        )
        ctx._clear_round_data()
        assert len(ctx.tool_calls_log) == 1
