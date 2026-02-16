"""Tool registry — manages available tools.

Provides registration, lookup, listing, and execution of tools
that implement the :class:`Tool` protocol.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from duh.tools.base import ToolDefinition, ToolResult

if TYPE_CHECKING:
    from duh.tools.base import Tool, ToolCall


class ToolRegistry:
    """Registry for managing available tools.

    Supports registration, lookup by name, listing definitions
    (for passing to provider APIs), and executing tool calls.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if tool.name in self._tools:
            msg = f"Tool already registered: {tool.name}"
            raise ValueError(msg)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool:
        """Get a tool by name.

        Raises:
            KeyError: If the tool is not found.
        """
        if name not in self._tools:
            msg = f"Tool not found: {name}"
            raise KeyError(msg)
        return self._tools[name]

    def list_definitions(self) -> list[ToolDefinition]:
        """Return tool definitions for all registered tools.

        Suitable for passing to provider APIs as available tools.
        """
        return [
            ToolDefinition(
                name=t.name,
                description=t.description,
                parameters_schema=t.parameters_schema,
            )
            for t in self._tools.values()
        ]

    async def execute(self, tool_call: ToolCall) -> ToolResult:
        """Execute a tool call and return the result.

        If the tool is not found or execution fails, returns a
        :class:`ToolResult` with ``is_error=True``.
        """
        try:
            tool = self.get(tool_call.name)
        except KeyError:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Tool not found: {tool_call.name}",
                is_error=True,
            )
        try:
            result = await tool.execute(**tool_call.arguments)
        except Exception as exc:
            return ToolResult(
                tool_call_id=tool_call.id,
                content=f"Tool execution error: {exc}",
                is_error=True,
            )
        return ToolResult(
            tool_call_id=tool_call.id,
            content=result,
        )

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def list_names(self) -> list[str]:
        """Return names of all registered tools."""
        return list(self._tools.keys())
