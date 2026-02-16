"""Tool protocol and data types.

Defines the ``Tool`` protocol that all tool implementations must
satisfy, plus data classes for tool calls, results, and definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ToolDefinition:
    """Schema definition for a tool, suitable for passing to providers."""

    name: str
    description: str
    parameters_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A tool invocation requested by a model."""

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ToolResult:
    """Result from executing a tool."""

    tool_call_id: str
    content: str
    is_error: bool = False


@runtime_checkable
class Tool(Protocol):
    """Protocol that all tool implementations must satisfy."""

    @property
    def name(self) -> str:
        """Unique name for this tool."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of what the tool does."""
        ...

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """JSON Schema for the tool's parameters."""
        ...

    async def execute(self, **kwargs: Any) -> str:
        """Execute the tool with the given arguments.

        Returns:
            String result of the tool execution.

        Raises:
            Exception: On execution failure.
        """
        ...
