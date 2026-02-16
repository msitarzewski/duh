"""Integration test: tool-augmented consensus.

Verifies that when tools are enabled, handle_propose uses
tool_augmented_send and tool calls are logged to the context.
"""

from __future__ import annotations

from typing import Any

from duh.consensus.handlers import (
    handle_challenge,
    handle_commit,
    handle_propose,
    handle_revise,
    select_challengers,
    select_proposer,
)
from duh.consensus.machine import (
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
)
from duh.tools.code_exec import CodeExecutionTool
from duh.tools.file_read import FileReadTool
from duh.tools.registry import ToolRegistry
from duh.tools.web_search import WebSearchTool

# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    defaults: dict[str, object] = {
        "thread_id": "t-tools",
        "question": "What is the latest Python version?",
        "max_rounds": 1,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


async def _setup_pm(provider: Any) -> Any:
    from duh.providers.manager import ProviderManager

    pm = ProviderManager()
    await pm.register(provider)
    return pm


def _setup_tool_registry() -> ToolRegistry:
    """Create a registry with all three tools."""
    from duh.config.schema import CodeExecutionConfig, WebSearchConfig

    registry = ToolRegistry()
    registry.register(WebSearchTool(WebSearchConfig()))
    registry.register(FileReadTool())
    registry.register(CodeExecutionTool(CodeExecutionConfig(enabled=True, timeout=5)))
    return registry


# ── Tests ────────────────────────────────────────────────────────


class TestToolAugmentedConsensus:
    """Tool-augmented consensus flow."""

    async def test_propose_with_tool_registry(self) -> None:
        """handle_propose with tool_registry uses tool_augmented_send path."""
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = await _setup_pm(provider)
        registry = _setup_tool_registry()

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.PROPOSE)

        proposer = select_proposer(pm)
        await handle_propose(ctx, pm, proposer, tool_registry=registry)

        # Proposal should be set (mock doesn't issue tool calls, so it's
        # the regular response through tool_augmented_send)
        assert ctx.proposal is not None
        assert ctx.proposal_model is not None

        # Verify provider was called with tools param
        assert len(provider.call_log) > 0
        last_call = provider.call_log[-1]
        assert last_call["tools"] is not None
        assert len(last_call["tools"]) == 3

    async def test_tool_definitions_forwarded(self) -> None:
        """All registered tool definitions are forwarded to the provider."""
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = await _setup_pm(provider)
        registry = _setup_tool_registry()

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.PROPOSE)

        await handle_propose(ctx, pm, select_proposer(pm), tool_registry=registry)

        last_call = provider.call_log[-1]
        tool_names = {t["name"] for t in last_call["tools"]}
        assert tool_names == {"web_search", "file_read", "code_execution"}

    async def test_full_round_with_tools_no_tool_calls(self) -> None:
        """Full consensus round with tools enabled but no tool calls made.

        Mock provider returns plain text (no tool_calls), so the loop
        completes normally with tool_calls_log empty.
        """
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = await _setup_pm(provider)
        registry = _setup_tool_registry()

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        # PROPOSE with tools
        sm.transition(ConsensusState.PROPOSE)
        proposer = select_proposer(pm)
        await handle_propose(ctx, pm, proposer, tool_registry=registry)

        # CHALLENGE with tools
        sm.transition(ConsensusState.CHALLENGE)
        challengers = select_challengers(pm, proposer)
        await handle_challenge(ctx, pm, challengers, tool_registry=registry)

        # REVISE (no tools)
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)

        # COMMIT
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        assert ctx.decision is not None
        assert ctx.confidence > 0
        # No tool calls were made (mock returns plain text)
        assert ctx.tool_calls_log == []

    async def test_propose_without_tool_registry_no_tools(self) -> None:
        """handle_propose without tool_registry doesn't send tools param."""
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.PROPOSE)

        await handle_propose(ctx, pm, select_proposer(pm))

        last_call = provider.call_log[-1]
        assert last_call.get("tools") is None

    async def test_registry_has_all_tools(self) -> None:
        """Tool registry correctly contains all three tool implementations."""
        registry = _setup_tool_registry()

        assert len(registry) == 3
        assert "web_search" in registry
        assert "file_read" in registry
        assert "code_execution" in registry

        defs = registry.list_definitions()
        for d in defs:
            assert d.name
            assert d.description
            assert d.parameters_schema

    async def test_cli_setup_tools_disabled(self) -> None:
        """_setup_tools returns None when tools are disabled."""
        from duh.cli.app import _setup_tools
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        config.tools.enabled = False
        result = _setup_tools(config)
        assert result is None

    async def test_cli_setup_tools_enabled(self) -> None:
        """_setup_tools returns a ToolRegistry when tools are enabled."""
        from duh.cli.app import _setup_tools
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        config.tools.enabled = True
        result = _setup_tools(config)
        assert result is not None
        assert isinstance(result, ToolRegistry)
        assert "web_search" in result
        assert "file_read" in result
        # Code execution not enabled by default
        assert "code_execution" not in result

    async def test_cli_setup_tools_with_code_exec(self) -> None:
        """_setup_tools includes code_execution when explicitly enabled."""
        from duh.cli.app import _setup_tools
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        config.tools.enabled = True
        config.tools.code_execution.enabled = True
        result = _setup_tools(config)
        assert result is not None
        assert "code_execution" in result
