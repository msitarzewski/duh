"""Tests for the core error hierarchy."""

from duh.core.errors import (
    ConfigError,
    ConsensusError,
    CostLimitExceededError,
    DuhError,
    InsufficientModelsError,
    ModelNotFoundError,
    ProviderAuthError,
    ProviderError,
    ProviderOverloadedError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    StorageError,
)


class TestHierarchy:
    """All errors inherit from DuhError."""

    def test_provider_error_is_duh_error(self):
        err = ProviderError("anthropic", "something broke")
        assert isinstance(err, DuhError)

    def test_provider_subclasses_are_provider_error(self):
        subclasses = [
            ProviderAuthError("openai", "bad key"),
            ProviderRateLimitError("anthropic"),
            ProviderTimeoutError("ollama", "timed out"),
            ProviderOverloadedError("openai", "overloaded"),
            ModelNotFoundError("anthropic", "no such model"),
        ]
        for err in subclasses:
            assert isinstance(err, ProviderError)
            assert isinstance(err, DuhError)

    def test_consensus_error_is_duh_error(self):
        err = ConsensusError("failed")
        assert isinstance(err, DuhError)

    def test_consensus_subclasses(self):
        assert isinstance(InsufficientModelsError("need 2"), ConsensusError)
        assert isinstance(CostLimitExceededError(1.0, 1.5), ConsensusError)

    def test_config_error_is_duh_error(self):
        assert isinstance(ConfigError("bad config"), DuhError)

    def test_storage_error_is_duh_error(self):
        assert isinstance(StorageError("db down"), DuhError)

    def test_no_shadow_builtin_memory_error(self):
        """StorageError does not shadow Python's built-in MemoryError."""
        assert not isinstance(StorageError("db"), MemoryError)


class TestProviderError:
    """ProviderError carries provider_id and formats messages."""

    def test_provider_id_attribute(self):
        err = ProviderError("anthropic", "connection failed")
        assert err.provider_id == "anthropic"

    def test_message_format(self):
        err = ProviderError("openai", "timeout")
        assert str(err) == "[openai] timeout"

    def test_subclass_inherits_provider_id(self):
        err = ProviderAuthError("anthropic", "invalid key")
        assert err.provider_id == "anthropic"
        assert "[anthropic]" in str(err)


class TestProviderRateLimitError:
    """Rate limit error with optional retry_after."""

    def test_without_retry_after(self):
        err = ProviderRateLimitError("openai")
        assert err.provider_id == "openai"
        assert err.retry_after is None
        assert "Rate limited" in str(err)
        assert "retry after" not in str(err)

    def test_with_retry_after(self):
        err = ProviderRateLimitError("anthropic", retry_after=30.0)
        assert err.retry_after == 30.0
        assert "retry after 30.0s" in str(err)

    def test_retry_after_zero(self):
        err = ProviderRateLimitError("anthropic", retry_after=0.0)
        assert err.retry_after == 0.0


class TestCostLimitExceededError:
    """Cost limit error with limit and current amounts."""

    def test_attributes(self):
        err = CostLimitExceededError(limit=5.00, current=5.50)
        assert err.limit == 5.00
        assert err.current == 5.50

    def test_message_format(self):
        err = CostLimitExceededError(limit=10.00, current=12.34)
        assert "$10.00" in str(err)
        assert "$12.34" in str(err)

    def test_is_consensus_error(self):
        err = CostLimitExceededError(1.0, 2.0)
        assert isinstance(err, ConsensusError)
        assert isinstance(err, DuhError)


class TestCatchBroad:
    """Catching DuhError catches everything in the hierarchy."""

    def test_catch_all_duh_errors(self):
        errors = [
            ProviderError("x", "y"),
            ProviderAuthError("x", "y"),
            ProviderRateLimitError("x"),
            ProviderTimeoutError("x", "y"),
            ProviderOverloadedError("x", "y"),
            ModelNotFoundError("x", "y"),
            ConsensusError("y"),
            InsufficientModelsError("y"),
            CostLimitExceededError(1.0, 2.0),
            ConfigError("y"),
            StorageError("y"),
        ]
        for err in errors:
            try:
                raise err
            except DuhError:
                pass  # All caught
