"""Tests for per-user + per-provider rate limiting (T6).

Verifies:
- Rate limiting by user_id (JWT auth)
- Rate limiting by api_key_id
- Rate limiting by IP fallback
- ProviderConfig accepts rate_limit field
- ProviderManager respects provider-level rate limits
- Response includes rate limit headers with identity info
"""

from __future__ import annotations

import hashlib
import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware
from duh.config.schema import ProviderConfig
from duh.memory.models import Base
from duh.memory.repository import MemoryRepository


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ── Test App Helpers ────────────────────────────────────────


async def _make_app(
    *,
    rate_limit: int = 100,
    window: int = 60,
    jwt_secret: str = "test-secret",
) -> FastAPI:
    """Create a minimal FastAPI app with middleware and in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="test")
    app.state.config = SimpleNamespace(
        api=SimpleNamespace(
            cors_origins=["http://localhost:3000"],
            rate_limit=rate_limit,
            rate_limit_window=window,
        ),
        auth=SimpleNamespace(jwt_secret=jwt_secret),
    )
    app.state.db_factory = factory
    app.state.engine = engine

    app.add_middleware(RateLimitMiddleware, rate_limit=rate_limit, window=window)
    app.add_middleware(APIKeyMiddleware)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/test")
    async def test_endpoint() -> dict[str, str]:
        return {"msg": "ok"}

    return app


async def _seed_key(app: FastAPI, name: str, raw_key: str) -> str:
    """Insert an API key into the test DB and return its ID."""
    async with app.state.db_factory() as session:
        repo = MemoryRepository(session)
        api_key = await repo.create_api_key(name, _hash(raw_key))
        await session.commit()
        return api_key.id


# ── Rate Limit by User ID ───────────────────────────────────


class TestRateLimitByUserId:
    @pytest.mark.asyncio
    async def test_rate_limit_by_user_id(self) -> None:
        """Requests with JWT token should be rate-limited by user_id."""
        from duh.api.auth import create_token

        app = await _make_app(rate_limit=3, window=60, jwt_secret="test-secret")
        client = TestClient(app, raise_server_exceptions=False)

        token = create_token("user-123", "test-secret")
        headers = {"Authorization": f"Bearer {token}"}

        # First 3 requests should succeed
        for _ in range(3):
            resp = client.get("/api/test", headers=headers)
            assert resp.status_code == 200

        # 4th request should be rate limited
        resp = client.get("/api/test", headers=headers)
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_different_users_have_separate_limits(self) -> None:
        """Different users should have independent rate limits."""
        from duh.api.auth import create_token

        app = await _make_app(rate_limit=2, window=60, jwt_secret="test-secret")
        client = TestClient(app, raise_server_exceptions=False)

        token_a = create_token("user-A", "test-secret")
        token_b = create_token("user-B", "test-secret")

        # User A uses 2 requests
        headers_a = {"Authorization": f"Bearer {token_a}"}
        for _ in range(2):
            resp = client.get("/api/test", headers=headers_a)
            assert resp.status_code == 200

        # User A is now limited
        resp = client.get("/api/test", headers=headers_a)
        assert resp.status_code == 429

        # User B should still be fine
        headers_b = {"Authorization": f"Bearer {token_b}"}
        resp = client.get("/api/test", headers=headers_b)
        assert resp.status_code == 200


# ── Rate Limit by API Key ───────────────────────────────────


class TestRateLimitByApiKey:
    @pytest.mark.asyncio
    async def test_rate_limit_by_api_key(self) -> None:
        """Requests with API key should be rate-limited by api_key_id."""
        app = await _make_app(rate_limit=3, window=60)
        await _seed_key(app, "test-key", "my-api-key")
        client = TestClient(app, raise_server_exceptions=False)

        headers = {"X-API-Key": "my-api-key"}

        # First 3 requests should succeed
        for _ in range(3):
            resp = client.get("/api/test", headers=headers)
            assert resp.status_code == 200

        # 4th request should be rate limited
        resp = client.get("/api/test", headers=headers)
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_different_api_keys_have_separate_limits(self) -> None:
        """Different API keys should have independent rate limits."""
        app = await _make_app(rate_limit=2, window=60)
        await _seed_key(app, "key-1", "api-key-1")
        await _seed_key(app, "key-2", "api-key-2")
        client = TestClient(app, raise_server_exceptions=False)

        # Key 1 uses 2 requests
        for _ in range(2):
            resp = client.get("/api/test", headers={"X-API-Key": "api-key-1"})
            assert resp.status_code == 200

        # Key 1 is now limited
        resp = client.get("/api/test", headers={"X-API-Key": "api-key-1"})
        assert resp.status_code == 429

        # Key 2 should still be fine
        resp = client.get("/api/test", headers={"X-API-Key": "api-key-2"})
        assert resp.status_code == 200


# ── Rate Limit by IP ────────────────────────────────────────


class TestRateLimitByIp:
    @pytest.mark.asyncio
    async def test_rate_limit_by_ip(self) -> None:
        """Unauthenticated requests should fall back to IP rate limiting."""
        app = await _make_app(rate_limit=3, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        # No keys in DB, so unauthenticated access allowed
        for _ in range(3):
            resp = client.get("/api/test")
            assert resp.status_code == 200

        # 4th request should be rate limited
        resp = client.get("/api/test")
        assert resp.status_code == 429


# ── Provider Rate Limit Config ───────────────────────────────


class TestProviderRateLimitConfig:
    def test_provider_config_accepts_rate_limit(self) -> None:
        """ProviderConfig should accept a rate_limit field."""
        config = ProviderConfig(rate_limit=100)
        assert config.rate_limit == 100

    def test_provider_config_default_rate_limit_zero(self) -> None:
        """Default rate_limit should be 0 (unlimited)."""
        config = ProviderConfig()
        assert config.rate_limit == 0

    def test_provider_config_rate_limit_in_dict(self) -> None:
        """rate_limit should appear in model dump."""
        config = ProviderConfig(rate_limit=50)
        data = config.model_dump()
        assert data["rate_limit"] == 50


# ── Provider Rate Limit Enforcement ──────────────────────────


class TestProviderRateLimitEnforcement:
    def test_provider_manager_respects_rate_limits(self) -> None:
        """ProviderManager should enforce per-provider rate limits."""
        from duh.providers.manager import ProviderManager, ProviderQuotaExceededError

        pm = ProviderManager()
        pm.set_provider_rate_limit("openai", 3)

        # First 3 checks should pass
        for _ in range(3):
            pm.check_provider_rate_limit("openai")

        # 4th check should raise
        with pytest.raises(ProviderQuotaExceededError) as exc_info:
            pm.check_provider_rate_limit("openai")
        assert exc_info.value.rate_limit == 3
        assert exc_info.value.provider_id == "openai"

    def test_unlimited_provider_never_limited(self) -> None:
        """Provider with rate_limit=0 should never be limited."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        pm.set_provider_rate_limit("anthropic", 0)

        # Should never raise
        for _ in range(1000):
            pm.check_provider_rate_limit("anthropic")

    def test_unconfigured_provider_never_limited(self) -> None:
        """Provider without a configured rate limit should never be limited."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()

        # Should never raise
        for _ in range(100):
            pm.check_provider_rate_limit("any-provider")

    def test_different_providers_have_separate_limits(self) -> None:
        """Different providers should have independent rate limits."""
        from duh.providers.manager import ProviderManager, ProviderQuotaExceededError

        pm = ProviderManager()
        pm.set_provider_rate_limit("openai", 2)
        pm.set_provider_rate_limit("anthropic", 2)

        # Exhaust openai
        pm.check_provider_rate_limit("openai")
        pm.check_provider_rate_limit("openai")
        with pytest.raises(ProviderQuotaExceededError):
            pm.check_provider_rate_limit("openai")

        # anthropic should still be fine
        pm.check_provider_rate_limit("anthropic")
        pm.check_provider_rate_limit("anthropic")

    def test_rate_limit_resets_after_window(self) -> None:
        """Provider rate limit should reset after the 60-second window."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        pm.set_provider_rate_limit("openai", 2)

        # Exhaust the limit
        pm.check_provider_rate_limit("openai")
        pm.check_provider_rate_limit("openai")

        # Simulate time passing by manipulating the timestamps
        pm._provider_requests["openai"] = [
            time.monotonic() - 61.0,
            time.monotonic() - 61.0,
        ]

        # Should work again
        pm.check_provider_rate_limit("openai")

    def test_get_provider_rate_limit_remaining(self) -> None:
        """get_provider_rate_limit_remaining returns correct count."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        pm.set_provider_rate_limit("openai", 5)

        assert pm.get_provider_rate_limit_remaining("openai") == 5

        pm.check_provider_rate_limit("openai")
        assert pm.get_provider_rate_limit_remaining("openai") == 4

        pm.check_provider_rate_limit("openai")
        assert pm.get_provider_rate_limit_remaining("openai") == 3

    def test_get_provider_rate_limit_remaining_no_limit(self) -> None:
        """get_provider_rate_limit_remaining returns None when no limit set."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        assert pm.get_provider_rate_limit_remaining("openai") is None

    @pytest.mark.asyncio
    async def test_get_provider_checks_rate_limit(self) -> None:
        """get_provider should check rate limit before returning provider."""
        from duh.providers.manager import ProviderManager, ProviderQuotaExceededError

        pm = ProviderManager()

        # Register a mock provider
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import MINIMAL

        provider = MockProvider(provider_id="mock-minimal", responses=MINIMAL)
        await pm.register(provider)  # type: ignore[arg-type]

        # Get models so we can use a valid model_ref
        models = pm.list_all_models()
        assert len(models) > 0
        model_ref = models[0].model_ref

        # Set rate limit
        pm.set_provider_rate_limit("mock-minimal", 2)

        # First 2 calls should work
        pm.get_provider(model_ref)
        pm.get_provider(model_ref)

        # 3rd should raise
        with pytest.raises(ProviderQuotaExceededError):
            pm.get_provider(model_ref)


# ── Rate Limit Headers ───────────────────────────────────────


class TestRateLimitHeaders:
    @pytest.mark.asyncio
    async def test_rate_limit_headers_with_user_id(self) -> None:
        """Response should include X-RateLimit-Key with user info when JWT auth used."""
        from duh.api.auth import create_token

        app = await _make_app(rate_limit=10, window=60, jwt_secret="test-secret")
        client = TestClient(app, raise_server_exceptions=False)

        token = create_token("user-42", "test-secret")
        resp = client.get("/api/test", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "9"
        assert resp.headers["X-RateLimit-Key"] == "user:user-42"

    @pytest.mark.asyncio
    async def test_rate_limit_headers_with_api_key(self) -> None:
        """Response should include X-RateLimit-Key with api_key info."""
        app = await _make_app(rate_limit=10, window=60)
        key_id = await _seed_key(app, "test-key", "my-api-key")
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/test", headers={"X-API-Key": "my-api-key"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "9"
        assert resp.headers["X-RateLimit-Key"] == f"api_key:{key_id}"

    @pytest.mark.asyncio
    async def test_rate_limit_headers_with_ip_fallback(self) -> None:
        """Response should include X-RateLimit-Key with IP when no auth."""
        app = await _make_app(rate_limit=10, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "9"
        # IP-based key
        assert resp.headers["X-RateLimit-Key"].startswith("ip:")

    @pytest.mark.asyncio
    async def test_rate_limit_headers_remaining_decrements(self) -> None:
        """X-RateLimit-Remaining should decrement with each request."""
        app = await _make_app(rate_limit=5, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        for expected_remaining in range(4, -1, -1):
            resp = client.get("/api/test")
            assert resp.status_code == 200
            assert resp.headers["X-RateLimit-Remaining"] == str(expected_remaining)
