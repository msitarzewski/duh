"""Tests for OpenAI provider adapter (mocked SDK)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from duh.core.errors import (
    ModelNotFoundError,
    ProviderAuthError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from duh.providers.base import (
    ModelInfo,
    ModelProvider,
    ModelResponse,
    PromptMessage,
    TokenUsage,
)
from duh.providers.openai import (
    PROVIDER_ID,
    OpenAIProvider,
    _build_messages,
    _map_error,
)

# ─── Helpers ──────────────────────────────────────────────────


def _make_usage(prompt_tokens: int = 100, completion_tokens: int = 50) -> MagicMock:
    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens
    return usage


def _make_response(
    text: str = "Hello world",
    finish_reason: str = "stop",
    prompt_tokens: int = 100,
    completion_tokens: int = 50,
) -> MagicMock:
    choice = MagicMock()
    choice.message.content = text
    choice.finish_reason = finish_reason

    response = MagicMock()
    response.choices = [choice]
    response.usage = _make_usage(prompt_tokens, completion_tokens)
    return response


def _make_client(response: Any = None) -> MagicMock:
    """Create a mocked AsyncOpenAI client."""
    client = MagicMock(spec=openai.AsyncOpenAI)
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=response or _make_response(),
    )
    return client


class _AsyncChunkIter:
    """Async iterator over mock stream chunks."""

    def __init__(self, chunks: list[Any]) -> None:
        self._chunks = chunks
        self._idx = 0

    def __aiter__(self) -> _AsyncChunkIter:
        return self

    async def __anext__(self) -> Any:
        if self._idx >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._idx]
        self._idx += 1
        return chunk


def _make_stream_chunk(
    content: str | None = None,
    finish_reason: str | None = None,
    usage: MagicMock | None = None,
) -> MagicMock:
    """Create a mock ChatCompletionChunk."""
    chunk = MagicMock()
    if content is not None:
        choice = MagicMock()
        choice.delta.content = content
        choice.finish_reason = finish_reason
        chunk.choices = [choice]
    else:
        chunk.choices = []
    chunk.usage = usage
    return chunk


# ─── Protocol ─────────────────────────────────────────────────


class TestProtocol:
    def test_provider_id(self):
        provider = OpenAIProvider(client=_make_client())
        assert provider.provider_id == PROVIDER_ID

    def test_satisfies_protocol(self):
        provider = OpenAIProvider(client=_make_client())
        assert isinstance(provider, ModelProvider)


# ─── list_models ──────────────────────────────────────────────


class TestListModels:
    async def test_returns_known_models(self):
        provider = OpenAIProvider(client=_make_client())
        models = await provider.list_models()
        assert len(models) >= 3
        assert all(isinstance(m, ModelInfo) for m in models)

    async def test_all_models_are_openai(self):
        provider = OpenAIProvider(client=_make_client())
        models = await provider.list_models()
        assert all(m.provider_id == PROVIDER_ID for m in models)

    async def test_gpt52_model_present(self):
        provider = OpenAIProvider(client=_make_client())
        models = await provider.list_models()
        ids = {m.model_id for m in models}
        assert "gpt-5.2" in ids

    async def test_models_have_costs(self):
        provider = OpenAIProvider(client=_make_client())
        models = await provider.list_models()
        for m in models:
            assert m.input_cost_per_mtok > 0
            assert m.output_cost_per_mtok > 0


# ─── _build_messages ──────────────────────────────────────────


class TestBuildMessages:
    def test_user_message_only(self):
        msgs = [PromptMessage(role="user", content="Hello")]
        api_msgs = _build_messages(msgs)
        assert api_msgs == [{"role": "user", "content": "Hello"}]

    def test_system_included_in_messages(self):
        msgs = [
            PromptMessage(role="system", content="Be helpful"),
            PromptMessage(role="user", content="Hi"),
        ]
        api_msgs = _build_messages(msgs)
        assert len(api_msgs) == 2
        assert api_msgs[0] == {"role": "system", "content": "Be helpful"}
        assert api_msgs[1] == {"role": "user", "content": "Hi"}

    def test_multi_turn(self):
        msgs = [
            PromptMessage(role="system", content="System"),
            PromptMessage(role="user", content="Q1"),
            PromptMessage(role="assistant", content="A1"),
            PromptMessage(role="user", content="Q2"),
        ]
        api_msgs = _build_messages(msgs)
        assert len(api_msgs) == 4
        assert api_msgs[0]["role"] == "system"
        assert api_msgs[1]["role"] == "user"
        assert api_msgs[2]["role"] == "assistant"
        assert api_msgs[3]["role"] == "user"


# ─── send ─────────────────────────────────────────────────────


class TestSend:
    async def test_returns_model_response(self):
        client = _make_client()
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "gpt-5.2")
        assert isinstance(resp, ModelResponse)

    async def test_content_extracted(self):
        client = _make_client(_make_response(text="The answer is 42"))
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "gpt-5.2")
        assert resp.content == "The answer is 42"

    async def test_usage_extracted(self):
        client = _make_client(
            _make_response(prompt_tokens=200, completion_tokens=80),
        )
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "gpt-5.2")
        assert isinstance(resp.usage, TokenUsage)
        assert resp.usage.input_tokens == 200
        assert resp.usage.output_tokens == 80

    async def test_latency_tracked(self):
        client = _make_client()
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "gpt-5.2")
        assert resp.latency_ms >= 0

    async def test_model_info_resolved(self):
        client = _make_client()
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "gpt-5.2")
        assert resp.model_info.model_id == "gpt-5.2"
        assert resp.model_info.provider_id == PROVIDER_ID

    async def test_unknown_model_gets_generic_info(self):
        client = _make_client()
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "gpt-unknown-99")
        assert resp.model_info.model_id == "gpt-unknown-99"
        assert resp.model_info.input_cost_per_mtok == 0.0

    async def test_passes_params_to_sdk(self):
        client = _make_client()
        provider = OpenAIProvider(client=client)
        msgs = [
            PromptMessage(role="system", content="Be concise"),
            PromptMessage(role="user", content="test"),
        ]
        await provider.send(
            msgs,
            "gpt-5.2",
            max_tokens=1000,
            temperature=0.3,
            stop_sequences=["STOP"],
        )
        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-5.2"
        assert call_kwargs["max_completion_tokens"] == 1000
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["stop"] == ["STOP"]
        # System message stays in messages array for OpenAI
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "Be concise"

    async def test_raw_response_preserved(self):
        mock_resp = _make_response()
        client = _make_client(mock_resp)
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "gpt-5.2")
        assert resp.raw_response is mock_resp


# ─── stream ───────────────────────────────────────────────────


class TestStream:
    async def test_yields_content_chunks(self):
        chunks = [
            _make_stream_chunk(content="Hello"),
            _make_stream_chunk(content=" world"),
            _make_stream_chunk(usage=_make_usage(100, 50)),
        ]
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            return_value=_AsyncChunkIter(chunks),
        )
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]

        result = []
        async for chunk in provider.stream(msgs, "gpt-5.2"):
            result.append(chunk)

        assert len(result) == 3
        assert result[0].text == "Hello"
        assert result[1].text == " world"
        assert result[2].is_final
        assert result[2].text == ""

    async def test_final_chunk_has_usage(self):
        chunks = [
            _make_stream_chunk(content="Hi"),
            _make_stream_chunk(usage=_make_usage(150, 75)),
        ]
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            return_value=_AsyncChunkIter(chunks),
        )
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]

        result = []
        async for chunk in provider.stream(msgs, "gpt-5.2"):
            result.append(chunk)

        final = result[-1]
        assert final.is_final
        assert final.usage is not None
        assert final.usage.input_tokens == 150
        assert final.usage.output_tokens == 75

    async def test_error_during_stream(self):
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            side_effect=openai.AuthenticationError(
                message="bad key",
                response=MagicMock(status_code=401, headers={}),
                body=None,
            ),
        )
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        with pytest.raises(ProviderAuthError):
            async for _ in provider.stream(msgs, "gpt-5.2"):
                pass

    async def test_passes_stream_options(self):
        chunks = [_make_stream_chunk(usage=_make_usage(10, 5))]
        client = _make_client()
        client.chat.completions.create = AsyncMock(
            return_value=_AsyncChunkIter(chunks),
        )
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]

        async for _ in provider.stream(msgs, "gpt-5.2"):
            pass

        call_kwargs = client.chat.completions.create.call_args.kwargs
        assert call_kwargs["stream"] is True
        assert call_kwargs["stream_options"] == {"include_usage": True}


# ─── Error Mapping ────────────────────────────────────────────


class TestErrorMapping:
    def _make_api_error(self, cls: type, status_code: int = 400) -> openai.APIError:
        response = MagicMock()
        response.status_code = status_code
        response.headers = {}
        return cls(
            message="test error",
            response=response,
            body=None,
        )

    def test_auth_error(self):
        err = self._make_api_error(openai.AuthenticationError, 401)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderAuthError)

    def test_rate_limit_error(self):
        err = self._make_api_error(openai.RateLimitError, 429)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderRateLimitError)

    def test_rate_limit_with_retry_after(self):
        err = self._make_api_error(openai.RateLimitError, 429)
        err.response.headers = {"retry-after": "30"}
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderRateLimitError)
        assert mapped.retry_after == 30.0

    def test_timeout_error(self):
        err = openai.APITimeoutError(request=MagicMock())
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderTimeoutError)

    def test_internal_server_error(self):
        err = self._make_api_error(openai.InternalServerError, 500)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderOverloadedError)

    def test_not_found_error(self):
        err = self._make_api_error(openai.NotFoundError, 404)
        mapped = _map_error(err)
        assert isinstance(mapped, ModelNotFoundError)

    def test_unknown_api_error_maps_to_overloaded(self):
        err = self._make_api_error(openai.UnprocessableEntityError, 422)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderOverloadedError)

    async def test_send_raises_mapped_error(self):
        client = _make_client()
        client.chat.completions.create.side_effect = openai.AuthenticationError(
            message="bad key",
            response=MagicMock(status_code=401, headers={}),
            body=None,
        )
        provider = OpenAIProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        with pytest.raises(ProviderAuthError):
            await provider.send(msgs, "gpt-5.2")


# ─── health_check ─────────────────────────────────────────────


class TestHealthCheck:
    async def test_healthy_when_api_responds(self):
        client = _make_client()
        provider = OpenAIProvider(client=client)
        assert await provider.health_check() is True

    async def test_unhealthy_on_error(self):
        client = _make_client()
        client.chat.completions.create.side_effect = Exception(
            "connection failed",
        )
        provider = OpenAIProvider(client=client)
        assert await provider.health_check() is False


# ─── base_url ─────────────────────────────────────────────────


class TestBaseUrl:
    def test_base_url_sets_default_api_key(self):
        """When base_url is provided without api_key, a placeholder
        is used so the SDK doesn't require OPENAI_API_KEY env var."""
        # This tests the constructor path, not an API call.
        # If AsyncOpenAI raises for missing key, this test fails.
        provider = OpenAIProvider(base_url="http://localhost:11434/v1")
        assert provider.provider_id == PROVIDER_ID
