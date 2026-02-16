"""Tests for CLI tool setup and tool-use display.

Verifies:
- _setup_tools() creates correct registry from config
- --tools/--no-tools flag overrides config
- show_tool_use() renders tool call logs correctly
- Tool registry wiring through _run_consensus
"""

from __future__ import annotations

from io import StringIO
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner
from rich.console import Console

from duh.cli.app import _setup_tools, cli
from duh.cli.display import ConsensusDisplay
from duh.config.schema import (
    CodeExecutionConfig,
    DuhConfig,
    ToolsConfig,
    WebSearchConfig,
)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ── _setup_tools() helper ────────────────────────────────────────


class TestSetupTools:
    def test_returns_none_when_disabled(self) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=False))
        result = _setup_tools(config)
        assert result is None

    def test_returns_registry_when_enabled(self) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=True))
        result = _setup_tools(config)
        assert result is not None
        assert len(result) >= 2  # web_search + file_read at minimum

    def test_registers_web_search(self) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=True))
        registry = _setup_tools(config)
        assert registry is not None
        assert "web_search" in registry

    def test_registers_file_read(self) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=True))
        registry = _setup_tools(config)
        assert registry is not None
        assert "file_read" in registry

    def test_does_not_register_code_exec_when_disabled(self) -> None:
        config = DuhConfig(
            tools=ToolsConfig(
                enabled=True,
                code_execution=CodeExecutionConfig(enabled=False),
            )
        )
        registry = _setup_tools(config)
        assert registry is not None
        assert "code_execution" not in registry

    def test_registers_code_exec_when_enabled(self) -> None:
        config = DuhConfig(
            tools=ToolsConfig(
                enabled=True,
                code_execution=CodeExecutionConfig(enabled=True),
            )
        )
        registry = _setup_tools(config)
        assert registry is not None
        assert "code_execution" in registry
        assert len(registry) == 3

    def test_web_search_config_forwarded(self) -> None:
        ws_config = WebSearchConfig(backend="tavily", max_results=10)
        config = DuhConfig(tools=ToolsConfig(enabled=True, web_search=ws_config))
        registry = _setup_tools(config)
        assert registry is not None
        tool = registry.get("web_search")
        assert tool._config.backend == "tavily"  # type: ignore[attr-defined]
        assert tool._config.max_results == 10  # type: ignore[attr-defined]

    def test_list_definitions_returns_openai_format(self) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=True))
        registry = _setup_tools(config)
        assert registry is not None
        defs = registry.list_definitions()
        assert len(defs) >= 2
        for d in defs:
            assert d.name
            assert d.description
            assert d.parameters_schema


# ── --tools/--no-tools CLI flag ──────────────────────────────────


class TestToolsFlag:
    def test_ask_help_shows_tools_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(cli, ["ask", "--help"])
        assert result.exit_code == 0
        assert "--tools" in result.output
        assert "--no-tools" in result.output

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_tools_flag_enables_tools(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=False))
        mock_config.return_value = config
        mock_run.return_value = ("Answer", 0.9, None, 0.01)

        runner.invoke(cli, ["ask", "--tools", "test question"])
        # After CLI processes --tools flag, config should be overridden
        assert config.tools.enabled is True

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_no_tools_flag_disables_tools(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=True))
        mock_config.return_value = config
        mock_run.return_value = ("Answer", 0.9, None, 0.01)

        runner.invoke(cli, ["ask", "--no-tools", "test question"])
        assert config.tools.enabled is False

    @patch("duh.cli.app.asyncio.run")
    @patch("duh.cli.app.load_config")
    def test_no_flag_preserves_config(
        self,
        mock_config: Any,
        mock_run: Any,
        runner: CliRunner,
    ) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=True))
        mock_config.return_value = config
        mock_run.return_value = ("Answer", 0.9, None, 0.01)

        runner.invoke(cli, ["ask", "test question"])
        # Should remain True since no flag was passed
        assert config.tools.enabled is True


# ── show_tool_use() display ──────────────────────────────────────


def _make_display() -> tuple[ConsensusDisplay, StringIO]:
    """Create a display with a captured StringIO console."""
    buf = StringIO()
    console = Console(file=buf, width=80, no_color=True)
    display = ConsensusDisplay(console=console)
    return display, buf


class TestShowToolUse:
    def test_renders_tool_calls(self) -> None:
        display, buf = _make_display()
        log = [
            {
                "phase": "PROPOSE",
                "tool": "web_search",
                "arguments": '{"query": "latest AI news"}',
            },
            {
                "phase": "CHALLENGE",
                "tool": "file_read",
                "arguments": '{"path": "/tmp/data.txt"}',
            },
        ]
        display.show_tool_use(log)
        output = buf.getvalue()
        assert "TOOLS" in output
        assert "2 calls" in output
        assert "PROPOSE" in output
        assert "web_search" in output
        assert "CHALLENGE" in output
        assert "file_read" in output

    def test_no_output_when_empty(self) -> None:
        display, buf = _make_display()
        display.show_tool_use([])
        output = buf.getvalue()
        assert output.strip() == ""

    def test_single_tool_call(self) -> None:
        display, buf = _make_display()
        log = [
            {
                "phase": "PROPOSE",
                "tool": "web_search",
                "arguments": '{"query": "test"}',
            },
        ]
        display.show_tool_use(log)
        output = buf.getvalue()
        assert "1 calls" in output
        assert "web_search" in output

    def test_missing_fields_handled(self) -> None:
        display, buf = _make_display()
        log = [{}]  # All fields missing
        display.show_tool_use(log)
        output = buf.getvalue()
        assert "unknown" in output
        assert "1 calls" in output


# ── Tool registry wiring in _ask_async ───────────────────────────


class TestAskAsyncToolWiring:
    @patch("duh.cli.app._run_consensus", new_callable=AsyncMock)
    @patch("duh.cli.app._setup_providers", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_tools_enabled_passes_registry(
        self,
        mock_config: Any,
        mock_providers: Any,
        mock_consensus: Any,
        runner: CliRunner,
    ) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=True))
        mock_config.return_value = config
        mock_providers.return_value.list_all_models.return_value = ["model1"]
        mock_consensus.return_value = ("Answer", 0.9, None, 0.01)

        runner.invoke(cli, ["ask", "test question"])

        # _run_consensus should have been called with a tool_registry
        call_kwargs = mock_consensus.call_args
        assert call_kwargs.kwargs.get("tool_registry") is not None

    @patch("duh.cli.app._run_consensus", new_callable=AsyncMock)
    @patch("duh.cli.app._setup_providers", new_callable=AsyncMock)
    @patch("duh.cli.app.load_config")
    def test_tools_disabled_passes_none(
        self,
        mock_config: Any,
        mock_providers: Any,
        mock_consensus: Any,
        runner: CliRunner,
    ) -> None:
        config = DuhConfig(tools=ToolsConfig(enabled=False))
        mock_config.return_value = config
        mock_providers.return_value.list_all_models.return_value = ["model1"]
        mock_consensus.return_value = ("Answer", 0.9, None, 0.01)

        runner.invoke(cli, ["ask", "test question"])

        call_kwargs = mock_consensus.call_args
        assert call_kwargs.kwargs.get("tool_registry") is None
