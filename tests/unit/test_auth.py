"""Tests for JWT authentication: hashing, tokens, endpoints, middleware."""

from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.auth import (
    create_token,
    decode_token,
    hash_password,
    verify_password,
)
from duh.api.auth import (
    router as auth_router,
)
from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware
from duh.memory.models import Base

# ── Helpers ────────────────────────────────────────────────────


async def _make_auth_app(
    *,
    jwt_secret: str = "test-secret-key",
    registration_enabled: bool = True,
    token_expiry_hours: int = 24,
) -> FastAPI:
    """Create a minimal FastAPI app with auth routes and in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="test-auth")
    app.state.config = SimpleNamespace(
        auth=SimpleNamespace(
            jwt_secret=jwt_secret,
            registration_enabled=registration_enabled,
            token_expiry_hours=token_expiry_hours,
        ),
        api=SimpleNamespace(
            cors_origins=["http://localhost:3000"],
            rate_limit=100,
            rate_limit_window=60,
        ),
    )
    app.state.db_factory = factory
    app.state.engine = engine

    # Add middleware (same order as production)
    app.add_middleware(RateLimitMiddleware, rate_limit=100, window=60)
    app.add_middleware(APIKeyMiddleware)

    app.include_router(auth_router)

    @app.get("/api/test")
    async def test_endpoint() -> dict[str, str]:
        return {"msg": "ok"}

    return app


async def _register_user(
    client: TestClient,
    email: str = "test@example.com",
    password: str = "strong-pass-123",
    display_name: str = "Test User",
) -> dict:  # type: ignore[type-arg]
    """Helper to register a user and return the response JSON."""
    resp = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": password,
            "display_name": display_name,
        },
    )
    return resp.json()  # type: ignore[no-any-return]


# ── Password hashing ──────────────────────────────────────────


class TestHashPassword:
    def test_hash_password(self) -> None:
        """Hash produces a valid bcrypt hash string."""
        hashed = hash_password("mypassword")
        assert hashed.startswith("$2")
        assert len(hashed) == 60

    def test_verify_password_correct(self) -> None:
        """Correct password verifies successfully."""
        hashed = hash_password("correct-password")
        assert verify_password("correct-password", hashed) is True

    def test_verify_password_wrong(self) -> None:
        """Wrong password fails verification."""
        hashed = hash_password("correct-password")
        assert verify_password("wrong-password", hashed) is False


# ── JWT tokens ────────────────────────────────────────────────


class TestJWTTokens:
    def test_create_token(self) -> None:
        """Token is a valid JWT string."""
        token = create_token("user-123", "secret")
        assert isinstance(token, str)
        assert len(token) > 0
        # Should be decodable
        payload = jwt.decode(token, "secret", algorithms=["HS256"])
        assert payload["sub"] == "user-123"

    def test_decode_token_valid(self) -> None:
        """Decode returns payload with sub."""
        token = create_token("user-456", "secret", expiry_hours=1)
        payload = decode_token(token, "secret")
        assert payload["sub"] == "user-456"
        assert "exp" in payload
        assert "iat" in payload

    def test_decode_token_expired(self) -> None:
        """Expired token raises HTTPException."""
        from fastapi import HTTPException

        # Create a token that's already expired
        payload = {
            "sub": "user-789",
            "exp": time.time() - 3600,  # 1 hour ago
            "iat": time.time() - 7200,
        }
        token = jwt.encode(payload, "secret", algorithm="HS256")

        with pytest.raises(HTTPException) as exc_info:
            decode_token(token, "secret")
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_decode_token_invalid(self) -> None:
        """Invalid token raises HTTPException."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("not-a-valid-token", "secret")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in exc_info.value.detail


# ── Register endpoint ─────────────────────────────────────────


class TestRegisterEndpoint:
    async def test_register_endpoint(self) -> None:
        """POST /api/auth/register creates user and returns token."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "password123",
                "display_name": "New User",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"]
        assert data["role"] == "contributor"

    async def test_register_duplicate_email(self) -> None:
        """Duplicate email returns 409."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)
        # Register first time
        await _register_user(client, email="dup@example.com")
        # Register again with same email
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "dup@example.com",
                "password": "pass2",
                "display_name": "Dup User",
            },
        )
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"]

    async def test_register_disabled(self) -> None:
        """Returns 403 when registration_enabled=False."""
        app = await _make_auth_app(registration_enabled=False)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "pass",
                "display_name": "User",
            },
        )
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()


# ── Login endpoint ────────────────────────────────────────────


class TestLoginEndpoint:
    async def test_login_success(self) -> None:
        """Correct credentials return a token."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)
        await _register_user(client, email="login@example.com", password="mypass")

        resp = client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "mypass"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["role"] == "contributor"

    async def test_login_wrong_password(self) -> None:
        """Wrong password returns 401."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)
        await _register_user(client, email="wp@example.com", password="correct")

        resp = client.post(
            "/api/auth/login",
            json={"email": "wp@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    async def test_login_nonexistent_user(self) -> None:
        """Nonexistent email returns 401."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "pass"},
        )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]


# ── /me endpoint ──────────────────────────────────────────────


class TestMeEndpoint:
    async def test_me_endpoint(self) -> None:
        """GET /api/auth/me returns user info when authenticated."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)
        reg_data = await _register_user(client, email="me@example.com")
        token = reg_data["access_token"]

        resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "me@example.com"
        assert data["display_name"] == "Test User"
        assert data["role"] == "contributor"
        assert data["is_active"] is True

    async def test_me_no_token(self) -> None:
        """GET /api/auth/me without token returns 401."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


# ── JWT middleware integration ────────────────────────────────


class TestJWTMiddlewareIntegration:
    async def test_bearer_token_accepted_by_middleware(self) -> None:
        """Bearer token accepted by APIKeyMiddleware as alternative to X-API-Key."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)

        # Seed an API key so the middleware would reject requests without auth
        from duh.api.middleware import hash_api_key
        from duh.memory.repository import MemoryRepository

        async with app.state.db_factory() as session:
            repo = MemoryRepository(session)
            await repo.create_api_key("test-key", hash_api_key("secret-key"))
            await session.commit()

        # Register a user and get a JWT token
        reg_data = await _register_user(client, email="jwt@example.com")
        token = reg_data["access_token"]

        # Access /api/test with Bearer token (no X-API-Key)
        resp = client.get(
            "/api/test",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"msg": "ok"}

    async def test_no_auth_rejected_when_keys_exist(self) -> None:
        """Request with no auth is rejected when API keys exist in DB."""
        app = await _make_auth_app()
        client = TestClient(app, raise_server_exceptions=False)

        from duh.api.middleware import hash_api_key
        from duh.memory.repository import MemoryRepository

        async with app.state.db_factory() as session:
            repo = MemoryRepository(session)
            await repo.create_api_key("test-key", hash_api_key("secret-key"))
            await session.commit()

        # Access /api/test with no auth at all
        resp = client.get("/api/test")
        assert resp.status_code == 401
