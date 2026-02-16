"""Tests for tool call forwarding and parsing across all providers.

Verifies that:
- tools parameter is forwarded correctly in send() calls
- tool_calls are parsed from mock responses into ToolCallData objects
- response_format parameter works
- Edge cases: no tools, empty tool_calls, malformed responses
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from duh.providers.base import PromptMessage, ToolCallData
from duh.providers.openai import OpenAIProvider

# ── Shared fixtures ──────────────────────────────────────────────

SAMPLE_TOOLS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    }
]

USER_MSG = [PromptMessage(role="user", content="Search for cats")]


# ═══════════════════════════════════════════════════════════════════
# OpenAI Provider — Tool Call Tests
# ═══════════════════════════════════════════════════════════════════


def _oai_make_response_with_tool_calls(
    tool_calls: list[dict[str, Any]] | None = None,
    text: str = "",
    finish_reason: str = "tool_calls",
) -> MagicMock:
    """Build an OpenAI mock response with optional tool calls."""
    choice = MagicMock()
    choice.message.content = text
    choice.finish_reason = finish_reason

    if tool_calls:
        mock_tcs = []
        for tc in tool_calls:
            mock_tc = MagicMock()
            mock_tc.id = tc["id"]
            mock_tc.function.name = tc["name"]
            mock_tc.function.arguments = tc["arguments"]
            mock_tcs.append(mock_tc)
        choice.message.tool_calls = mock_tcs
    else:
        choice.message.tool_calls = None

    response = MagicMock()
    response.choices = [choice]
    usage = MagicMock()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    response.usage = usage
    return response


def _oai_make_client(response: Any = None) -> MagicMock:
    import openai

    client = MagicMock(spec=openai.AsyncOpenAI)
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    if response is None:
        response = _oai_make_response_with_tool_calls()
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


class TestOpenAIToolForwarding:
    async def test_tools_param_forwarded(self) -> None:
        client = _oai_make_client()
        provider = OpenAIProvider(client=client)
        await provider.send(USER_MSG, "gpt-5.2", tools=SAMPLE_TOOLS)
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["tools"] is SAMPLE_TOOLS

    async def test_no_tools_param_omitted(self) -> None:
        client = _oai_make_client()
        provider = OpenAIProvider(client=client)
        await provider.send(USER_MSG, "gpt-5.2")
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert "tools" not in call_kwargs

    async def test_response_format_json(self) -> None:
        client = _oai_make_client()
        provider = OpenAIProvider(client=client)
        await provider.send(USER_MSG, "gpt-5.2", response_format="json")
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"] == {"type": "json_object"}

    async def test_response_format_none_omitted(self) -> None:
        client = _oai_make_client()
        provider = OpenAIProvider(client=client)
        await provider.send(USER_MSG, "gpt-5.2")
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert "response_format" not in call_kwargs


class TestOpenAIToolCallParsing:
    async def test_single_tool_call_parsed(self) -> None:
        response = _oai_make_response_with_tool_calls(
            tool_calls=[
                {
                    "id": "call_abc123",
                    "name": "web_search",
                    "arguments": '{"query": "cats"}',
                }
            ]
        )
        client = _oai_make_client(response)
        provider = OpenAIProvider(client=client)
        resp = await provider.send(USER_MSG, "gpt-5.2", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert isinstance(tc, ToolCallData)
        assert tc.id == "call_abc123"
        assert tc.name == "web_search"
        assert tc.arguments == '{"query": "cats"}'

    async def test_multiple_tool_calls_parsed(self) -> None:
        response = _oai_make_response_with_tool_calls(
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "web_search",
                    "arguments": '{"query": "cats"}',
                },
                {
                    "id": "call_2",
                    "name": "web_search",
                    "arguments": '{"query": "dogs"}',
                },
            ]
        )
        client = _oai_make_client(response)
        provider = OpenAIProvider(client=client)
        resp = await provider.send(USER_MSG, "gpt-5.2", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].id == "call_1"
        assert resp.tool_calls[1].id == "call_2"

    async def test_no_tool_calls_returns_none(self) -> None:
        response = _oai_make_response_with_tool_calls(
            tool_calls=None, text="No tools needed", finish_reason="stop"
        )
        client = _oai_make_client(response)
        provider = OpenAIProvider(client=client)
        resp = await provider.send(USER_MSG, "gpt-5.2", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is None

    async def test_finish_reason_tool_calls(self) -> None:
        response = _oai_make_response_with_tool_calls(
            tool_calls=[
                {
                    "id": "call_1",
                    "name": "web_search",
                    "arguments": "{}",
                }
            ],
            finish_reason="tool_calls",
        )
        client = _oai_make_client(response)
        provider = OpenAIProvider(client=client)
        resp = await provider.send(USER_MSG, "gpt-5.2", tools=SAMPLE_TOOLS)
        assert resp.finish_reason == "tool_calls"

    async def test_empty_choices_no_tool_calls(self) -> None:
        response = MagicMock()
        response.choices = []
        response.usage = MagicMock()
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 0
        client = _oai_make_client(response)
        provider = OpenAIProvider(client=client)
        resp = await provider.send(USER_MSG, "gpt-5.2")
        assert resp.tool_calls is None
        assert resp.content == ""


# ═══════════════════════════════════════════════════════════════════
# Anthropic Provider — Tool Call Tests
# ═══════════════════════════════════════════════════════════════════


def _anth_make_response_with_tool_use(
    tool_use_blocks: list[dict[str, Any]] | None = None,
    text: str = "",
    stop_reason: str = "end_turn",
) -> MagicMock:
    """Build an Anthropic mock response with optional tool_use blocks."""
    content_blocks = []

    if text:
        text_block = MagicMock()
        text_block.text = text
        text_block.type = "text"
        content_blocks.append(text_block)

    if tool_use_blocks:
        for tu in tool_use_blocks:
            block = MagicMock()
            block.type = "tool_use"
            block.id = tu["id"]
            block.name = tu["name"]
            block.input = tu["input"]
            # Ensure hasattr(block, "text") returns False for tool_use blocks
            del block.text
            content_blocks.append(block)

    response = MagicMock()
    response.content = content_blocks
    response.stop_reason = stop_reason
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    response.usage = usage
    return response


def _anth_make_client(response: Any = None) -> MagicMock:
    import anthropic

    client = MagicMock(spec=anthropic.AsyncAnthropic)
    client.messages = MagicMock()
    if response is None:
        response = _anth_make_response_with_tool_use(text="Hello")
    client.messages.create = AsyncMock(return_value=response)
    return client


class TestAnthropicToolForwarding:
    async def test_tools_param_forwarded(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        client = _anth_make_client()
        provider = AnthropicProvider(client=client)
        await provider.send(USER_MSG, "claude-opus-4-6", tools=SAMPLE_TOOLS)
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["tools"] is SAMPLE_TOOLS

    async def test_no_tools_param_omitted(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        client = _anth_make_client()
        provider = AnthropicProvider(client=client)
        await provider.send(USER_MSG, "claude-opus-4-6")
        call_kwargs = client.messages.create.call_args.kwargs
        assert "tools" not in call_kwargs


class TestAnthropicToolCallParsing:
    async def test_single_tool_use_parsed(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        response = _anth_make_response_with_tool_use(
            tool_use_blocks=[
                {
                    "id": "toolu_abc123",
                    "name": "web_search",
                    "input": {"query": "cats"},
                }
            ],
            stop_reason="tool_use",
        )
        client = _anth_make_client(response)
        provider = AnthropicProvider(client=client)
        resp = await provider.send(USER_MSG, "claude-opus-4-6", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert isinstance(tc, ToolCallData)
        assert tc.id == "toolu_abc123"
        assert tc.name == "web_search"
        assert json.loads(tc.arguments) == {"query": "cats"}

    async def test_multiple_tool_use_parsed(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        response = _anth_make_response_with_tool_use(
            tool_use_blocks=[
                {
                    "id": "toolu_1",
                    "name": "web_search",
                    "input": {"query": "cats"},
                },
                {
                    "id": "toolu_2",
                    "name": "web_search",
                    "input": {"query": "dogs"},
                },
            ],
            stop_reason="tool_use",
        )
        client = _anth_make_client(response)
        provider = AnthropicProvider(client=client)
        resp = await provider.send(USER_MSG, "claude-opus-4-6", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 2
        assert resp.tool_calls[0].id == "toolu_1"
        assert resp.tool_calls[1].id == "toolu_2"

    async def test_text_and_tool_use_combined(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        response = _anth_make_response_with_tool_use(
            text="Let me search for that.",
            tool_use_blocks=[
                {
                    "id": "toolu_1",
                    "name": "web_search",
                    "input": {"query": "cats"},
                }
            ],
            stop_reason="tool_use",
        )
        client = _anth_make_client(response)
        provider = AnthropicProvider(client=client)
        resp = await provider.send(USER_MSG, "claude-opus-4-6", tools=SAMPLE_TOOLS)
        assert resp.content == "Let me search for that."
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1

    async def test_no_tool_use_returns_none(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        response = _anth_make_response_with_tool_use(
            text="No tools needed", stop_reason="end_turn"
        )
        client = _anth_make_client(response)
        provider = AnthropicProvider(client=client)
        resp = await provider.send(USER_MSG, "claude-opus-4-6", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is None

    async def test_finish_reason_tool_use(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        response = _anth_make_response_with_tool_use(
            tool_use_blocks=[
                {
                    "id": "toolu_1",
                    "name": "web_search",
                    "input": {},
                }
            ],
            stop_reason="tool_use",
        )
        client = _anth_make_client(response)
        provider = AnthropicProvider(client=client)
        resp = await provider.send(USER_MSG, "claude-opus-4-6", tools=SAMPLE_TOOLS)
        assert resp.finish_reason == "tool_use"

    async def test_empty_content_no_tool_calls(self) -> None:
        from duh.providers.anthropic import AnthropicProvider

        response = MagicMock()
        response.content = []
        response.stop_reason = "end_turn"
        usage = MagicMock()
        usage.input_tokens = 10
        usage.output_tokens = 0
        usage.cache_read_input_tokens = 0
        usage.cache_creation_input_tokens = 0
        response.usage = usage
        client = _anth_make_client(response)
        provider = AnthropicProvider(client=client)
        resp = await provider.send(USER_MSG, "claude-opus-4-6")
        assert resp.tool_calls is None
        assert resp.content == ""


# ═══════════════════════════════════════════════════════════════════
# Google Provider — Tool Call Tests
# ═══════════════════════════════════════════════════════════════════


def _google_make_response_with_function_calls(
    function_calls: list[dict[str, Any]] | None = None,
    text: str = "",
) -> MagicMock:
    """Build a Google Gemini mock response with optional function calls."""
    response = MagicMock()
    response.text = text or None

    parts = []
    if text:
        text_part = MagicMock()
        text_part.function_call = None
        text_part.text = text
        parts.append(text_part)

    if function_calls:
        for fc in function_calls:
            part = MagicMock()
            part.function_call = MagicMock()
            part.function_call.name = fc["name"]
            part.function_call.args = fc.get("args")
            parts.append(part)

    if parts:
        cand_content = MagicMock()
        cand_content.parts = parts
        candidate = MagicMock()
        candidate.content = cand_content
        response.candidates = [candidate]
    else:
        response.candidates = []

    response.usage_metadata = MagicMock()
    response.usage_metadata.prompt_token_count = 100
    response.usage_metadata.candidates_token_count = 50
    return response


def _google_make_client(response: Any = None) -> MagicMock:
    client = MagicMock()
    if response is None:
        response = _google_make_response_with_function_calls(text="Hello")
    client.aio.models.generate_content = AsyncMock(return_value=response)
    return client


def _mock_genai_config(**kwargs: Any) -> MagicMock:
    """Create a MagicMock that stores config kwargs as attributes."""
    config = MagicMock()
    for k, v in kwargs.items():
        setattr(config, k, v)
    return config


_PATCH_CONFIG = patch(
    "duh.providers.google.genai.types.GenerateContentConfig",
    side_effect=_mock_genai_config,
)


class TestGoogleToolForwarding:
    @_PATCH_CONFIG
    async def test_tools_param_forwarded(self, _mock_cfg: Any) -> None:
        from duh.providers.google import GoogleProvider

        client = _google_make_client()
        provider = GoogleProvider(client=client)
        await provider.send(USER_MSG, "gemini-2.5-flash", tools=SAMPLE_TOOLS)
        call_kwargs = client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs["config"]
        assert config.tools is SAMPLE_TOOLS

    async def test_no_tools_param_not_in_config(self) -> None:
        from duh.providers.google import GoogleProvider

        client = _google_make_client()
        provider = GoogleProvider(client=client)
        await provider.send(USER_MSG, "gemini-2.5-flash")
        call_kwargs = client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs["config"]
        # When tools is not passed, the real config object won't have tools set
        assert not hasattr(config, "tools") or config.tools is None

    async def test_response_format_json(self) -> None:
        from duh.providers.google import GoogleProvider

        client = _google_make_client()
        provider = GoogleProvider(client=client)
        await provider.send(USER_MSG, "gemini-2.5-flash", response_format="json")
        call_kwargs = client.aio.models.generate_content.call_args
        config = call_kwargs.kwargs["config"]
        assert config.response_mime_type == "application/json"


class TestGoogleToolCallParsing:
    @_PATCH_CONFIG
    async def test_single_function_call_parsed(self, _mock_cfg: Any) -> None:
        from duh.providers.google import GoogleProvider

        response = _google_make_response_with_function_calls(
            function_calls=[{"name": "web_search", "args": {"query": "cats"}}]
        )
        client = _google_make_client(response)
        provider = GoogleProvider(client=client)
        resp = await provider.send(USER_MSG, "gemini-2.5-flash", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert isinstance(tc, ToolCallData)
        assert tc.name == "web_search"
        assert tc.id == "google-web_search"
        assert json.loads(tc.arguments) == {"query": "cats"}

    @_PATCH_CONFIG
    async def test_multiple_function_calls_parsed(self, _mock_cfg: Any) -> None:
        from duh.providers.google import GoogleProvider

        response = _google_make_response_with_function_calls(
            function_calls=[
                {"name": "web_search", "args": {"query": "cats"}},
                {"name": "web_search", "args": {"query": "dogs"}},
            ]
        )
        client = _google_make_client(response)
        provider = GoogleProvider(client=client)
        resp = await provider.send(USER_MSG, "gemini-2.5-flash", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 2

    @_PATCH_CONFIG
    async def test_no_function_calls_returns_none(self, _mock_cfg: Any) -> None:
        from duh.providers.google import GoogleProvider

        response = _google_make_response_with_function_calls(text="No tools needed")
        client = _google_make_client(response)
        provider = GoogleProvider(client=client)
        resp = await provider.send(USER_MSG, "gemini-2.5-flash", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is None

    @_PATCH_CONFIG
    async def test_function_call_with_no_args(self, _mock_cfg: Any) -> None:
        from duh.providers.google import GoogleProvider

        response = _google_make_response_with_function_calls(
            function_calls=[{"name": "get_time", "args": None}]
        )
        client = _google_make_client(response)
        provider = GoogleProvider(client=client)
        resp = await provider.send(USER_MSG, "gemini-2.5-flash", tools=SAMPLE_TOOLS)
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert json.loads(resp.tool_calls[0].arguments) == {}

    async def test_no_candidates_no_tool_calls(self) -> None:
        from duh.providers.google import GoogleProvider

        response = MagicMock()
        response.text = ""
        response.candidates = []
        response.usage_metadata = MagicMock()
        response.usage_metadata.prompt_token_count = 10
        response.usage_metadata.candidates_token_count = 0
        client = _google_make_client(response)
        provider = GoogleProvider(client=client)
        resp = await provider.send(USER_MSG, "gemini-2.5-flash")
        assert resp.tool_calls is None

    async def test_candidate_with_no_content(self) -> None:
        from duh.providers.google import GoogleProvider

        response = MagicMock()
        response.text = ""
        candidate = MagicMock()
        candidate.content = None
        response.candidates = [candidate]
        response.usage_metadata = MagicMock()
        response.usage_metadata.prompt_token_count = 10
        response.usage_metadata.candidates_token_count = 0
        client = _google_make_client(response)
        provider = GoogleProvider(client=client)
        resp = await provider.send(USER_MSG, "gemini-2.5-flash")
        assert resp.tool_calls is None
