"""Tests for MockProvider — our foundational test infrastructure."""

from __future__ import annotations

from duh.providers.base import (
    ModelInfo,
    ModelProvider,
    ModelResponse,
    PromptMessage,
    StreamChunk,
    TokenUsage,
)
from tests.fixtures.providers import MockProvider
from tests.fixtures.responses import (
    CONSENSUS_AGREEMENT,
    CONSENSUS_BASIC,
    CONSENSUS_DISAGREEMENT,
    MINIMAL,
)

# ─── Protocol Conformance ─────────────────────────────────────


class TestProtocolConformance:
    def test_satisfies_model_provider_protocol(self):
        provider = MockProvider()
        assert isinstance(provider, ModelProvider)

    def test_provider_id(self):
        provider = MockProvider(provider_id="test-provider")
        assert provider.provider_id == "test-provider"

    def test_default_provider_id(self):
        provider = MockProvider()
        assert provider.provider_id == "mock"


# ─── list_models ──────────────────────────────────────────────


class TestListModels:
    async def test_returns_model_info_per_response(self):
        provider = MockProvider(responses=MINIMAL)
        models = await provider.list_models()
        assert len(models) == 2
        assert all(isinstance(m, ModelInfo) for m in models)

    async def test_model_ids_match_response_keys(self):
        provider = MockProvider(responses=MINIMAL)
        models = await provider.list_models()
        model_ids = {m.model_id for m in models}
        assert model_ids == set(MINIMAL.keys())

    async def test_empty_responses_returns_empty(self):
        provider = MockProvider(responses={})
        models = await provider.list_models()
        assert models == []

    async def test_models_are_local(self):
        provider = MockProvider(responses=MINIMAL)
        models = await provider.list_models()
        assert all(m.is_local for m in models)

    async def test_models_have_zero_cost(self):
        provider = MockProvider(responses=MINIMAL)
        models = await provider.list_models()
        for m in models:
            assert m.input_cost_per_mtok == 0.0
            assert m.output_cost_per_mtok == 0.0


# ─── send ─────────────────────────────────────────────────────


class TestSend:
    async def test_returns_model_response(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        resp = await provider.send(messages, "model-a")
        assert isinstance(resp, ModelResponse)

    async def test_returns_canned_content(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        resp = await provider.send(messages, "model-a")
        assert resp.content == MINIMAL["model-a"]

    async def test_unknown_model_returns_default(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        resp = await provider.send(messages, "unknown-model")
        assert resp.content == "Mock response"

    async def test_includes_usage(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        resp = await provider.send(messages, "model-a")
        assert isinstance(resp.usage, TokenUsage)
        assert resp.usage.input_tokens > 0

    async def test_finish_reason_is_stop(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        resp = await provider.send(messages, "model-a")
        assert resp.finish_reason == "stop"

    async def test_records_call(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        await provider.send(messages, "model-a")
        assert len(provider.call_log) == 1
        assert provider.call_log[0]["method"] == "send"
        assert provider.call_log[0]["model_id"] == "model-a"

    async def test_multiple_calls_recorded(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        await provider.send(messages, "model-a")
        await provider.send(messages, "model-b")
        assert len(provider.call_log) == 2

    async def test_kwargs_recorded(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        await provider.send(messages, "model-a", max_tokens=1000, temperature=0.5)
        assert provider.call_log[0]["max_tokens"] == 1000
        assert provider.call_log[0]["temperature"] == 0.5


# ─── stream ───────────────────────────────────────────────────


class TestStream:
    async def test_yields_stream_chunks(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        chunks = [c async for c in provider.stream(messages, "model-a")]
        assert all(isinstance(c, StreamChunk) for c in chunks)

    async def test_final_chunk_is_marked(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        chunks = [c async for c in provider.stream(messages, "model-a")]
        assert chunks[-1].is_final is True
        assert all(not c.is_final for c in chunks[:-1])

    async def test_final_chunk_has_usage(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        chunks = [c async for c in provider.stream(messages, "model-a")]
        assert chunks[-1].usage is not None
        assert all(c.usage is None for c in chunks[:-1])

    async def test_reassembled_content_matches(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        chunks = [c async for c in provider.stream(messages, "model-a")]
        reassembled = "".join(c.text for c in chunks)
        # Words are split and rejoined — allow whitespace variation
        assert reassembled.strip() == MINIMAL["model-a"].strip()

    async def test_records_call(self):
        provider = MockProvider(responses=MINIMAL)
        messages = [PromptMessage(role="user", content="test")]
        _ = [c async for c in provider.stream(messages, "model-a")]
        assert len(provider.call_log) == 1
        assert provider.call_log[0]["method"] == "stream"


# ─── health_check ─────────────────────────────────────────────


class TestHealthCheck:
    async def test_healthy_by_default(self):
        provider = MockProvider()
        assert await provider.health_check() is True

    async def test_unhealthy_when_configured(self):
        provider = MockProvider(healthy=False)
        assert await provider.health_check() is False


# ─── Canned Response Library ──────────────────────────────────


class TestCannedResponses:
    def test_consensus_basic_has_all_roles(self):
        assert "proposer" in CONSENSUS_BASIC
        assert "challenger-1" in CONSENSUS_BASIC
        assert "challenger-2" in CONSENSUS_BASIC
        assert "reviser" in CONSENSUS_BASIC

    def test_consensus_agreement_has_all_roles(self):
        assert "proposer" in CONSENSUS_AGREEMENT
        assert "reviser" in CONSENSUS_AGREEMENT

    def test_consensus_disagreement_has_all_roles(self):
        assert "proposer" in CONSENSUS_DISAGREEMENT
        assert "reviser" in CONSENSUS_DISAGREEMENT

    def test_minimal_has_two_models(self):
        assert len(MINIMAL) == 2

    def test_all_responses_are_nonempty_strings(self):
        for responses in [
            CONSENSUS_BASIC,
            CONSENSUS_AGREEMENT,
            CONSENSUS_DISAGREEMENT,
            MINIMAL,
        ]:
            for key, value in responses.items():
                assert isinstance(key, str)
                assert isinstance(value, str)
                assert len(value) > 0


# ─── Conftest Fixtures ────────────────────────────────────────


class TestConftestFixtures:
    def test_mock_provider_fixture(self, mock_provider):
        assert isinstance(mock_provider, MockProvider)
        assert mock_provider.provider_id == "mock"

    def test_mock_provider_minimal_fixture(self, mock_provider_minimal):
        assert isinstance(mock_provider_minimal, MockProvider)
        assert mock_provider_minimal.provider_id == "mock-minimal"

    def test_make_model_info_fixture(self, make_model_info):
        info = make_model_info()
        assert isinstance(info, ModelInfo)
        assert info.provider_id == "test"

    def test_make_model_info_overrides(self, make_model_info):
        info = make_model_info(provider_id="custom", model_id="custom-model")
        assert info.provider_id == "custom"
        assert info.model_id == "custom-model"

    def test_make_usage_fixture(self, make_usage):
        usage = make_usage()
        assert isinstance(usage, TokenUsage)
        assert usage.input_tokens == 100

    def test_make_usage_overrides(self, make_usage):
        usage = make_usage(input_tokens=500)
        assert usage.input_tokens == 500
