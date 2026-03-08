"""Tests for native provider web search support."""

from __future__ import annotations

from typing import Any, ClassVar
from unittest.mock import AsyncMock, MagicMock

from duh.config.schema import WebSearchConfig
from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    ModelResponse,
    PromptMessage,
    TokenUsage,
)

# ── Helpers ────────────────────────────────────────────────────────


def _model_info(provider: str = "test", model: str = "m1") -> ModelInfo:
    return ModelInfo(
        provider_id=provider,
        model_id=model,
        display_name="Test",
        capabilities=ModelCapability.TEXT,
        context_window=128_000,
        max_output_tokens=4096,
        input_cost_per_mtok=0.0,
        output_cost_per_mtok=0.0,
    )


def _text_response(provider: str = "test") -> ModelResponse:
    return ModelResponse(
        content="ok",
        model_info=_model_info(provider),
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        finish_reason="stop",
        latency_ms=1.0,
    )


_MESSAGES = [PromptMessage(role="user", content="What happened today?")]


def _make_anthropic_client(mock_msg: object) -> AsyncMock:
    """Create a mocked Anthropic client with stream support."""
    mock_client = AsyncMock()
    stream_cm = MagicMock()
    stream_cm.get_final_message = AsyncMock(return_value=mock_msg)
    stream_cm.__aenter__ = AsyncMock(return_value=stream_cm)
    stream_cm.__aexit__ = AsyncMock(return_value=False)
    mock_client.messages.stream = MagicMock(return_value=stream_cm)
    return mock_client


def _make_anthropic_msg() -> MagicMock:
    """Create a minimal Anthropic response message."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="result", type="text")]
    mock_msg.stop_reason = "stop"
    mock_msg.usage = MagicMock(
        input_tokens=10,
        output_tokens=5,
        cache_read_input_tokens=0,
        cache_creation_input_tokens=0,
    )
    return mock_msg


# ── Anthropic ──────────────────────────────────────────────────────


class TestAnthropicNativeSearch:
    async def test_web_search_injects_server_tool(self) -> None:
        """web_search=True adds Anthropic server tool to kwargs."""
        from duh.providers.anthropic import AnthropicProvider

        mock_msg = _make_anthropic_msg()
        mock_client = _make_anthropic_client(mock_msg)

        provider = AnthropicProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "claude-sonnet-4-6",
            web_search=True,
        )

        call_kwargs = mock_client.messages.stream.call_args[1]
        tools = call_kwargs["tools"]
        assert any(t.get("type", "").startswith("web_search") for t in tools), (
            "Server tool not found in tools"
        )

    async def test_web_search_false_no_server_tool(self) -> None:
        """web_search=False does not add server tool."""
        from duh.providers.anthropic import AnthropicProvider

        mock_msg = _make_anthropic_msg()
        mock_client = _make_anthropic_client(mock_msg)

        provider = AnthropicProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "claude-sonnet-4-6",
            web_search=False,
        )

        call_kwargs = mock_client.messages.stream.call_args[1]
        assert "tools" not in call_kwargs

    async def test_web_search_with_function_tools(self) -> None:
        """web_search=True alongside function tools keeps both."""
        from duh.providers.anthropic import AnthropicProvider

        mock_msg = _make_anthropic_msg()
        mock_client = _make_anthropic_client(mock_msg)

        func_tool: dict[str, object] = {
            "name": "calculator",
            "description": "Math",
            "parameters": {"type": "object", "properties": {}},
        }

        provider = AnthropicProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "claude-sonnet-4-6",
            tools=[func_tool],
            web_search=True,
        )

        call_kwargs = mock_client.messages.stream.call_args[1]
        tools = call_kwargs["tools"]
        # Server tool should be first
        assert tools[0].get("type", "").startswith("web_search")
        # Function tool should follow
        assert tools[1]["name"] == "calculator"


# ── Google ─────────────────────────────────────────────────────────


class TestGoogleNativeSearch:
    async def test_web_search_injects_grounding(self) -> None:
        """web_search=True adds GoogleSearch grounding tool."""
        from duh.providers.google import GoogleProvider

        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=5,
        )

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        provider = GoogleProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "gemini-2.5-flash",
            web_search=True,
        )

        call_kwargs = mock_client.aio.models.generate_content.call_args[1]
        config = call_kwargs["config"]
        tools = config.tools
        assert tools is not None
        # Should have ONLY the GoogleSearch grounding tool
        assert len(tools) == 1
        assert getattr(tools[0], "google_search", None) is not None

    async def test_web_search_replaces_function_tools(self) -> None:
        """web_search=True replaces function tools (they can't coexist)."""
        from duh.providers.google import GoogleProvider

        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=5,
        )

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        func_tool: dict[str, object] = {
            "name": "calculator",
            "description": "Math",
            "parameters": {"type": "object", "properties": {}},
        }

        provider = GoogleProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "gemini-2.5-flash",
            tools=[func_tool],
            web_search=True,
        )

        call_kwargs = mock_client.aio.models.generate_content.call_args[1]
        config = call_kwargs["config"]
        tools = config.tools
        # Grounding replaces function tools — only 1 tool, the grounding one
        assert len(tools) == 1
        assert getattr(tools[0], "google_search", None) is not None

    async def test_web_search_false_no_grounding(self) -> None:
        """web_search=False does not add grounding tool."""
        from duh.providers.google import GoogleProvider

        mock_response = MagicMock()
        mock_response.candidates = []
        mock_response.usage_metadata = MagicMock(
            prompt_token_count=10,
            candidates_token_count=5,
        )

        mock_client = MagicMock()
        mock_client.aio.models.generate_content = AsyncMock(
            return_value=mock_response,
        )

        provider = GoogleProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "gemini-2.5-flash",
            web_search=False,
        )

        call_kwargs = mock_client.aio.models.generate_content.call_args[1]
        config = call_kwargs["config"]
        assert config.tools is None or len(config.tools) == 0


# ── Mistral ────────────────────────────────────────────────────────


class TestMistralNativeSearch:
    async def test_web_search_injects_tool(self) -> None:
        """web_search=True adds web_search tool to kwargs."""
        from duh.providers.mistral import MistralProvider

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="result", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
        )

        mock_client = MagicMock()
        mock_client.chat.complete_async = AsyncMock(return_value=mock_response)

        provider = MistralProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "mistral-large-latest",
            web_search=True,
        )

        call_kwargs = mock_client.chat.complete_async.call_args[1]
        tools = call_kwargs["tools"]
        assert any(t.get("type") == "web_search" for t in tools)

    async def test_web_search_false_no_tool(self) -> None:
        """web_search=False does not add web_search tool."""
        from duh.providers.mistral import MistralProvider

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="result", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
        )

        mock_client = MagicMock()
        mock_client.chat.complete_async = AsyncMock(return_value=mock_response)

        provider = MistralProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "mistral-large-latest",
            web_search=False,
        )

        call_kwargs = mock_client.chat.complete_async.call_args[1]
        assert "tools" not in call_kwargs


# ── OpenAI ─────────────────────────────────────────────────────────


class TestOpenAINativeSearch:
    async def test_search_model_gets_web_search_options(self) -> None:
        """web_search=True + search model adds web_search_options."""
        from duh.providers.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="result", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
        )

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response,
        )

        provider = OpenAIProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "gpt-4o-search-preview",
            web_search=True,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "web_search_options" in call_kwargs

    async def test_standard_model_ignores_web_search(self) -> None:
        """web_search=True + non-search model does NOT add web_search_options."""
        from duh.providers.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="result", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
        )

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response,
        )

        provider = OpenAIProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "gpt-5.4",
            web_search=True,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "web_search_options" not in call_kwargs

    async def test_web_search_false_no_options(self) -> None:
        """web_search=False never adds web_search_options."""
        from duh.providers.openai import OpenAIProvider

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="result", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
        )

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response,
        )

        provider = OpenAIProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "gpt-4o-search-preview",
            web_search=False,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert "web_search_options" not in call_kwargs


# ── Perplexity ─────────────────────────────────────────────────────


class TestPerplexityNativeSearch:
    async def test_web_search_is_noop(self) -> None:
        """web_search=True changes nothing for Perplexity (always-on)."""
        from duh.providers.perplexity import PerplexityProvider

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content="result", tool_calls=None),
                finish_reason="stop",
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
        )

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=mock_response,
        )

        provider = PerplexityProvider(client=mock_client)
        await provider.send(
            _MESSAGES,
            "sonar",
            web_search=True,
        )

        call_kwargs = mock_client.chat.completions.create.call_args[1]
        # No web_search_options or special tools added
        assert "web_search_options" not in call_kwargs
        assert "tools" not in call_kwargs


# ── Config ─────────────────────────────────────────────────────────


class TestWebSearchConfig:
    def test_native_defaults_true(self) -> None:
        """WebSearchConfig.native defaults to True."""
        cfg = WebSearchConfig()
        assert cfg.native is True

    def test_native_explicit_false(self) -> None:
        """WebSearchConfig.native can be set to False."""
        cfg = WebSearchConfig(native=False)
        assert cfg.native is False


# ── Catalog capabilities ──────────────────────────────────────────


class TestWebSearchCapability:
    def test_web_search_in_flag(self) -> None:
        """WEB_SEARCH exists as a ModelCapability flag."""
        assert hasattr(ModelCapability, "WEB_SEARCH")

    def test_anthropic_has_web_search(self) -> None:
        from duh.providers.catalog import PROVIDER_CAPS

        assert ModelCapability.WEB_SEARCH in PROVIDER_CAPS["anthropic"]

    def test_google_has_web_search(self) -> None:
        from duh.providers.catalog import PROVIDER_CAPS

        assert ModelCapability.WEB_SEARCH in PROVIDER_CAPS["google"]

    def test_mistral_has_web_search(self) -> None:
        from duh.providers.catalog import PROVIDER_CAPS

        assert ModelCapability.WEB_SEARCH in PROVIDER_CAPS["mistral"]

    def test_perplexity_has_web_search(self) -> None:
        from duh.providers.catalog import PROVIDER_CAPS

        assert ModelCapability.WEB_SEARCH in PROVIDER_CAPS["perplexity"]

    def test_openai_no_web_search(self) -> None:
        from duh.providers.catalog import PROVIDER_CAPS

        assert ModelCapability.WEB_SEARCH not in PROVIDER_CAPS["openai"]


# ── tool_augmented_send integration ──────────────────────────────


class TestAugmentedSendWebSearch:
    async def test_web_search_filters_ddg_tool(self) -> None:
        """web_search=True removes 'web_search' from tools list."""
        from duh.tools.augmented_send import tool_augmented_send
        from duh.tools.registry import ToolRegistry

        call_log: list[dict[str, Any]] = []

        class _MockProvider:
            provider_id = "test"

            async def send(
                self, messages: Any, model_id: str, **kwargs: Any
            ) -> ModelResponse:
                call_log.append(kwargs)
                return _text_response()

        class _WebSearchTool:
            name = "web_search"
            description = "Search the web"
            parameters_schema: ClassVar[dict[str, Any]] = {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            }

            async def execute(self, **kwargs: Any) -> str:
                return "results"

        class _OtherTool:
            name = "calculator"
            description = "Math"
            parameters_schema: ClassVar[dict[str, Any]] = {
                "type": "object",
                "properties": {},
            }

            async def execute(self, **kwargs: Any) -> str:
                return "42"

        registry = ToolRegistry()
        registry.register(_WebSearchTool())
        registry.register(_OtherTool())

        await tool_augmented_send(
            _MockProvider(),  # type: ignore[arg-type]
            "m1",
            _MESSAGES,
            registry,
            web_search=True,
        )

        # web_search tool should be filtered out, calculator remains
        tools = call_log[0]["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "calculator"
        # web_search flag should be passed through
        assert call_log[0]["web_search"] is True

    async def test_no_web_search_keeps_ddg_tool(self) -> None:
        """web_search=False keeps 'web_search' in tools list."""
        from duh.tools.augmented_send import tool_augmented_send
        from duh.tools.registry import ToolRegistry

        call_log: list[dict[str, Any]] = []

        class _MockProvider:
            provider_id = "test"

            async def send(
                self, messages: Any, model_id: str, **kwargs: Any
            ) -> ModelResponse:
                call_log.append(kwargs)
                return _text_response()

        class _WebSearchTool:
            name = "web_search"
            description = "Search the web"
            parameters_schema: ClassVar[dict[str, Any]] = {
                "type": "object",
                "properties": {"query": {"type": "string"}},
            }

            async def execute(self, **kwargs: Any) -> str:
                return "results"

        registry = ToolRegistry()
        registry.register(_WebSearchTool())

        await tool_augmented_send(
            _MockProvider(),  # type: ignore[arg-type]
            "m1",
            _MESSAGES,
            registry,
            web_search=False,
        )

        tools = call_log[0]["tools"]
        assert len(tools) == 1
        assert tools[0]["name"] == "web_search"
        assert call_log[0]["web_search"] is False
