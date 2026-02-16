"""Tests for ProviderManager: registration, discovery, routing, cost tracking."""

from __future__ import annotations

import pytest

from duh.core.errors import CostLimitExceededError, ModelNotFoundError
from duh.providers.base import ModelInfo, TokenUsage
from duh.providers.manager import ProviderManager
from tests.fixtures.providers import MockProvider

# ── Helpers ──────────────────────────────────────────────────────


def _make_provider(
    provider_id: str = "mock",
    models: dict[str, str] | None = None,
) -> MockProvider:
    """Create a MockProvider with deterministic responses."""
    return MockProvider(
        provider_id=provider_id,
        responses=models or {"model-a": "response a", "model-b": "response b"},
    )


# ── Registration ─────────────────────────────────────────────────


class TestRegistration:
    async def test_register_single_provider(self) -> None:
        mgr = ProviderManager()
        provider = _make_provider("alpha")
        await mgr.register(provider)

        models = mgr.list_all_models()
        assert len(models) == 2
        refs = {m.model_ref for m in models}
        assert refs == {"alpha:model-a", "alpha:model-b"}

    async def test_register_multiple_providers(self) -> None:
        mgr = ProviderManager()
        await mgr.register(_make_provider("alpha"))
        await mgr.register(_make_provider("beta", {"m1": "r1"}))

        models = mgr.list_all_models()
        assert len(models) == 3
        provider_ids = {m.provider_id for m in models}
        assert provider_ids == {"alpha", "beta"}

    async def test_register_duplicate_provider_raises(self) -> None:
        mgr = ProviderManager()
        await mgr.register(_make_provider("alpha"))

        with pytest.raises(ValueError, match="already registered"):
            await mgr.register(_make_provider("alpha"))

    async def test_unregister_removes_provider_and_models(self) -> None:
        mgr = ProviderManager()
        await mgr.register(_make_provider("alpha"))
        await mgr.register(_make_provider("beta", {"m1": "r1"}))

        mgr.unregister("alpha")
        models = mgr.list_all_models()
        assert len(models) == 1
        assert models[0].provider_id == "beta"

    def test_unregister_unknown_provider_raises(self) -> None:
        mgr = ProviderManager()
        with pytest.raises(KeyError, match="not registered"):
            mgr.unregister("nonexistent")


# ── Model Discovery ─────────────────────────────────────────────


class TestModelDiscovery:
    async def test_list_all_models_empty(self) -> None:
        mgr = ProviderManager()
        assert mgr.list_all_models() == []

    async def test_list_all_models_aggregates(self) -> None:
        mgr = ProviderManager()
        await mgr.register(_make_provider("a", {"m1": "r1", "m2": "r2"}))
        await mgr.register(_make_provider("b", {"m3": "r3"}))

        models = mgr.list_all_models()
        assert len(models) == 3
        refs = {m.model_ref for m in models}
        assert refs == {"a:m1", "a:m2", "b:m3"}

    async def test_get_model_info_found(self) -> None:
        mgr = ProviderManager()
        await mgr.register(_make_provider("alpha"))

        info = mgr.get_model_info("alpha:model-a")
        assert isinstance(info, ModelInfo)
        assert info.provider_id == "alpha"
        assert info.model_id == "model-a"

    async def test_get_model_info_unknown_ref_raises(self) -> None:
        mgr = ProviderManager()
        await mgr.register(_make_provider("alpha"))

        with pytest.raises(ModelNotFoundError, match="no-such-model"):
            mgr.get_model_info("alpha:no-such-model")

    async def test_get_model_info_unknown_provider_raises(self) -> None:
        mgr = ProviderManager()
        with pytest.raises(ModelNotFoundError):
            mgr.get_model_info("nope:model-a")

    async def test_get_model_info_malformed_ref_raises(self) -> None:
        mgr = ProviderManager()
        with pytest.raises(ModelNotFoundError):
            mgr.get_model_info("no-colon-here")


# ── Routing ──────────────────────────────────────────────────────


class TestRouting:
    async def test_get_provider_returns_tuple(self) -> None:
        mgr = ProviderManager()
        provider = _make_provider("alpha")
        await mgr.register(provider)

        resolved_provider, model_id = mgr.get_provider("alpha:model-a")
        assert resolved_provider is provider
        assert model_id == "model-a"

    async def test_get_provider_unknown_ref_raises(self) -> None:
        mgr = ProviderManager()
        with pytest.raises(ModelNotFoundError):
            mgr.get_provider("unknown:model")

    async def test_routing_after_unregister_raises(self) -> None:
        mgr = ProviderManager()
        await mgr.register(_make_provider("alpha"))
        mgr.unregister("alpha")

        with pytest.raises(ModelNotFoundError):
            mgr.get_provider("alpha:model-a")


# ── Cost Tracking ────────────────────────────────────────────────


def _make_model_info(
    provider_id: str = "test",
    model_id: str = "model",
    input_cost: float = 3.0,
    output_cost: float = 15.0,
) -> ModelInfo:
    """Create a ModelInfo with specified pricing."""
    from duh.providers.base import ModelCapability

    return ModelInfo(
        provider_id=provider_id,
        model_id=model_id,
        display_name=f"Test {model_id}",
        capabilities=ModelCapability.TEXT,
        context_window=200_000,
        max_output_tokens=4096,
        input_cost_per_mtok=input_cost,
        output_cost_per_mtok=output_cost,
    )


class TestCostTracking:
    def test_initial_cost_is_zero(self) -> None:
        mgr = ProviderManager()
        assert mgr.total_cost == 0.0
        assert mgr.cost_by_provider == {}

    def test_record_usage_computes_cost(self) -> None:
        mgr = ProviderManager()
        info = _make_model_info(input_cost=3.0, output_cost=15.0)
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)

        call_cost = mgr.record_usage(info, usage)
        # 1M * $3/M + 100K * $15/M = $3 + $1.5 = $4.5
        assert call_cost == pytest.approx(4.5)
        assert mgr.total_cost == pytest.approx(4.5)

    def test_record_usage_accumulates(self) -> None:
        mgr = ProviderManager()
        info = _make_model_info(input_cost=1.0, output_cost=1.0)
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)

        mgr.record_usage(info, usage)  # $2.0
        mgr.record_usage(info, usage)  # $2.0
        assert mgr.total_cost == pytest.approx(4.0)

    def test_cost_by_provider_tracks_separately(self) -> None:
        mgr = ProviderManager()
        info_a = _make_model_info(provider_id="alpha", input_cost=1.0, output_cost=1.0)
        info_b = _make_model_info(provider_id="beta", input_cost=2.0, output_cost=2.0)
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)

        mgr.record_usage(info_a, usage)  # alpha: $2
        mgr.record_usage(info_b, usage)  # beta: $4
        mgr.record_usage(info_a, usage)  # alpha: $2 more

        assert mgr.cost_by_provider["alpha"] == pytest.approx(4.0)
        assert mgr.cost_by_provider["beta"] == pytest.approx(4.0)
        assert mgr.total_cost == pytest.approx(8.0)

    def test_cost_by_provider_returns_copy(self) -> None:
        mgr = ProviderManager()
        info = _make_model_info()
        usage = TokenUsage(input_tokens=1_000, output_tokens=1_000)
        mgr.record_usage(info, usage)

        costs = mgr.cost_by_provider
        costs["test"] = 999.0
        assert mgr.cost_by_provider["test"] != 999.0

    def test_record_usage_zero_cost_for_local(self) -> None:
        mgr = ProviderManager()
        info = _make_model_info(input_cost=0.0, output_cost=0.0)
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=500_000)

        call_cost = mgr.record_usage(info, usage)
        assert call_cost == 0.0
        assert mgr.total_cost == 0.0

    def test_hard_limit_raises_when_exceeded(self) -> None:
        mgr = ProviderManager(cost_hard_limit=5.0)
        info = _make_model_info(input_cost=3.0, output_cost=15.0)
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)

        # First call: $4.5 — within limit
        mgr.record_usage(info, usage)
        assert mgr.total_cost == pytest.approx(4.5)

        # Second call: $4.5 more = $9.0 total — over $5 limit
        with pytest.raises(CostLimitExceededError, match=r"5\.00") as exc_info:
            mgr.record_usage(info, usage)

        assert exc_info.value.limit == 5.0
        assert exc_info.value.current == pytest.approx(9.0)

    def test_no_hard_limit_when_zero(self) -> None:
        mgr = ProviderManager(cost_hard_limit=0.0)
        info = _make_model_info(input_cost=100.0, output_cost=100.0)
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)

        # Should not raise even with huge cost
        mgr.record_usage(info, usage)
        assert mgr.total_cost == pytest.approx(200.0)

    def test_reset_cost_clears_all(self) -> None:
        mgr = ProviderManager()
        info = _make_model_info()
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
        mgr.record_usage(info, usage)
        assert mgr.total_cost > 0

        mgr.reset_cost()
        assert mgr.total_cost == 0.0
        assert mgr.cost_by_provider == {}

    def test_reset_cost_allows_spending_again(self) -> None:
        mgr = ProviderManager(cost_hard_limit=5.0)
        info = _make_model_info(input_cost=3.0, output_cost=15.0)
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)

        mgr.record_usage(info, usage)  # $4.5
        mgr.reset_cost()

        # After reset, same call should succeed (under limit again)
        call_cost = mgr.record_usage(info, usage)
        assert call_cost == pytest.approx(4.5)
        assert mgr.total_cost == pytest.approx(4.5)


# ── Integration: Register + Route + Cost ─────────────────────────


class TestEndToEnd:
    async def test_register_route_and_track_cost(self) -> None:
        mgr = ProviderManager(cost_hard_limit=1.0)
        provider = _make_provider("alpha")
        await mgr.register(provider)

        # Route to provider
        p, model_id = mgr.get_provider("alpha:model-a")
        assert p is provider
        assert model_id == "model-a"

        # Get model info for cost tracking
        info = mgr.get_model_info("alpha:model-a")
        assert info.provider_id == "alpha"

        # Mock provider has 0.0 pricing, so no cost limit hit
        usage = TokenUsage(input_tokens=1000, output_tokens=500)
        cost = mgr.record_usage(info, usage)
        assert cost == 0.0
