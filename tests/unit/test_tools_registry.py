"""Tests for tool registry."""

from __future__ import annotations

from typing import Any

import pytest

from duh.tools.base import ToolCall
from duh.tools.registry import ToolRegistry

# ── Mock tools ──────────────────────────────────────────────────────


class _SearchTool:
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {"query": {"type": "string"}}}

    async def execute(self, **kwargs: Any) -> str:
        return f"Results for: {kwargs.get('query', '')}"


class _FailTool:
    @property
    def name(self) -> str:
        return "fail_tool"

    @property
    def description(self) -> str:
        return "Always fails"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object"}

    async def execute(self, **kwargs: Any) -> str:
        msg = "Intentional failure"
        raise RuntimeError(msg)


# ── Registration ────────────────────────────────────────────────────


class TestRegistration:
    def test_register_and_get(self) -> None:
        reg = ToolRegistry()
        tool = _SearchTool()
        reg.register(tool)
        assert reg.get("web_search") is tool

    def test_duplicate_registration_raises(self) -> None:
        reg = ToolRegistry()
        reg.register(_SearchTool())
        with pytest.raises(ValueError, match=r"already registered"):
            reg.register(_SearchTool())

    def test_get_missing_raises(self) -> None:
        reg = ToolRegistry()
        with pytest.raises(KeyError, match=r"not found"):
            reg.get("nonexistent")

    def test_contains(self) -> None:
        reg = ToolRegistry()
        reg.register(_SearchTool())
        assert "web_search" in reg
        assert "nonexistent" not in reg

    def test_len(self) -> None:
        reg = ToolRegistry()
        assert len(reg) == 0
        reg.register(_SearchTool())
        assert len(reg) == 1

    def test_list_names(self) -> None:
        reg = ToolRegistry()
        reg.register(_SearchTool())
        reg.register(_FailTool())
        names = reg.list_names()
        assert "web_search" in names
        assert "fail_tool" in names


# ── Definitions ─────────────────────────────────────────────────────


class TestListDefinitions:
    def test_empty_registry(self) -> None:
        reg = ToolRegistry()
        assert reg.list_definitions() == []

    def test_definitions_match_tools(self) -> None:
        reg = ToolRegistry()
        reg.register(_SearchTool())
        defs = reg.list_definitions()
        assert len(defs) == 1
        assert defs[0].name == "web_search"
        assert defs[0].description == "Search the web"
        assert "query" in defs[0].parameters_schema["properties"]


# ── Execution ───────────────────────────────────────────────────────


class TestExecution:
    async def test_execute_success(self) -> None:
        reg = ToolRegistry()
        reg.register(_SearchTool())
        call = ToolCall(id="tc-1", name="web_search", arguments={"query": "test"})
        result = await reg.execute(call)
        assert not result.is_error
        assert "test" in result.content
        assert result.tool_call_id == "tc-1"

    async def test_execute_missing_tool(self) -> None:
        reg = ToolRegistry()
        call = ToolCall(id="tc-2", name="nonexistent")
        result = await reg.execute(call)
        assert result.is_error
        assert "not found" in result.content

    async def test_execute_tool_failure(self) -> None:
        reg = ToolRegistry()
        reg.register(_FailTool())
        call = ToolCall(id="tc-3", name="fail_tool")
        result = await reg.execute(call)
        assert result.is_error
        assert "Intentional failure" in result.content
