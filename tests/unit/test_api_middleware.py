"""Tests for API middleware: auth, rate limiting, CORS."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware, hash_api_key
from duh.memory.models import Base
from duh.memory.repository import MemoryRepository


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ── Helpers ────────────────────────────────────────────────────


async def _make_app(
    *,
    rate_limit: int = 100,
    window: int = 60,
    cors_origins: list[str] | None = None,
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
            cors_origins=cors_origins or ["http://localhost:3000"],
            rate_limit=rate_limit,
            rate_limit_window=window,
        ),
    )
    app.state.db_factory = factory
    app.state.engine = engine

    # Middleware (reverse order: CORS outermost, auth innermost)
    if cors_origins is not None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

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


async def _revoke_key(app: FastAPI, key_id: str) -> None:
    """Revoke an API key in the test DB."""
    async with app.state.db_factory() as session:
        repo = MemoryRepository(session)
        await repo.revoke_api_key(key_id)
        await session.commit()


# ── hash_api_key ───────────────────────────────────────────────


class TestHashAPIKey:
    def test_produces_sha256_hex(self) -> None:
        result = hash_api_key("my-secret-key")
        expected = hashlib.sha256(b"my-secret-key").hexdigest()
        assert result == expected

    def test_consistent(self) -> None:
        assert hash_api_key("test") == hash_api_key("test")

    def test_different_inputs_differ(self) -> None:
        assert hash_api_key("a") != hash_api_key("b")


# ── APIKeyMiddleware ───────────────────────────────────────────


class TestAPIKeyMiddleware:
    async def test_health_exempt(self) -> None:
        """Health endpoint does not require auth."""
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/health")
        assert resp.status_code == 200

    async def test_docs_exempt(self) -> None:
        """Docs endpoints do not require auth."""
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/docs")
        assert resp.status_code != 401

    async def test_no_keys_allows_unauthenticated(self) -> None:
        """Dev mode: no keys in DB allows unauthenticated access."""
        app = await _make_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert resp.json() == {"msg": "ok"}

    async def test_missing_key_returns_401_when_keys_exist(self) -> None:
        """If keys exist in DB but no header provided, return 401."""
        app = await _make_app()
        await _seed_key(app, "existing", "secret-1")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")
        assert resp.status_code == 401
        assert "Missing API key" in resp.json()["detail"]

    async def test_invalid_key_returns_401(self) -> None:
        """An invalid API key returns 401."""
        app = await _make_app()
        await _seed_key(app, "valid", "real-key")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test", headers={"X-API-Key": "wrong-key"})
        assert resp.status_code == 401
        assert "Invalid or revoked" in resp.json()["detail"]

    async def test_revoked_key_returns_401(self) -> None:
        """A revoked API key returns 401."""
        app = await _make_app()
        key_id = await _seed_key(app, "to-revoke", "rev-key")
        await _revoke_key(app, key_id)

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test", headers={"X-API-Key": "rev-key"})
        assert resp.status_code == 401
        assert "Invalid or revoked" in resp.json()["detail"]

    async def test_valid_key_passes(self) -> None:
        """A valid API key allows the request through."""
        app = await _make_app()
        await _seed_key(app, "good", "my-key")

        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test", headers={"X-API-Key": "my-key"})
        assert resp.status_code == 200
        assert resp.json() == {"msg": "ok"}


# ── RateLimitMiddleware ────────────────────────────────────────


class TestRateLimitMiddleware:
    async def test_requests_within_limit_succeed(self) -> None:
        """Requests under the limit return 200."""
        app = await _make_app(rate_limit=5, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(5):
            resp = client.get("/api/test")
            assert resp.status_code == 200

    async def test_exceeding_limit_returns_429(self) -> None:
        """Exceeding rate limit returns 429."""
        app = await _make_app(rate_limit=3, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        for _ in range(3):
            resp = client.get("/api/test")
            assert resp.status_code == 200

        resp = client.get("/api/test")
        assert resp.status_code == 429
        assert "Rate limit exceeded" in resp.json()["detail"]

    async def test_rate_limit_headers_present(self) -> None:
        """Rate limit headers are included in responses."""
        app = await _make_app(rate_limit=10, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/test")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" in resp.headers
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert "X-RateLimit-Remaining" in resp.headers
        assert resp.headers["X-RateLimit-Remaining"] == "9"

    async def test_retry_after_header_on_429(self) -> None:
        """429 responses include Retry-After header."""
        app = await _make_app(rate_limit=1, window=120)
        client = TestClient(app, raise_server_exceptions=False)
        client.get("/api/test")  # consume the one allowed

        resp = client.get("/api/test")
        assert resp.status_code == 429
        assert resp.headers["Retry-After"] == "120"


# ── CORS ───────────────────────────────────────────────────────


class TestCORSHeaders:
    async def test_cors_headers_present(self) -> None:
        """CORS headers are returned for configured origins."""
        app = await _make_app(cors_origins=["http://localhost:3000"])
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get(
            "/api/test",
            headers={"Origin": "http://localhost:3000"},
        )
        assert (
            resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        )

    async def test_preflight_options(self) -> None:
        """OPTIONS preflight returns proper CORS headers."""
        app = await _make_app(cors_origins=["http://localhost:3000"])
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.options(
            "/api/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-API-Key",
            },
        )
        assert resp.status_code == 200
        assert (
            resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
        )
        assert "X-API-Key" in resp.headers.get("access-control-allow-headers", "")
