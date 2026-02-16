"""Exception hierarchy for duh.

Every module imports from here. The hierarchy is:

    DuhError
    ├── ProviderError(provider_id)
    │   ├── ProviderAuthError
    │   ├── ProviderRateLimitError(retry_after)
    │   ├── ProviderTimeoutError
    │   ├── ProviderOverloadedError
    │   └── ModelNotFoundError
    ├── ConsensusError
    │   ├── InsufficientModelsError
    │   └── CostLimitExceededError(limit, current)
    ├── ConfigError
    └── StorageError
"""

from __future__ import annotations


class DuhError(Exception):
    """Base exception for all duh errors."""


# ─── Provider Errors ──────────────────────────────────────────


class ProviderError(DuhError):
    """Base for provider-related errors."""

    def __init__(self, provider_id: str, message: str) -> None:
        self.provider_id = provider_id
        super().__init__(f"[{provider_id}] {message}")


class ProviderAuthError(ProviderError):
    """Invalid or missing API key."""


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded. Includes retry_after if available."""

    def __init__(self, provider_id: str, retry_after: float | None = None) -> None:
        self.retry_after = retry_after
        msg = "Rate limited"
        if retry_after is not None:
            msg += f" (retry after {retry_after}s)"
        super().__init__(provider_id, msg)


class ProviderTimeoutError(ProviderError):
    """Model call timed out."""


class ProviderOverloadedError(ProviderError):
    """Provider is overloaded (529, 503)."""


class ModelNotFoundError(ProviderError):
    """Requested model not available from this provider."""


# ─── Consensus Errors ─────────────────────────────────────────


class ConsensusError(DuhError):
    """Base for consensus protocol errors."""


class InsufficientModelsError(ConsensusError):
    """Not enough models available for meaningful consensus."""


class CostLimitExceededError(ConsensusError):
    """Hard cost limit reached."""

    def __init__(self, limit: float, current: float) -> None:
        self.limit = limit
        self.current = current
        super().__init__(f"Cost limit ${limit:.2f} exceeded (current: ${current:.2f})")


# ─── Configuration Errors ─────────────────────────────────────


class ConfigError(DuhError):
    """Invalid configuration."""


# ─── Storage Errors ───────────────────────────────────────────


class StorageError(DuhError):
    """Database or memory layer error."""
