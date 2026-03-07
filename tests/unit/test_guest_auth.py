"""Tests for guest authentication endpoint."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.auth import router as auth_router
from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware
from duh.memory.models import Base, User


async def _make_guest_app(
    *,
    jwt_secret: str = "test-secret-key",
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

    app = FastAPI(title="test-guest")
    app.state.config = SimpleNamespace(
        auth=SimpleNamespace(
            jwt_secret=jwt_secret,
            registration_enabled=True,
            token_expiry_hours=24,
        ),
        api=SimpleNamespace(
            cors_origins=["http://localhost:3000"],
            rate_limit=100,
            rate_limit_window=60,
        ),
    )
    app.state.db_factory = factory
    app.state.engine = engine

    app.add_middleware(RateLimitMiddleware, rate_limit=100, window=60)
    app.add_middleware(APIKeyMiddleware)

    app.include_router(auth_router)
    return app


class TestGuestEndpoint:
    async def test_create_guest(self) -> None:
        """POST /api/auth/guest creates a guest user and returns token."""
        app = await _make_guest_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/auth/guest", json={"email": "guest@example.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"]
        assert data["role"] == "contributor"

    async def test_guest_idempotent(self) -> None:
        """Calling guest endpoint twice with same email returns tokens for same user."""
        app = await _make_guest_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp1 = client.post("/api/auth/guest", json={"email": "same@example.com"})
        resp2 = client.post("/api/auth/guest", json={"email": "same@example.com"})

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["user_id"] == resp2.json()["user_id"]

    async def test_guest_conflict_with_registered_user(self) -> None:
        """Guest endpoint returns 409 if email belongs to a registered user."""
        app = await _make_guest_app()
        client = TestClient(app, raise_server_exceptions=False)

        # Register a full user first
        client.post(
            "/api/auth/register",
            json={
                "email": "registered@example.com",
                "password": "strong-pass",
                "display_name": "Registered",
            },
        )

        # Try guest login with same email
        resp = client.post("/api/auth/guest", json={"email": "registered@example.com"})
        assert resp.status_code == 409
        assert "log in" in resp.json()["detail"].lower()

    async def test_guest_user_has_is_guest_flag(self) -> None:
        """Guest user is created with is_guest=True."""
        app = await _make_guest_app()
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/api/auth/guest", json={"email": "flag@example.com"})
        assert resp.status_code == 200
        user_id = resp.json()["user_id"]

        from sqlalchemy import select

        async with app.state.db_factory() as session:
            user = (
                await session.execute(select(User).where(User.id == user_id))
            ).scalar_one()
            assert user.is_guest is True
            assert user.password_hash is None

    async def test_guest_endpoint_exempt_from_api_key(self) -> None:
        """Guest endpoint is accessible without API key."""
        app = await _make_guest_app()
        client = TestClient(app, raise_server_exceptions=False)

        # Seed an API key so middleware enforces auth
        from duh.api.middleware import hash_api_key
        from duh.memory.repository import MemoryRepository

        async with app.state.db_factory() as session:
            repo = MemoryRepository(session)
            await repo.create_api_key("test-key", hash_api_key("secret-key"))
            await session.commit()

        resp = client.post("/api/auth/guest", json={"email": "exempt@example.com"})
        assert resp.status_code == 200
