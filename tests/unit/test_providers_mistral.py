"""Tests for Mistral provider adapter (mocked SDK)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
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
from duh.providers.mistral import (
    PROVIDER_ID,
    MistralProvider,
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
    choice.message.tool_calls = None
    choice.finish_reason = finish_reason

    response = MagicMock()
    response.choices = [choice]
    response.usage = _make_usage(prompt_tokens, completion_tokens)
    return response


def _make_client(response: Any = None) -> MagicMock:
    """Create a mocked Mistral client."""
    client = MagicMock()
    client.chat = MagicMock()
    client.chat.complete_async = AsyncMock(
        return_value=response or _make_response(),
    )
    client.chat.stream_async = AsyncMock()
    return client


def _make_sdk_error(message: str = "error", status_code: int = 400) -> Any:
    """Create a Mistral SDKError with the given status code."""
    from mistralai import models as mm

    raw_response = httpx.Response(status_code=status_code, text=message)
    return mm.SDKError(message=message, raw_response=raw_response, body=message)


class _AsyncStreamIter:
    """Async iterator over mock stream events."""

    def __init__(self, events: list[Any]) -> None:
        self._events = events
        self._idx = 0

    def __aiter__(self) -> _AsyncStreamIter:
        return self

    async def __anext__(self) -> Any:
        if self._idx >= len(self._events):
            raise StopAsyncIteration
        event = self._events[self._idx]
        self._idx += 1
        return event


def _make_stream_event(
    content: str | None = None,
    finish_reason: str | None = None,
    usage: MagicMock | None = None,
) -> MagicMock:
    """Create a mock stream event wrapping a chunk in .data."""
    chunk = MagicMock()
    if content is not None:
        choice = MagicMock()
        choice.delta.content = content
        choice.finish_reason = finish_reason
        chunk.choices = [choice]
    else:
        chunk.choices = []
    chunk.usage = usage

    event = MagicMock()
    event.data = chunk
    return event


# ─── Protocol ─────────────────────────────────────────────────


class TestProtocol:
    def test_provider_id(self):
        provider = MistralProvider(client=_make_client())
        assert provider.provider_id == PROVIDER_ID

    def test_satisfies_protocol(self):
        provider = MistralProvider(client=_make_client())
        assert isinstance(provider, ModelProvider)


# ─── list_models ──────────────────────────────────────────────


class TestListModels:
    async def test_returns_known_models(self):
        provider = MistralProvider(client=_make_client())
        models = await provider.list_models()
        assert len(models) >= 4
        assert all(isinstance(m, ModelInfo) for m in models)

    async def test_all_models_are_mistral(self):
        provider = MistralProvider(client=_make_client())
        models = await provider.list_models()
        assert all(m.provider_id == PROVIDER_ID for m in models)

    async def test_mistral_large_model_present(self):
        provider = MistralProvider(client=_make_client())
        models = await provider.list_models()
        ids = {m.model_id for m in models}
        assert "mistral-large-latest" in ids

    async def test_models_have_costs(self):
        provider = MistralProvider(client=_make_client())
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
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "mistral-large-latest")
        assert isinstance(resp, ModelResponse)

    async def test_content_extracted(self):
        client = _make_client(_make_response(text="The answer is 42"))
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "mistral-large-latest")
        assert resp.content == "The answer is 42"

    async def test_usage_extracted(self):
        client = _make_client(
            _make_response(prompt_tokens=200, completion_tokens=80),
        )
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "mistral-large-latest")
        assert isinstance(resp.usage, TokenUsage)
        assert resp.usage.input_tokens == 200
        assert resp.usage.output_tokens == 80

    async def test_latency_tracked(self):
        client = _make_client()
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "mistral-large-latest")
        assert resp.latency_ms >= 0

    async def test_model_info_resolved(self):
        client = _make_client()
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "mistral-large-latest")
        assert resp.model_info.model_id == "mistral-large-latest"
        assert resp.model_info.provider_id == PROVIDER_ID

    async def test_unknown_model_gets_generic_info(self):
        client = _make_client()
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "mistral-unknown-99")
        assert resp.model_info.model_id == "mistral-unknown-99"
        assert resp.model_info.input_cost_per_mtok == 0.0

    async def test_passes_params_to_sdk(self):
        client = _make_client()
        provider = MistralProvider(client=client)
        msgs = [
            PromptMessage(role="system", content="Be concise"),
            PromptMessage(role="user", content="test"),
        ]
        await provider.send(
            msgs,
            "mistral-large-latest",
            max_tokens=1000,
            temperature=0.3,
            stop_sequences=["STOP"],
        )
        call_kwargs = client.chat.complete_async.call_args.kwargs
        assert call_kwargs["model"] == "mistral-large-latest"
        assert call_kwargs["max_tokens"] == 1000
        assert call_kwargs["temperature"] == 0.3
        assert call_kwargs["stop"] == ["STOP"]
        # System message stays in messages array for Mistral
        assert call_kwargs["messages"][0]["role"] == "system"
        assert call_kwargs["messages"][0]["content"] == "Be concise"

    async def test_raw_response_preserved(self):
        mock_resp = _make_response()
        client = _make_client(mock_resp)
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        resp = await provider.send(msgs, "mistral-large-latest")
        assert resp.raw_response is mock_resp


# ─── stream ───────────────────────────────────────────────────


class TestStream:
    async def test_yields_content_chunks(self):
        events = [
            _make_stream_event(content="Hello"),
            _make_stream_event(content=" world"),
            _make_stream_event(usage=_make_usage(100, 50)),
        ]
        client = _make_client()
        client.chat.stream_async = AsyncMock(
            return_value=_AsyncStreamIter(events),
        )
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]

        result = []
        async for chunk in provider.stream(msgs, "mistral-large-latest"):
            result.append(chunk)

        assert len(result) == 3
        assert result[0].text == "Hello"
        assert result[1].text == " world"
        assert result[2].is_final
        assert result[2].text == ""

    async def test_final_chunk_has_usage(self):
        events = [
            _make_stream_event(content="Hi"),
            _make_stream_event(usage=_make_usage(150, 75)),
        ]
        client = _make_client()
        client.chat.stream_async = AsyncMock(
            return_value=_AsyncStreamIter(events),
        )
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]

        result = []
        async for chunk in provider.stream(msgs, "mistral-large-latest"):
            result.append(chunk)

        final = result[-1]
        assert final.is_final
        assert final.usage is not None
        assert final.usage.input_tokens == 150
        assert final.usage.output_tokens == 75

    async def test_error_during_stream(self):
        client = _make_client()
        client.chat.stream_async = AsyncMock(
            side_effect=_make_sdk_error("bad key", 401),
        )
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        with pytest.raises(ProviderAuthError):
            async for _ in provider.stream(msgs, "mistral-large-latest"):
                pass


# ─── Error Mapping ────────────────────────────────────────────


class TestErrorMapping:
    def test_auth_error(self):
        err = _make_sdk_error("auth failed", 401)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderAuthError)

    def test_rate_limit_error(self):
        err = _make_sdk_error("rate limited", 429)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderRateLimitError)

    def test_timeout_error(self):
        err = _make_sdk_error("timeout", 408)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderTimeoutError)

    def test_not_found_error(self):
        err = _make_sdk_error("not found", 404)
        mapped = _map_error(err)
        assert isinstance(mapped, ModelNotFoundError)

    def test_unknown_sdk_error_maps_to_overloaded(self):
        err = _make_sdk_error("server error", 500)
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderOverloadedError)

    def test_validation_error_maps_to_overloaded(self):
        from mistralai import models as mm

        raw_response = httpx.Response(status_code=422, text="validation error")
        err = mm.HTTPValidationError(data=None, raw_response=raw_response, body="")
        mapped = _map_error(err)
        assert isinstance(mapped, ProviderOverloadedError)

    async def test_send_raises_mapped_error(self):
        client = _make_client()
        client.chat.complete_async.side_effect = _make_sdk_error("bad key", 401)
        provider = MistralProvider(client=client)
        msgs = [PromptMessage(role="user", content="test")]
        with pytest.raises(ProviderAuthError):
            await provider.send(msgs, "mistral-large-latest")


# ─── health_check ─────────────────────────────────────────────


class TestHealthCheck:
    async def test_healthy_when_api_responds(self):
        client = _make_client()
        provider = MistralProvider(client=client)
        assert await provider.health_check() is True

    async def test_unhealthy_on_error(self):
        client = _make_client()
        client.chat.complete_async.side_effect = Exception(
            "connection failed",
        )
        provider = MistralProvider(client=client)
        assert await provider.health_check() is False
