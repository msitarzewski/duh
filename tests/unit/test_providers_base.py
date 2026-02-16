"""Tests for provider data classes and protocol."""

from __future__ import annotations

from typing import TYPE_CHECKING

from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ModelResponse,
    PromptMessage,
    StreamChunk,
    TokenUsage,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


# ─── Fixtures ─────────────────────────────────────────────────


def _make_model_info(**overrides: object) -> ModelInfo:
    defaults = {
        "provider_id": "test",
        "model_id": "test-model",
        "display_name": "Test Model",
        "capabilities": ModelCapability.TEXT | ModelCapability.STREAMING,
        "context_window": 128_000,
        "max_output_tokens": 4096,
        "input_cost_per_mtok": 3.0,
        "output_cost_per_mtok": 15.0,
    }
    defaults.update(overrides)
    return ModelInfo(**defaults)  # type: ignore[arg-type]


def _make_usage(**overrides: object) -> TokenUsage:
    defaults = {"input_tokens": 100, "output_tokens": 50}
    defaults.update(overrides)
    return TokenUsage(**defaults)  # type: ignore[arg-type]


# ─── ModelCapability ──────────────────────────────────────────


class TestModelCapability:
    def test_individual_flags(self):
        assert ModelCapability.TEXT is not ModelCapability.STREAMING

    def test_combination(self):
        caps = (
            ModelCapability.TEXT | ModelCapability.STREAMING | ModelCapability.JSON_MODE
        )
        assert ModelCapability.TEXT in caps
        assert ModelCapability.STREAMING in caps
        assert ModelCapability.JSON_MODE in caps
        assert ModelCapability.VISION not in caps

    def test_all_flags_distinct(self):
        all_caps = [
            ModelCapability.TEXT,
            ModelCapability.STREAMING,
            ModelCapability.TOOL_USE,
            ModelCapability.VISION,
            ModelCapability.JSON_MODE,
            ModelCapability.SYSTEM_PROMPT,
        ]
        values = [c.value for c in all_caps]
        assert len(values) == len(set(values))


# ─── ModelInfo ────────────────────────────────────────────────


class TestModelInfo:
    def test_creation(self):
        info = _make_model_info()
        assert info.provider_id == "test"
        assert info.model_id == "test-model"
        assert info.display_name == "Test Model"
        assert info.context_window == 128_000

    def test_model_ref(self):
        info = _make_model_info(provider_id="anthropic", model_id="claude-opus-4-6")
        assert info.model_ref == "anthropic:claude-opus-4-6"

    def test_is_local_default_false(self):
        info = _make_model_info()
        assert info.is_local is False

    def test_is_local_true(self):
        info = _make_model_info(is_local=True)
        assert info.is_local is True

    def test_frozen(self):
        info = _make_model_info()
        try:
            info.model_id = "other"  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass

    def test_hashable(self):
        info = _make_model_info()
        assert hash(info) is not None
        assert {info}  # can be used in sets

    def test_equality(self):
        a = _make_model_info(model_id="a")
        b = _make_model_info(model_id="a")
        c = _make_model_info(model_id="c")
        assert a == b
        assert a != c

    def test_cost_zero_for_local(self):
        info = _make_model_info(
            is_local=True, input_cost_per_mtok=0.0, output_cost_per_mtok=0.0
        )
        assert info.input_cost_per_mtok == 0.0
        assert info.output_cost_per_mtok == 0.0


# ─── TokenUsage ───────────────────────────────────────────────


class TestTokenUsage:
    def test_creation(self):
        usage = _make_usage()
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50

    def test_total_tokens(self):
        usage = _make_usage(input_tokens=200, output_tokens=80)
        assert usage.total_tokens == 280

    def test_cache_defaults_zero(self):
        usage = _make_usage()
        assert usage.cache_read_tokens == 0
        assert usage.cache_write_tokens == 0

    def test_with_cache(self):
        usage = TokenUsage(
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=80,
            cache_write_tokens=20,
        )
        assert usage.cache_read_tokens == 80
        assert usage.cache_write_tokens == 20

    def test_frozen(self):
        usage = _make_usage()
        try:
            usage.input_tokens = 999  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass


# ─── ModelResponse ────────────────────────────────────────────


class TestModelResponse:
    def test_creation(self):
        info = _make_model_info()
        usage = _make_usage()
        resp = ModelResponse(
            content="Hello",
            model_info=info,
            usage=usage,
            finish_reason="stop",
            latency_ms=123.4,
        )
        assert resp.content == "Hello"
        assert resp.finish_reason == "stop"
        assert resp.latency_ms == 123.4
        assert resp.raw_response is None

    def test_raw_response_excluded_from_repr(self):
        info = _make_model_info()
        usage = _make_usage()
        resp = ModelResponse(
            content="Hi",
            model_info=info,
            usage=usage,
            finish_reason="stop",
            latency_ms=50.0,
            raw_response={"big": "object"},
        )
        assert "big" not in repr(resp)

    def test_mutable(self):
        """ModelResponse is mutable (not frozen) — content can be updated."""
        info = _make_model_info()
        usage = _make_usage()
        resp = ModelResponse(
            content="original",
            model_info=info,
            usage=usage,
            finish_reason="stop",
            latency_ms=10.0,
        )
        resp.content = "updated"
        assert resp.content == "updated"


# ─── StreamChunk ──────────────────────────────────────────────


class TestStreamChunk:
    def test_intermediate_chunk(self):
        chunk = StreamChunk(text="Hello ")
        assert chunk.text == "Hello "
        assert chunk.is_final is False
        assert chunk.usage is None

    def test_final_chunk(self):
        usage = _make_usage()
        chunk = StreamChunk(text=".", is_final=True, usage=usage)
        assert chunk.is_final is True
        assert chunk.usage is not None
        assert chunk.usage.total_tokens == 150

    def test_frozen(self):
        chunk = StreamChunk(text="hi")
        try:
            chunk.text = "bye"  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass


# ─── PromptMessage ────────────────────────────────────────────


class TestPromptMessage:
    def test_creation(self):
        msg = PromptMessage(role="user", content="What is 2+2?")
        assert msg.role == "user"
        assert msg.content == "What is 2+2?"

    def test_system_message(self):
        msg = PromptMessage(role="system", content="You are helpful.")
        assert msg.role == "system"

    def test_frozen(self):
        msg = PromptMessage(role="user", content="hi")
        try:
            msg.role = "system"  # type: ignore[misc]
            raise AssertionError("Should not allow mutation")
        except AttributeError:
            pass


# ─── ModelProvider Protocol ───────────────────────────────────


class TestModelProviderProtocol:
    def test_protocol_is_runtime_checkable(self):
        """Can use isinstance() with ModelProvider."""
        assert hasattr(ModelProvider, "__protocol_attrs__") or hasattr(
            ModelProvider, "__abstractmethods__"
        )

    def test_conforming_class_is_instance(self):
        """A class implementing all methods satisfies the protocol."""

        class FakeProvider:
            @property
            def provider_id(self) -> str:
                return "fake"

            async def list_models(self) -> list[ModelInfo]:
                return []

            async def send(
                self,
                messages: list[PromptMessage],
                model_id: str,
                *,
                max_tokens: int = 4096,
                temperature: float = 0.7,
                stop_sequences: list[str] | None = None,
            ) -> ModelResponse:
                raise NotImplementedError

            async def stream(
                self,
                messages: list[PromptMessage],
                model_id: str,
                *,
                max_tokens: int = 4096,
                temperature: float = 0.7,
                stop_sequences: list[str] | None = None,
            ) -> AsyncIterator[StreamChunk]:
                raise NotImplementedError
                yield  # type: ignore[misc]

            async def health_check(self) -> bool:
                return True

        provider = FakeProvider()
        assert isinstance(provider, ModelProvider)
