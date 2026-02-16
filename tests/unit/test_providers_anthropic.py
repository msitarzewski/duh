"""Tests for Anthropic provider adapter (mocked SDK)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import anthropic
import pytest

from duh.core.errors import (
    ModelNotFoundError,
    ProviderAuthError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from duh.providers.anthropic import (
    PROVIDER_ID,
    AnthropicProvider,
    _build_messages,
    _map_error,
)
from duh.providers.base import (
    ModelInfo,
    ModelProvider,
    ModelResponse,
    PromptMessage,
    TokenUsage,
)

# ─── Helpers ──────────────────────────────────────────────────


def _make_usage(input_tokens: int = 100, output_tokens: int = 50) -> MagicMock:
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0
    return usage


def _make_response(
    text: str = "Hello world",
    stop_reason: str = "end_turn",
    input_tokens: int = 100,
    output_tokens: int = 50,
) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text

    response = MagicMock()
    response.content = [content_block]
    response.usage = _make_usage(input_tokens, output_tokens)
    response.stop_reason = stop_reason
    return response


def _make_client(response: Any = None) -> MagicMock:
    """Create a mocked AsyncAnthropic client."""
    client = MagicMock(spec=anthropic.AsyncAnthropic)
    client.messages = MagicMock()
    client.messages.create = AsyncMock(return_value=response or _make_response())
    return client


# ─── Protocol ─────────────────────────────────────────────────


class TestProtocol:
    def test_provider_id(self):
        provider = AnthropicProvider(client=_make_client())
        assert provider.provider_id == PROVIDER_ID

    def test_satisfies_protocol(self):
        provider = AnthropicProvider(client=_make_client())
        assert isinstance(provider, ModelProvider)


# ─── list_models ──────────────────────────────────────────────


class TestListModels:
    async def test_returns_known_models(self):
        provider = AnthropicProvider(client=_make_client())
        models = await provider.list_models()
        assert len(models) >= 3
        assert all(isinstance(m, ModelInfo) for m in models)

    async def test_all_models_are_anthropic(self):
        provider = AnthropicProvider(client=_make_client())
        models = await provider.list_models()
        assert all(m.provider_id == PROVIDER_ID for m in models)

    async def test_opus_model_present(self):
        provider = AnthropicProvider(client=_make_client())
        models = await provider.list_models()
        ids = {m.model_id for m in models}
        assert "claude-opus-4-6" in ids

    async def test_models_have_costs(self):
        provider = AnthropicProvider(client=_make_client())
        models = await provider.list_models()
        for m in models:
            assert m.input_cost_per_mtok > 0
            assert m.output_cost_per_mtok > 0


# ─── _build_messages ──────────────────────────────────────────


class TestBuildMessages:
    def test_user_message_only(self):
        msgs = [PromptMessage(role="user", content="Hello")]
        system, api_msgs = _build_messages(msgs)
        assert system is anthropic.NOT_GIVEN
        assert api_msgs == [{"role": "user", "content": "Hello"}]

    def test_system_extracted(self):
        msgs = [
            PromptMessage(role="system", content="Be helpful"),
            PromptMessage(role="user", content="Hi"),
        ]
        system, api_msgs = _build_messages(msgs)
        assert system == "Be helpful"
        assert len(api_msgs) == 1
        assert api_msgs[0]["role"] == "user"

    def test_multi_turn(self):
        msgs = [
            PromptMessage(role="system", content="System"),
            PromptMessage(role="user", content="Q1"),
            PromptMessage(role="assistant", content="A1"),
            PromptMessage(role="user", content="Q2"),
        ]
        system, api_msgs = _build_messages(msgs)
        assert system == "System"
        assert len(api_msgs) == 3
        assert api_msgs[0]["role"] == "user"
        assert api_msgs[1]["role"] == "assistant"
        assert api_msgs[2]["role"] == "user"


# ─── send ─────────────────────────────────────────────────────


class TestSend:
    async def test_returns_model_response(self):
        client = _make_client()
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "claude-opus-4-6")
        assert isinstance(resp, ModelResponse)

    async def test_content_extracted(self):
        client = _make_client(_make_response(text="The answer is 42"))
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "claude-opus-4-6")
        assert resp.content == "The answer is 42"

    async def test_usage_extracted(self):
        client = _make_client(_make_response(input_tokens=200, output_tokens=80))
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "claude-opus-4-6")
        assert isinstance(resp.usage, TokenUsage)
        assert resp.usage.input_tokens == 200
        assert resp.usage.output_tokens == 80

    async def test_latency_tracked(self):
        client = _make_client()
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "claude-opus-4-6")
        assert resp.latency_ms >= 0

    async def test_model_info_resolved(self):
        client = _make_client()
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "claude-opus-4-6")
        assert resp.model_info.model_id == "claude-opus-4-6"
        assert resp.model_info.provider_id == PROVIDER_ID

    async def test_unknown_model_gets_generic_info(self):
        client = _make_client()
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "claude-unknown-99")
        assert resp.model_info.model_id == "claude-unknown-99"
        assert resp.model_info.input_cost_per_mtok == 0.0

    async def test_passes_params_to_sdk(self):
        client = _make_client()
        provider = AnthropicProvider(client=client)
        msgs = [
            PromptMessage(role="system", content="Be concise"),
            PromptMessage(role="user", content="test"),
        ]
        await provider.send(
            msgs,
            "claude-opus-4-6",
            max_tokens=1000,
            temperature=0.3,
            stop_sequences=["STOP"],
        )
        call_kwargs = client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-opus-4-6"
        assert call_kwargs["max_tokens"] == 1000
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["system"] == "Be concise"
        assert call_kwargs["stop_sequences"] == ["STOP"]

    async def test_raw_response_preserved(self):
        mock_resp = _make_response()
        client = _make_client(mock_resp)
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "claude-opus-4-6")
        assert resp.raw_response is mock_resp


# ─── Error Mapping ────────────────────────────────────────────


class TestErrorMapping:
    def _make_api_error(self, cls: type, status_code: int = 400) -> anthropic.APIError:
        response = MagicMock()
        response.status_code = status_code
        response.headers = {}
        return cls(
            message="test error",
            response=response,
            body=None,
        )

    def test_auth_error(self):
        err = self._make_api_error(anthropic.AuthenticationError, 401)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderAuthError)

    def test_rate_limit_error(self):
        err = self._make_api_error(anthropic.RateLimitError, 429)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderRateLimitError)

    def test_rate_limit_with_retry_after(self):
        err = self._make_api_error(anthropic.RateLimitError, 429)
        err.response.headers = {"retry-after": "30"}
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderRateLimitError)
        assert mapped.retry_after == 30.0

    def test_timeout_error(self):
        err = anthropic.APITimeoutError(request=MagicMock())
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderTimeoutError)

    def test_internal_server_error(self):
        err = self._make_api_error(anthropic.InternalServerError, 500)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderOverloadedError)

    def test_not_found_error(self):
        err = self._make_api_error(anthropic.NotFoundError, 404)
        mapped = _map_error(err)
        assert isinstance(mapped, ModelNotFoundError)

    def test_unknown_api_error_maps_to_overloaded(self):
        err = self._make_api_error(anthropic.UnprocessableEntityError, 422)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderOverloadedError)

    async def test_send_raises_mapped_error(self):
        client = _make_client()
        client.messages.create.side_effect = anthropic.AuthenticationError(
            message="bad key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        provider = AnthropicProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        with pytest.raises(ProviderAuthError):
            await provider.send(msgs, "claude-opus-4-6")


# ─── health_check ─────────────────────────────────────────────


class TestHealthCheck:
    async def test_healthy_when_api_responds(self):
        client = _make_client()
        provider = AnthropicProvider(client=client)
        assert await provider.health_check() is True

    async def test_unhealthy_on_error(self):
        client = _make_client()
        client.messages.create.side_effect = Exception("connection failed")
        provider = AnthropicProvider(client=client)
        assert await provider.health_check() is False
