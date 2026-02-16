# Errors

duh uses a structured error hierarchy rooted at `DuhError`. All duh-specific exceptions inherit from this base class.

## Error hierarchy

```
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
```

## Provider errors

All provider errors include a `provider_id` attribute identifying which provider raised the error.

### `ProviderAuthError`

**When**: Invalid or missing API key.

**Common causes**:

- API key not set in environment
- API key expired or revoked
- Wrong key for the provider

**Fix**: Check your API key. Run `duh models` to verify provider connectivity.

### `ProviderRateLimitError`

**When**: API rate limit exceeded.

**Attributes**: `retry_after` (float or None) -- seconds to wait before retrying.

**Common causes**:

- Too many requests in a short period
- Account-level rate limits

**Fix**: Wait and retry. duh's built-in retry logic handles transient rate limits automatically.

### `ProviderTimeoutError`

**When**: Model call timed out.

**Common causes**:

- Network connectivity issues
- Provider experiencing high latency
- Very long generation requests

**Fix**: Retry the request. If persistent, check your network connection.

### `ProviderOverloadedError`

**When**: Provider returned a 503 or 529 status.

**Common causes**:

- Provider infrastructure under heavy load
- Temporary capacity issues

**Fix**: Wait and retry. This is usually transient.

### `ModelNotFoundError`

**When**: Requested model is not available from this provider.

**Common causes**:

- Model ID typo
- Model deprecated or not yet available
- Account doesn't have access to the model

**Fix**: Run `duh models` to see available models.

## Consensus errors

### `InsufficientModelsError`

**When**: Not enough models available for meaningful consensus.

**Common causes**:

- No providers configured
- All providers failed health checks
- All API keys missing or invalid

**Fix**: Configure at least one provider with valid API keys. See [Installation](../getting-started/installation.md).

### `CostLimitExceededError`

**When**: Cumulative cost exceeds the hard limit.

**Attributes**: `limit` (float), `current` (float) -- the configured limit and current total cost.

**Common causes**:

- Many consensus queries in a session
- High-cost models with long responses
- Hard limit set too low

**Fix**: Increase `cost.hard_limit` in config, or set to `0` to disable.

```
Cost limit $10.00 exceeded (current: $10.23)
```

## Configuration errors

### `ConfigError`

**When**: Invalid configuration.

**Common causes**:

- Invalid TOML syntax in config file
- `DUH_CONFIG` points to a non-existent file
- Config file path passed to `--config` doesn't exist
- Pydantic validation failure (wrong types, invalid values)

**Fix**: Check your config file syntax and values. See [Config Reference](config-reference.md).

## Storage errors

### `StorageError`

**When**: Database or memory layer error.

**Common causes**:

- Database file locked by another process
- Database file corrupted
- Thread not found (for delete operations)

**Fix**: Check that no other duh process is running. If the database is corrupted, you can delete it and start fresh (data will be lost).

## Catching errors in code

```python
from duh.core.errors import (
    DuhError,
    ProviderError,
    ProviderRateLimitError,
    CostLimitExceededError,
    ConfigError,
)

try:
    result = await run_consensus(...)
except CostLimitExceededError as e:
    print(f"Budget exceeded: ${e.current:.2f} > ${e.limit:.2f}")
except ProviderRateLimitError as e:
    print(f"Rate limited by {e.provider_id}")
    if e.retry_after:
        print(f"Retry after {e.retry_after}s")
except ProviderError as e:
    print(f"Provider {e.provider_id} failed: {e}")
except DuhError as e:
    print(f"duh error: {e}")
```
