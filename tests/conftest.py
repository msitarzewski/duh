"""Shared test fixtures for duh."""

from __future__ import annotations

import os
import socket
import sys
import tempfile
from pathlib import Path
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


@pytest.fixture(autouse=True)
def isolated_runtime(monkeypatch, tmp_path):
    """Never discover developer secrets or contact external services in tests."""
    from duh.config import loader

    for key in _service_environment_keys():
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("DUH_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(loader, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def connect(sock, address):
        if sock.family != socket.AF_UNIX:
            pytest.fail("Network connections are disabled in the test suite")
        return original_connect(sock, address)

    def connect_ex(sock, address):
        if sock.family != socket.AF_UNIX:
            pytest.fail("Network connections are disabled in the test suite")
        return original_connect_ex(sock, address)

    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket.socket, "connect_ex", connect_ex)


@pytest.fixture(autouse=True)
async def dispose_created_engines(monkeypatch, request):
    """Own real test engines until they are closed, rather than relying on GC."""
    import sqlalchemy.ext.asyncio as sqlalchemy_async

    engines = []

    def tracked_engine(*args, **kwargs):
        engine = create_async_engine(*args, **kwargs)
        engines.append(engine)
        return engine

    modules = [request.module, sqlalchemy_async]
    modules.extend(
        module
        for name in ("duh.api.app", "duh.cli.app")
        if (module := sys.modules.get(name)) is not None
    )
    for module in modules:
        if getattr(module, "create_async_engine", None) is create_async_engine:
            monkeypatch.setattr(module, "create_async_engine", tracked_engine)
    try:
        yield
    finally:
        while engines:
            await engines.pop().dispose()


_SESSION_PATCH = pytest.MonkeyPatch()
_SESSION_CONFIG_HOME = None


def _service_environment_keys():
    prefixes = (
        "DUH_",
        "OPENAI_",
        "ANTHROPIC_",
        "GOOGLE_",
        "MISTRAL_",
        "PERPLEXITY_",
        "CLOUDFLARE_",
        "STRIPE_",
        "SENTRY_",
        "AWS_",
        "AZURE_",
    )
    return tuple(
        key
        for key in os.environ
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET"))
        or key.startswith(prefixes)
        or key in {"DATABASE_URL", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"}
    )


def _unix_only(method):
    def guarded(sock, *args, **kwargs):
        if sock.family != socket.AF_UNIX:
            pytest.fail("Network connections are disabled throughout the test session")
        return method(sock, *args, **kwargs)

    return guarded


def _blocked_dns(*args, **kwargs):
    pytest.fail("DNS resolution is disabled throughout the test session")


def pytest_sessionstart(session):
    """Isolate collection and higher-scoped fixtures before importing test modules."""
    from duh.config import loader

    global _SESSION_CONFIG_HOME
    blocked_paths = {
        loader._user_config_path().resolve(),
        loader._project_config_path().resolve(),
    }
    override = os.environ.get("DUH_CONFIG")
    if override:
        blocked_paths.add(Path(override).resolve())
    for key in _service_environment_keys():
        os.environ.pop(key, None)
    _SESSION_CONFIG_HOME = tempfile.TemporaryDirectory(prefix="duh-test-config-")
    _SESSION_PATCH.setenv("HOME", _SESSION_CONFIG_HOME.name)
    _SESSION_PATCH.setenv("PYTHON_DOTENV_DISABLED", "1")
    _SESSION_PATCH.setenv("XDG_CONFIG_HOME", _SESSION_CONFIG_HOME.name)
    _SESSION_PATCH.setenv("DUH_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    _SESSION_PATCH.setattr(loader, "load_dotenv", lambda *args, **kwargs: False)
    _SESSION_PATCH.setattr("dotenv.load_dotenv", lambda *args, **kwargs: False)
    discover = loader._discover_config_files

    def isolated_discovery():
        return [path for path in discover() if path.resolve() not in blocked_paths]

    _SESSION_PATCH.setattr(loader, "_discover_config_files", isolated_discovery)
    for name in ("connect", "connect_ex", "send", "sendall", "sendto", "sendmsg"):
        if hasattr(socket.socket, name):
            _SESSION_PATCH.setattr(
                socket.socket, name, _unix_only(getattr(socket.socket, name))
            )
    for name in (
        "getaddrinfo",
        "gethostbyname",
        "gethostbyname_ex",
        "gethostbyaddr",
        "getnameinfo",
    ):
        _SESSION_PATCH.setattr(socket, name, _blocked_dns)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    _SESSION_PATCH.undo()
    if _SESSION_CONFIG_HOME is not None:
        _SESSION_CONFIG_HOME.cleanup()
