# 150215_retry-backoff

## Objective
v0.1 Task 8: Create retry with exponential backoff utility.

## Outcome
- 201/201 unit tests passing (29 new + 172 existing)
- Linter: 0 errors, 0 warnings
- mypy strict: 0 issues (16 source files)
- Format: clean

## Files Created/Modified
- `src/duh/core/retry.py` — RetryConfig, is_retryable, _compute_delay, retry_with_backoff
- `tests/unit/test_retry.py` — 29 tests covering config, retryability, delays, full retry behavior
- `src/duh/core/__init__.py` — Added re-exports for RetryConfig, is_retryable, retry_with_backoff

## RetryConfig
- Frozen dataclass with slots: `max_retries=3`, `base_delay=1.0`, `max_delay=60.0`, `jitter=True`

## Retryable vs Non-Retryable
- **Retryable**: ProviderRateLimitError, ProviderTimeoutError, ProviderOverloadedError
- **Non-retryable (fail fast)**: ProviderAuthError, ModelNotFoundError, any non-ProviderError

## Delay Computation
- Exponential backoff: `base_delay * 2^attempt`
- Capped at `max_delay`
- `retry_after` from ProviderRateLimitError overrides exponential (also capped)
- Jitter: ±50% randomization via `random.uniform(0.5, 1.5)`, configurable

## retry_with_backoff API
```python
async def retry_with_backoff(
    fn: Callable[[], Awaitable[T]],
    config: RetryConfig | None = None,
    on_retry: Callable[[int, float, Exception], None] | None = None,
) -> T:
```
- `fn`: Zero-arg callable returning awaitable (e.g. `lambda: provider.send(...)`)
- `on_retry`: Optional callback(attempt, delay, error) for logging
- `max_retries=3` means 3 retries after initial attempt (4 total tries)

## Notes
- mypy strict required explicit `delay: float` annotation due to `float * int` inference issue
- `asyncio.sleep` patched via `patch.object(asyncio, "sleep", new_callable=AsyncMock)` in tests
- `random.uniform` patched via `patch("duh.core.retry.random.uniform", ...)` for deterministic jitter tests
