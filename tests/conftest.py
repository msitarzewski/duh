"""Shared test fixtures for duh."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.memory.models import Base
from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    TokenUsage,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.fixtures.providers import MockProvider as MockProviderType


@pytest.fixture
async def db_session() -> AsyncSession:  # type: ignore[misc]
    """In-memory SQLite async session with FK enforcement."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def make_model_info() -> Any:
    """Factory fixture for ModelInfo with sensible defaults."""

    def _make(**overrides: Any) -> ModelInfo:
        defaults: dict[str, Any] = {
            "provider_id": "test",
            "model_id": "test-model",
            "display_name": "Test Model",
            "capabilities": ModelCapability.TEXT | ModelCapability.STREAMING,
            "context_window": 128_000,
            "max_output_tokens": 4096,
            "input_cost_per_mtok": 3.0,
            "output_cost_per_mtok": 15.0,
        }
        defaults.update(overrides)
        return ModelInfo(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def make_usage() -> Any:
    """Factory fixture for TokenUsage with sensible defaults."""

    def _make(**overrides: Any) -> TokenUsage:
        defaults: dict[str, Any] = {"input_tokens": 100, "output_tokens": 50}
        defaults.update(overrides)
        return TokenUsage(**defaults)  # type: ignore[arg-type]

    return _make


@pytest.fixture
def mock_provider() -> MockProviderType:
    """Provider with canned responses for deterministic consensus tests."""
    from tests.fixtures.providers import MockProvider
    from tests.fixtures.responses import CONSENSUS_BASIC

    return MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)


@pytest.fixture
def mock_provider_minimal() -> MockProviderType:
    """Minimal mock provider with two simple models."""
    from tests.fixtures.providers import MockProvider
    from tests.fixtures.responses import MINIMAL

    return MockProvider(provider_id="mock-minimal", responses=MINIMAL)
