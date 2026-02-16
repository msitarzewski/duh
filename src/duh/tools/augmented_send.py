"""Tool-augmented send — wraps provider.send() with a tool-use loop.

Sends a prompt, checks for tool calls in the response, executes them,
feeds results back, and repeats until a text response or max rounds.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.providers.base import ModelProvider, ModelResponse
    from duh.tools.base import ToolCall
    from duh.tools.registry import ToolRegistry


async def tool_augmented_send(
    provider: ModelProvider,
    model_id: str,
    messages: list[PromptMessage],
    tool_registry: ToolRegistry,
    *,
    max_tool_rounds: int = 5,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ModelResponse:
    """Send a prompt with tool-use loop.

    1. Call provider.send() with tool definitions
    2. If response has tool_calls, execute them via registry
    3. Feed tool results back as messages
    4. Repeat until text response or max_tool_rounds reached

    Args:
        provider: The model provider to use.
        model_id: Model to call.
        messages: Initial prompt messages.
        tool_registry: Registry of available tools.
        max_tool_rounds: Maximum tool-use iterations.
        temperature: Sampling temperature.
        max_tokens: Max output tokens.

    Returns:
        Final ModelResponse (text content or last tool round).
    """
    from duh.tools.base import ToolCall as ToolCallType

    tool_defs = tool_registry.list_definitions()
    tools_param: list[dict[str, object]] = [
        {
            "name": td.name,
            "description": td.description,
            "parameters": td.parameters_schema,
        }
        for td in tool_defs
    ]

    current_messages = list(messages)

    for _round in range(max_tool_rounds):
        response = await provider.send(
            current_messages,
            model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=tools_param if tools_param else None,
        )

        # If no tool calls, return the response as-is
        if not response.tool_calls:
            return response

        # Execute tool calls
        tool_results: list[str] = []
        for tc_data in response.tool_calls:
            try:
                args = json.loads(tc_data.arguments)
            except json.JSONDecodeError:
                args = {}
            tool_call: ToolCall = ToolCallType(
                id=tc_data.id,
                name=tc_data.name,
                arguments=args,
            )
            result = await tool_registry.execute(tool_call)
            tool_results.append(f"Tool '{tc_data.name}' result: {result.content}")

        # Add assistant message with tool call indication
        current_messages.append(
            PromptMessage(
                role="assistant",
                content=response.content or "(tool calls made)",
            )
        )
        # Add tool results as user message
        current_messages.append(
            PromptMessage(
                role="user",
                content="\n\n".join(tool_results),
            )
        )

    # Max rounds reached — return last response
    return response
