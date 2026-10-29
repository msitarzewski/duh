"""Provider manager: registration, model discovery, cost tracking, routing."""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from duh.core.errors import CostLimitExceededError, ModelNotFoundError, ProviderError

if TYPE_CHECKING:
    from collections.abc import Iterator

    from duh.providers.base import ModelInfo, ModelProvider, TokenUsage


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    """Immutable totals for one execution, independent of global telemetry."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


@dataclass(slots=True)
class UsageLedger:
    """A run's mutable ledger, inherited by its asynchronous child tasks."""

    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cost_by_provider: dict[str, float] = field(default_factory=dict)
    parent: UsageLedger | None = field(default=None, repr=False)

    def snapshot(self) -> UsageSnapshot:
        return UsageSnapshot(self.input_tokens, self.output_tokens, self.cost_usd)


class ProviderQuotaExceededError(ProviderError):
    """Raised when a provider's configured rate limit is exceeded.

    Distinct from ``ProviderRateLimitError`` in ``core.errors`` which
    represents rate limits returned by the external provider API.
    This error represents *our* configured per-provider quota.
    """

    def __init__(self, provider_id: str, rate_limit: int) -> None:
        super().__init__(
            provider_id,
            f"Provider quota exceeded: {rate_limit} requests per minute",
        )
        self.rate_limit = rate_limit


class ProviderManager:
    """Central registry for provider adapters.

    Handles multi-provider registration, model discovery across all
    providers, routing by ``model_ref`` (``provider_id:model_id``),
    and cumulative cost tracking with hard-limit enforcement.
    """

    def __init__(self, *, cost_hard_limit: float = 0.0) -> None:
        """Create a new provider manager.

        Args:
            cost_hard_limit: Maximum run cost in USD. Unscoped callers retain
                cumulative enforcement for compatibility. 0 = no limit.
        """
        self._providers: dict[str, ModelProvider] = {}
        self._model_index: dict[str, ModelInfo] = {}  # model_ref -> ModelInfo
        self._cost_hard_limit = cost_hard_limit
        self._total_cost: float = 0.0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._cost_by_provider: dict[str, float] = {}
        self._provider_rate_limits: dict[str, int] = {}  # provider_id -> rpm
        self._provider_requests: dict[str, list[float]] = {}  # pid -> ts
        self._run_usage: ContextVar[UsageLedger | None] = ContextVar(
            f"provider_manager_usage_{id(self)}", default=None
        )

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

        Also checks provider-level rate limits before returning.

        Returns:
            (provider, model_id) tuple for direct send/stream calls.

        Raises:
            ModelNotFoundError: If the model_ref is not in the index.
            ProviderQuotaExceededError: If the provider's rate limit is exceeded.
        """
        info = self.get_model_info(model_ref)
        self.check_provider_rate_limit(info.provider_id)
        provider = self._providers[info.provider_id]
        return provider, info.model_id

    # ── Cost tracking ────────────────────────────────────────────

    @contextmanager
    def usage_scope(self, *, child: bool = False) -> Iterator[UsageLedger]:
        """Isolate a run while retaining its budget across nested operations.

        Child tasks inherit the same ledger. Independent request tasks create
        different ledgers even when they share this provider manager. Nested
        engines/subtasks reuse the current ledger instead of resetting budget.
        ``child=True`` measures a subtask separately while also charging its
        parent ledger and enforcing the outermost run's hard limit.
        """
        existing = self._run_usage.get()
        if existing is not None and not child:
            yield existing
            return
        ledger = UsageLedger(parent=existing)
        token = self._run_usage.set(ledger)
        try:
            yield ledger
        finally:
            self._run_usage.reset(token)

    @property
    def aggregate_usage(self) -> UsageSnapshot:
        """All-time telemetry, which is never used as another run's budget."""
        return UsageSnapshot(
            self._total_input_tokens, self._total_output_tokens, self._total_cost
        )

    @property
    def total_cost(self) -> float:
        """Active scope cost, or cumulative telemetry outside an execution."""
        ledger = self._run_usage.get()
        return ledger.cost_usd if ledger is not None else self._total_cost

    @property
    def total_input_tokens(self) -> int:
        """Active scope input tokens, or cumulative telemetry when unscoped."""
        ledger = self._run_usage.get()
        return ledger.input_tokens if ledger is not None else self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        """Active scope output tokens, or cumulative telemetry when unscoped."""
        ledger = self._run_usage.get()
        return ledger.output_tokens if ledger is not None else self._total_output_tokens

    @property
    def cost_by_provider(self) -> dict[str, float]:
        """Active scope cost by provider, or cumulative telemetry when unscoped."""
        ledger = self._run_usage.get()
        return dict(
            ledger.cost_by_provider if ledger is not None else self._cost_by_provider
        )

    def record_usage(self, model_info: ModelInfo, usage: TokenUsage) -> float:
        """Record token usage and accumulate cost.

        Args:
            model_info: Model metadata (contains pricing).
            usage: Token counts from the call.

        Returns:
            The cost of this individual call in USD.

        Raises:
            CostLimitExceededError: If the outer run's cost exceeds its hard
                limit (or cumulative cost for legacy unscoped callers).
        """
        input_cost = (usage.input_tokens / 1_000_000) * model_info.input_cost_per_mtok
        output_cost = (
            usage.output_tokens / 1_000_000
        ) * model_info.output_cost_per_mtok
        call_cost = input_cost + output_cost

        self._total_cost += call_cost
        self._total_input_tokens += usage.input_tokens
        self._total_output_tokens += usage.output_tokens
        pid = model_info.provider_id
        self._cost_by_provider[pid] = self._cost_by_provider.get(pid, 0.0) + call_cost

        ledger = self._run_usage.get()
        budget_cost = self._total_cost
        while ledger is not None:
            ledger.cost_usd += call_cost
            ledger.input_tokens += usage.input_tokens
            ledger.output_tokens += usage.output_tokens
            ledger.cost_by_provider[pid] = (
                ledger.cost_by_provider.get(pid, 0.0) + call_cost
            )
            budget_cost = ledger.cost_usd
            ledger = ledger.parent

        if self._cost_hard_limit > 0 and budget_cost > self._cost_hard_limit:
            raise CostLimitExceededError(
                limit=self._cost_hard_limit,
                current=budget_cost,
            )

        return call_cost

    def reset_cost(self) -> None:
        """Reset the cost and token accumulators to zero."""
        if self._run_usage.get() is not None:
            raise RuntimeError("Cannot reset usage during an active run")
        self._total_cost = 0.0
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._cost_by_provider.clear()

    # ── Provider rate limiting ───────────────────────────────────

    def set_provider_rate_limit(self, provider_id: str, rpm: int) -> None:
        """Set a per-minute rate limit for a provider.

        Args:
            provider_id: The provider identifier.
            rpm: Requests per minute. 0 = unlimited.
        """
        self._provider_rate_limits[provider_id] = rpm
        if provider_id not in self._provider_requests:
            self._provider_requests[provider_id] = []

    def check_provider_rate_limit(self, provider_id: str) -> None:
        """Check if a provider's rate limit has been exceeded.

        Raises:
            ProviderQuotaExceededError: If the provider's rate limit is exceeded.
        """
        rpm = self._provider_rate_limits.get(provider_id, 0)
        if rpm <= 0:
            return  # unlimited

        now = time.monotonic()
        window = 60.0  # 1 minute

        # Clean old entries
        self._provider_requests.setdefault(provider_id, [])
        self._provider_requests[provider_id] = [
            t for t in self._provider_requests[provider_id] if now - t < window
        ]

        if len(self._provider_requests[provider_id]) >= rpm:
            raise ProviderQuotaExceededError(provider_id, rpm)

        # Record this request
        self._provider_requests[provider_id].append(now)

    def get_provider_rate_limit_remaining(self, provider_id: str) -> int | None:
        """Get remaining requests for a provider in the current window.

        Returns:
            Number of remaining requests, or None if no limit is set.
        """
        rpm = self._provider_rate_limits.get(provider_id, 0)
        if rpm <= 0:
            return None

        now = time.monotonic()
        window = 60.0
        self._provider_requests.setdefault(provider_id, [])
        current = [t for t in self._provider_requests[provider_id] if now - t < window]
        return max(0, rpm - len(current))
