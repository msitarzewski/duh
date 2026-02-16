"""Tests for the Google (Gemini) provider adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from duh.core.errors import (
    ModelNotFoundError,
    ProviderAuthError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from duh.providers.base import ModelCapability, PromptMessage
from duh.providers.google import (
    PROVIDER_ID,
    GoogleProvider,
    _build_contents,
    _map_error,
)

# ── Helpers ─────────────────────────────────────────────────────


def _make_genai_error(cls_name: str, message: str) -> Exception:
    """Create a google.genai error with the right constructor signature."""
    from google.genai import errors as genai_errors

    cls = getattr(genai_errors, cls_name)
    try:
        return cls(message)
    except TypeError:
        # Newer SDK requires (message, response_json)
        return cls(message, {})


def _make_response(
    text: str = "Hello",
    prompt_tokens: int = 10,
    candidate_tokens: int = 20,
) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    resp.usage_metadata = MagicMock()
    resp.usage_metadata.prompt_token_count = prompt_tokens
    resp.usage_metadata.candidates_token_count = candidate_tokens
    return resp


def _make_client(response: Any = None) -> MagicMock:
    client = MagicMock()
    if response is None:
        response = _make_response()
    client.aio.models.generate_content = AsyncMock(return_value=response)
    return client


# ── Provider ID ─────────────────────────────────────────────────


def test_provider_id():
    prov = GoogleProvider(client=_make_client())
    assert prov.provider_id == PROVIDER_ID
    assert prov.provider_id == "google"


# ── list_models ─────────────────────────────────────────────────


async def test_list_models():
    prov = GoogleProvider(client=_make_client())
    models = await prov.list_models()
    assert len(models) == 4
    ids = {m.model_id for m in models}
    assert "gemini-3-pro-preview" in ids
    assert "gemini-3-flash-preview" in ids
    assert "gemini-2.5-pro" in ids
    assert "gemini-2.5-flash" in ids
    for m in models:
        assert m.provider_id == "google"
        assert m.capabilities & ModelCapability.TEXT
        assert m.capabilities & ModelCapability.STREAMING
        assert m.context_window > 0
        assert m.input_cost_per_mtok >= 0


# ── _build_contents ─────────────────────────────────────────────


def test_build_contents_with_system():
    msgs = [
        PromptMessage(role="system", content="Be helpful."),
        PromptMessage(role="user", content="Hi"),
    ]
    system, contents = _build_contents(msgs)
    assert system == "Be helpful."
    assert len(contents) == 1
    assert contents[0]["role"] == "user"


def test_build_contents_no_system():
    msgs = [PromptMessage(role="user", content="Hi")]
    system, contents = _build_contents(msgs)
    assert system is None
    assert len(contents) == 1


def test_build_contents_assistant_maps_to_model():
    msgs = [
        PromptMessage(role="user", content="Hi"),
        PromptMessage(role="assistant", content="Hello"),
    ]
    _, contents = _build_contents(msgs)
    assert contents[1]["role"] == "model"


# ── send ────────────────────────────────────────────────────────


async def test_send_basic():
    client = _make_client(_make_response("Test answer", 100, 50))
    prov = GoogleProvider(client=client)
    resp = await prov.send(
        [PromptMessage(role="user", content="Hi")],
        "gemini-2.5-flash",
    )
    assert resp.content == "Test answer"
    assert resp.usage.input_tokens == 100
    assert resp.usage.output_tokens == 50
    assert resp.model_info.provider_id == "google"
    assert resp.latency_ms > 0


async def test_send_with_system_prompt():
    client = _make_client()
    prov = GoogleProvider(client=client)
    await prov.send(
        [
            PromptMessage(role="system", content="Be terse."),
            PromptMessage(role="user", content="Hi"),
        ],
        "gemini-2.5-pro",
    )
    call_kwargs = client.aio.models.generate_content.call_args
    config = call_kwargs.kwargs["config"]
    assert config.system_instruction == "Be terse."


async def test_send_with_stop_sequences():
    client = _make_client()
    prov = GoogleProvider(client=client)
    await prov.send(
        [PromptMessage(role="user", content="Hi")],
        "gemini-2.5-flash",
        stop_sequences=["STOP"],
    )
    call_kwargs = client.aio.models.generate_content.call_args
    config = call_kwargs.kwargs["config"]
    assert config.stop_sequences == ["STOP"]


async def test_send_no_usage_metadata():
    resp = _make_response()
    resp.usage_metadata = None
    client = _make_client(resp)
    prov = GoogleProvider(client=client)
    result = await prov.send(
        [PromptMessage(role="user", content="Hi")],
        "gemini-2.5-flash",
    )
    assert result.usage.input_tokens == 0
    assert result.usage.output_tokens == 0


async def test_send_empty_text():
    resp = _make_response()
    resp.text = None
    client = _make_client(resp)
    prov = GoogleProvider(client=client)
    result = await prov.send(
        [PromptMessage(role="user", content="Hi")],
        "gemini-2.5-flash",
    )
    assert result.content == ""


# ── stream ──────────────────────────────────────────────────────


async def test_stream_basic():
    chunk1 = MagicMock()
    chunk1.text = "Hello "
    chunk1.usage_metadata = None
    chunk2 = MagicMock()
    chunk2.text = "world"
    chunk2.usage_metadata = MagicMock()
    chunk2.usage_metadata.prompt_token_count = 10
    chunk2.usage_metadata.candidates_token_count = 5

    async def mock_stream(*args: Any, **kwargs: Any) -> Any:
        for c in [chunk1, chunk2]:
            yield c

    client = MagicMock()
    client.aio.models.generate_content_stream = AsyncMock(return_value=mock_stream())
    prov = GoogleProvider(client=client)

    chunks = []
    async for c in prov.stream(
        [PromptMessage(role="user", content="Hi")],
        "gemini-2.5-flash",
    ):
        chunks.append(c)

    assert len(chunks) == 3  # "Hello ", "world", final
    assert chunks[0].text == "Hello "
    assert chunks[1].text == "world"
    assert chunks[2].is_final
    assert chunks[2].usage is not None
    assert chunks[2].usage.input_tokens == 10


# ── error mapping ───────────────────────────────────────────────


def test_map_error_auth():
    e = _make_genai_error("ClientError", "API key not valid")
    mapped = _map_error(e)
    assert isinstance(mapped, ProviderAuthError)


def test_map_error_not_found():
    e = _make_genai_error("ClientError", "404 model not found")
    mapped = _map_error(e)
    assert isinstance(mapped, ModelNotFoundError)


def test_map_error_rate_limit():
    e = _make_genai_error("ClientError", "429 rate limit exceeded")
    mapped = _map_error(e)
    assert isinstance(mapped, ProviderRateLimitError)


def test_map_error_server():
    e = _make_genai_error("ServerError", "503 overloaded")
    mapped = _map_error(e)
    assert isinstance(mapped, ProviderOverloadedError)


def test_map_error_timeout():
    e = _make_genai_error("ClientError", "request timed out")
    mapped = _map_error(e)
    assert isinstance(mapped, ProviderTimeoutError)


# ── send error propagation ──────────────────────────────────────


async def test_send_client_error_raises():
    e = _make_genai_error("ClientError", "API key not valid")
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=e)
    prov = GoogleProvider(client=client)
    with pytest.raises(ProviderAuthError):
        await prov.send(
            [PromptMessage(role="user", content="Hi")],
            "gemini-2.5-flash",
        )


async def test_send_server_error_raises():
    e = _make_genai_error("ServerError", "503")
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=e)
    prov = GoogleProvider(client=client)
    with pytest.raises(ProviderOverloadedError):
        await prov.send(
            [PromptMessage(role="user", content="Hi")],
            "gemini-2.5-flash",
        )


# ── health_check ────────────────────────────────────────────────


async def test_health_check_success():
    prov = GoogleProvider(client=_make_client())
    assert await prov.health_check() is True


async def test_health_check_failure():
    client = MagicMock()
    client.aio.models.generate_content = AsyncMock(side_effect=Exception("fail"))
    prov = GoogleProvider(client=client)
    assert await prov.health_check() is False


# ── _resolve_model_info ─────────────────────────────────────────


def test_resolve_known_model():
    prov = GoogleProvider(client=_make_client())
    info = prov._resolve_model_info("gemini-2.5-pro")
    assert info.display_name == "Gemini 2.5 Pro"
    assert info.input_cost_per_mtok == 1.25


def test_resolve_unknown_model():
    prov = GoogleProvider(client=_make_client())
    info = prov._resolve_model_info("gemini-unknown-99")
    assert info.display_name == "Gemini (gemini-unknown-99)"
    assert info.input_cost_per_mtok == 0.0
