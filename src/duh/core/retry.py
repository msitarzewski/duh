"""Retry with exponential backoff for provider calls."""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

from duh.core.errors import (
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

T = TypeVar("T")

_RETRYABLE_TYPES: tuple[type[Exception], ...] = (
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderOverloadedError,
)


@dataclass(frozen=True, slots=True)
class RetryConfig:
    """Configuration for retry with backoff."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: bool = True


def is_retryable(error: Exception) -> bool:
    """Check if an error should trigger a retry."""
    return isinstance(error, _RETRYABLE_TYPES)


def _compute_delay(
    attempt: int,
    config: RetryConfig,
    error: Exception,
) -> float:
    """Compute backoff delay for a retry attempt."""
    # Use retry_after from rate limit errors if available
    if isinstance(error, ProviderRateLimitError) and error.retry_after is not None:
        return min(error.retry_after, config.max_delay)

    # Exponential backoff: base_delay * 2^attempt
    delay: float = config.base_delay * (2**attempt)
    delay = min(delay, config.max_delay)

    # Add jitter (±50% of delay)
    if config.jitter:
        delay *= random.uniform(0.5, 1.5)

    return delay


async def retry_with_backoff(
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
    on_retry: Callable[[int, float, Exception], None] | None = None,
) -> T:
    """Execute fn with retry and exponential backoff.

    Retries on ProviderRateLimitError, ProviderTimeoutError,
    and ProviderOverloadedError. All other errors propagate immediately.

    Args:
        fn: Zero-arg callable returning an awaitable.
        config: Retry configuration. Uses defaults if None.
        on_retry: Optional callback(attempt, delay, error) before each retry.

    Returns:
        The result of fn().

    Raises:
        The original error after retries exhausted, or immediately
        for non-retryable errors.
    """
    cfg = config or RetryConfig()

    for attempt in range(cfg.max_retries + 1):
        try:
            return await fn()
        except Exception as e:
            if not is_retryable(e):
                raise
            if attempt >= cfg.max_retries:
                raise
            delay = _compute_delay(attempt, cfg, e)
            if on_retry is not None:
                on_retry(attempt + 1, delay, e)
            await asyncio.sleep(delay)

    # Unreachable, but satisfies mypy
    msg = f"Retry loop exited unexpectedly (max_retries={cfg.max_retries})"
    raise RuntimeError(msg)
