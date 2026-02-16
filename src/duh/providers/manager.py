"""Provider manager: registration, model discovery, cost tracking, routing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from duh.core.errors import CostLimitExceededError, ModelNotFoundError

if TYPE_CHECKING:
    from duh.providers.base import ModelInfo, ModelProvider, TokenUsage


class ProviderManager:
    """Central registry for provider adapters.

    Handles multi-provider registration, model discovery across all
    providers, routing by ``model_ref`` (``provider_id:model_id``),
    and cumulative cost tracking with hard-limit enforcement.
    """

    def __init__(self, *, cost_hard_limit: float = 0.0) -> None:
        """Create a new provider manager.

        Args:
            cost_hard_limit: Maximum cumulative cost in USD. 0 = no limit.
        """
        self._providers: dict[str, ModelProvider] = {}
        self._model_index: dict[str, ModelInfo] = {}  # model_ref -> ModelInfo
        self._cost_hard_limit = cost_hard_limit
        self._total_cost: float = 0.0
        self._cost_by_provider: dict[str, float] = {}

    # ── Registration ─────────────────────────────────────────────

    async def register(self, provider: ModelProvider) -> None:
        """Register a provider and index its models.

        Raises:
            ValueError: If a provider with the same provider_id is
                already registered.
        """
        pid = provider.provider_id
        if pid in self._providers:
            msg = f"Provider already registered: {pid}"
            raise ValueError(msg)

        self._providers[pid] = provider
        models = await provider.list_models()
        for model in models:
            self._model_index[model.model_ref] = model

    def unregister(self, provider_id: str) -> None:
        """Remove a provider and its models from the registry.

        Raises:
            KeyError: If the provider_id is not registered.
        """
        if provider_id not in self._providers:
            msg = f"Provider not registered: {provider_id}"
            raise KeyError(msg)

        del self._providers[provider_id]
        # Remove all models belonging to this provider
        self._model_index = {
            ref: info
            for ref, info in self._model_index.items()
            if info.provider_id != provider_id
        }

    # ── Discovery ────────────────────────────────────────────────

    def list_all_models(self) -> list[ModelInfo]:
        """Return metadata for all models across all registered providers."""
        return list(self._model_index.values())

    def get_model_info(self, model_ref: str) -> ModelInfo:
        """Look up model metadata by ``provider_id:model_id``.

        Raises:
            ModelNotFoundError: If the model_ref is not in the index.
        """
        info = self._model_index.get(model_ref)
        if info is None:
            provider_id, _, model_id = model_ref.partition(":")
            pid = provider_id or "unknown"
            mid = model_id or model_ref
            raise ModelNotFoundError(pid, f"Model not found: {mid}")
        return info

    # ── Routing ──────────────────────────────────────────────────

    def get_provider(self, model_ref: str) -> tuple[ModelProvider, str]:
        """Resolve a model_ref to its provider and model_id.

        Returns:
            (provider, model_id) tuple for direct send/stream calls.

        Raises:
            ModelNotFoundError: If the model_ref is not in the index.
        """
        info = self.get_model_info(model_ref)
        provider = self._providers[info.provider_id]
        return provider, info.model_id

    # ── Cost tracking ────────────────────────────────────────────

    @property
    def total_cost(self) -> float:
        """Cumulative cost in USD across all providers."""
        return self._total_cost

    @property
    def cost_by_provider(self) -> dict[str, float]:
        """Cost breakdown by provider_id."""
        return dict(self._cost_by_provider)

    def record_usage(self, model_info: ModelInfo, usage: TokenUsage) -> float:
        """Record token usage and accumulate cost.

        Args:
            model_info: Model metadata (contains pricing).
            usage: Token counts from the call.

        Returns:
            The cost of this individual call in USD.

        Raises:
            CostLimitExceededError: If the cumulative cost exceeds
                the hard limit (when limit > 0).
        """
        input_cost = (usage.input_tokens / 1_000_000) * model_info.input_cost_per_mtok
        output_cost = (
            usage.output_tokens / 1_000_000
        ) * model_info.output_cost_per_mtok
        call_cost = input_cost + output_cost

        self._total_cost += call_cost
        pid = model_info.provider_id
        self._cost_by_provider[pid] = self._cost_by_provider.get(pid, 0.0) + call_cost

        if self._cost_hard_limit > 0 and self._total_cost > self._cost_hard_limit:
            raise CostLimitExceededError(
                limit=self._cost_hard_limit,
                current=self._total_cost,
            )

        return call_cost

    def reset_cost(self) -> None:
        """Reset the cost accumulator to zero."""
        self._total_cost = 0.0
        self._cost_by_provider.clear()
