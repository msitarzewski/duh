"""Tests for retry with backoff utility."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from duh.core.errors import (
    ModelNotFoundError,
    ProviderAuthError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
)
from duh.core.retry import (
    RetryConfig,
    _compute_delay,
    is_retryable,
    retry_with_backoff,
)

# ─── RetryConfig ──────────────────────────────────────────────


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_retries == 3
        assert cfg.base_delay == 1.0
        assert cfg.max_delay == 60.0
        assert cfg.jitter is True

    def test_custom_values(self):
        cfg = RetryConfig(max_retries=5, base_delay=0.5, max_delay=30.0, jitter=False)
        assert cfg.max_retries == 5
        assert cfg.base_delay == 0.5
        assert cfg.max_delay == 30.0
        assert cfg.jitter is False

    def test_frozen(self):
        cfg = RetryConfig()
        with pytest.raises(AttributeError):
            cfg.max_retries = 5  # type: ignore[misc]


# ─── is_retryable ─────────────────────────────────────────────


class TestIsRetryable:
    def test_rate_limit_is_retryable(self):
        assert is_retryable(ProviderRateLimitError("test")) is True

    def test_timeout_is_retryable(self):
        assert is_retryable(ProviderTimeoutError("test", "timeout")) is True

    def test_overloaded_is_retryable(self):
        err = ProviderOverloadedError("test", "overloaded")
        assert is_retryable(err) is True

    def test_auth_is_not_retryable(self):
        assert is_retryable(ProviderAuthError("test", "bad key")) is False

    def test_model_not_found_is_not_retryable(self):
        assert is_retryable(ModelNotFoundError("test", "nope")) is False

    def test_generic_exception_is_not_retryable(self):
        assert is_retryable(ValueError("oops")) is False


# ─── _compute_delay ───────────────────────────────────────────


class TestComputeDelay:
    def test_exponential_backoff(self):
        cfg = RetryConfig(base_delay=1.0, jitter=False)
        err = ProviderTimeoutError("test", "timeout")
        assert _compute_delay(0, cfg, err) == 1.0
        assert _compute_delay(1, cfg, err) == 2.0
        assert _compute_delay(2, cfg, err) == 4.0
        assert _compute_delay(3, cfg, err) == 8.0

    def test_respects_max_delay(self):
        cfg = RetryConfig(base_delay=10.0, max_delay=15.0, jitter=False)
        err = ProviderTimeoutError("test", "timeout")
        assert _compute_delay(0, cfg, err) == 10.0
        assert _compute_delay(1, cfg, err) == 15.0  # capped
        assert _compute_delay(2, cfg, err) == 15.0  # capped

    def test_uses_retry_after_from_rate_limit(self):
        cfg = RetryConfig(base_delay=1.0, jitter=False)
        err = ProviderRateLimitError("test", retry_after=30.0)
        assert _compute_delay(0, cfg, err) == 30.0
        # retry_after overrides exponential regardless of attempt
        assert _compute_delay(5, cfg, err) == 30.0

    def test_retry_after_capped_by_max_delay(self):
        cfg = RetryConfig(max_delay=10.0, jitter=False)
        err = ProviderRateLimitError("test", retry_after=30.0)
        assert _compute_delay(0, cfg, err) == 10.0

    def test_rate_limit_without_retry_after_uses_backoff(self):
        cfg = RetryConfig(base_delay=2.0, jitter=False)
        err = ProviderRateLimitError("test")  # no retry_after
        assert _compute_delay(0, cfg, err) == 2.0
        assert _compute_delay(1, cfg, err) == 4.0

    def test_jitter_adds_variance(self):
        cfg = RetryConfig(base_delay=10.0, jitter=True)
        err = ProviderTimeoutError("test", "timeout")
        with patch("duh.core.retry.random.uniform", return_value=0.8):
            delay = _compute_delay(0, cfg, err)
        assert delay == pytest.approx(8.0)

    def test_no_jitter_when_disabled(self):
        cfg = RetryConfig(base_delay=10.0, jitter=False)
        err = ProviderTimeoutError("test", "timeout")
        assert _compute_delay(0, cfg, err) == 10.0


# ─── retry_with_backoff ───────────────────────────────────────


class TestRetryWithBackoff:
    async def test_succeeds_on_first_try(self):
        fn = AsyncMock(return_value="ok")
        result = await retry_with_backoff(fn)
        assert result == "ok"
        assert fn.call_count == 1

    async def test_retries_on_rate_limit(self):
        fn = AsyncMock(
            side_effect=[ProviderRateLimitError("test"), "ok"],
        )
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(fn)
        assert result == "ok"
        assert fn.call_count == 2

    async def test_retries_on_timeout(self):
        fn = AsyncMock(
            side_effect=[ProviderTimeoutError("test", "t"), "ok"],
        )
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(fn)
        assert result == "ok"
        assert fn.call_count == 2

    async def test_retries_on_overloaded(self):
        fn = AsyncMock(
            side_effect=[ProviderOverloadedError("test", "busy"), "ok"],
        )
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(fn)
        assert result == "ok"
        assert fn.call_count == 2

    async def test_fails_fast_on_auth_error(self):
        fn = AsyncMock(side_effect=ProviderAuthError("test", "bad key"))
        with pytest.raises(ProviderAuthError):
            await retry_with_backoff(fn)
        assert fn.call_count == 1

    async def test_fails_fast_on_model_not_found(self):
        fn = AsyncMock(side_effect=ModelNotFoundError("test", "nope"))
        with pytest.raises(ModelNotFoundError):
            await retry_with_backoff(fn)
        assert fn.call_count == 1

    async def test_fails_fast_on_generic_exception(self):
        fn = AsyncMock(side_effect=ValueError("bad"))
        with pytest.raises(ValueError, match="bad"):
            await retry_with_backoff(fn)
        assert fn.call_count == 1

    async def test_exhausts_retries_then_raises(self):
        cfg = RetryConfig(max_retries=2, jitter=False)
        fn = AsyncMock(side_effect=ProviderRateLimitError("test"))
        with (
            patch.object(asyncio, "sleep", new_callable=AsyncMock),
            pytest.raises(ProviderRateLimitError),
        ):
            await retry_with_backoff(fn, config=cfg)
        # 1 initial + 2 retries = 3 total attempts
        assert fn.call_count == 3

    async def test_on_retry_callback_called(self):
        cfg = RetryConfig(max_retries=2, jitter=False)
        fn = AsyncMock(
            side_effect=[
                ProviderRateLimitError("test"),
                ProviderTimeoutError("test", "t"),
                "ok",
            ],
        )
        callback = MagicMock()
        with patch.object(asyncio, "sleep", new_callable=AsyncMock):
            result = await retry_with_backoff(fn, config=cfg, on_retry=callback)
        assert result == "ok"
        assert callback.call_count == 2
        # First retry: attempt=1, rate limit error
        assert callback.call_args_list[0][0][0] == 1
        assert isinstance(callback.call_args_list[0][0][2], ProviderRateLimitError)
        # Second retry: attempt=2, timeout error
        assert callback.call_args_list[1][0][0] == 2
        assert isinstance(callback.call_args_list[1][0][2], ProviderTimeoutError)

    async def test_respects_retry_after_delay(self):
        cfg = RetryConfig(max_retries=1, jitter=False)
        fn = AsyncMock(
            side_effect=[
                ProviderRateLimitError("test", retry_after=42.0),
                "ok",
            ],
        )
        with patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            result = await retry_with_backoff(fn, config=cfg)
        assert result == "ok"
        mock_sleep.assert_called_once_with(42.0)

    async def test_exponential_delays(self):
        cfg = RetryConfig(max_retries=3, base_delay=1.0, jitter=False)
        fn = AsyncMock(
            side_effect=[
                ProviderTimeoutError("test", "t"),
                ProviderTimeoutError("test", "t"),
                ProviderTimeoutError("test", "t"),
                "ok",
            ],
        )
        with patch.object(asyncio, "sleep", new_callable=AsyncMock) as mock_sleep:
            result = await retry_with_backoff(fn, config=cfg)
        assert result == "ok"
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays == [1.0, 2.0, 4.0]

    async def test_default_config_used(self):
        fn = AsyncMock(return_value="ok")
        result = await retry_with_backoff(fn)
        assert result == "ok"

    async def test_zero_retries_tries_once(self):
        cfg = RetryConfig(max_retries=0)
        fn = AsyncMock(side_effect=ProviderRateLimitError("test"))
        with pytest.raises(ProviderRateLimitError):
            await retry_with_backoff(fn, config=cfg)
        assert fn.call_count == 1
