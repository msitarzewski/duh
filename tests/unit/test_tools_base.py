"""Tests for tool framework base types and registry."""

from __future__ import annotations

from typing import Any

import pytest

from duh.tools.base import Tool, ToolCall, ToolDefinition, ToolResult

# ── Data class tests ────────────────────────────────────────────────


class TestToolDefinition:
    def test_creation(self) -> None:
        td = ToolDefinition(
            name="search",
            description="Search the web",
            parameters_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
            },
        )
        assert td.name == "search"
        assert td.description == "Search the web"
        assert "query" in td.parameters_schema["properties"]

    def test_frozen(self) -> None:
        td = ToolDefinition(name="x", description="y", parameters_schema={})
        with pytest.raises(AttributeError):
            td.name = "z"  # type: ignore[misc]


class TestToolCall:
    def test_creation(self) -> None:
        tc = ToolCall(id="tc-1", name="search", arguments={"query": "test"})
        assert tc.id == "tc-1"
        assert tc.name == "search"
        assert tc.arguments == {"query": "test"}

    def test_default_empty_args(self) -> None:
        tc = ToolCall(id="tc-2", name="search")
        assert tc.arguments == {}


class TestToolResult:
    def test_success_result(self) -> None:
        tr = ToolResult(tool_call_id="tc-1", content="result text")
        assert not tr.is_error
        assert tr.content == "result text"

    def test_error_result(self) -> None:
        tr = ToolResult(tool_call_id="tc-1", content="error msg", is_error=True)
        assert tr.is_error


# ── Protocol conformance ────────────────────────────────────────────


class MockTool:
    """Test tool implementing the Tool protocol."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"input": {"type": "string"}}}

    async def execute(self, **kwargs: Any) -> str:
        return f"Executed with: {kwargs}"


class TestToolProtocol:
    def test_isinstance_check(self) -> None:
        tool = MockTool()
        assert isinstance(tool, Tool)

    async def test_execute(self) -> None:
        tool = MockTool()
        result = await tool.execute(input="test")
        assert "test" in result
