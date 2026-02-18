"""Tests for health check endpoints."""

from __future__ import annotations

import hashlib
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.health import router as health_router
from duh.api.middleware import APIKeyMiddleware
from duh.memory.models import Base


@pytest.fixture
async def health_app():
    """FastAPI app with health router and an in-memory DB."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI()
    app.state.db_factory = factory
    app.state.engine = engine
    app.include_router(health_router)

    yield app

    await engine.dispose()


class TestHealthBasic:
    def test_health_basic(self):
        """GET /api/health returns {"status": "ok"}."""
        from duh.api.app import create_app
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        config.database.url = "sqlite+aiosqlite:///:memory:"
        app = create_app(config)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestHealthDetailed:
    async def test_health_detailed_ok(self, health_app):
        """GET /api/health/detailed returns status, version, uptime, components."""
        client = TestClient(health_app, raise_server_exceptions=False)
        resp = client.get("/api/health/detailed")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "components" in data

    async def test_health_detailed_db_check(self, health_app):
        """Database component shows ok with working DB."""
        client = TestClient(health_app, raise_server_exceptions=False)
        resp = client.get("/api/health/detailed")
        data = resp.json()
        assert data["components"]["database"]["status"] == "ok"

    async def test_health_detailed_db_failure(self, health_app):
        """Database component shows error when DB fails."""

        # Replace db_factory with one that raises
        async def broken_factory():
            raise RuntimeError("DB is down")

        health_app.state.db_factory = MagicMock(side_effect=RuntimeError("DB is down"))

        client = TestClient(health_app, raise_server_exceptions=False)
        resp = client.get("/api/health/detailed")
        data = resp.json()
        assert data["components"]["database"]["status"] == "error"
        assert "DB is down" in data["components"]["database"]["detail"]
        assert data["status"] == "degraded"

    async def test_health_detailed_provider_healthy(self, health_app):
        """Provider shows ok when health_check returns True."""
        mock_provider = AsyncMock()
        mock_provider.health_check.return_value = True

        pm = MagicMock()
        pm._providers = {"test-provider": mock_provider}
        health_app.state.provider_manager = pm

        client = TestClient(health_app, raise_server_exceptions=False)
        resp = client.get("/api/health/detailed")
        data = resp.json()
        assert data["components"]["providers"]["test-provider"]["status"] == "ok"
        assert data["status"] == "ok"

    async def test_health_detailed_provider_unhealthy(self, health_app):
        """Provider shows unhealthy, status = degraded when all providers fail."""
        mock_provider = AsyncMock()
        mock_provider.health_check.return_value = False

        pm = MagicMock()
        pm._providers = {"bad-provider": mock_provider}
        health_app.state.provider_manager = pm

        client = TestClient(health_app, raise_server_exceptions=False)
        resp = client.get("/api/health/detailed")
        data = resp.json()
        assert data["components"]["providers"]["bad-provider"]["status"] == "unhealthy"
        assert data["status"] == "degraded"

    async def test_health_detailed_uptime(self, health_app):
        """Uptime is a positive number."""
        client = TestClient(health_app, raise_server_exceptions=False)
        resp = client.get("/api/health/detailed")
        data = resp.json()
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0


class TestHealthNoAuth:
    async def test_health_no_auth_required(self):
        """Both health endpoints are accessible without API key."""
        engine = create_async_engine("sqlite+aiosqlite://")

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_fks(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Seed an API key so auth is enforced
        from duh.memory.repository import MemoryRepository

        async with factory() as session:
            repo = MemoryRepository(session)
            await repo.create_api_key(
                "test-key",
                hashlib.sha256(b"secret").hexdigest(),
            )
            await session.commit()

        app = FastAPI()
        app.state.db_factory = factory
        app.state.engine = engine
        app.add_middleware(APIKeyMiddleware)
        app.include_router(health_router)

        @app.get("/api/protected")
        async def protected():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)

        # /api/health should be accessible without API key
        resp = client.get("/api/health")
        assert resp.status_code == 200

        # /api/health/detailed should be accessible without API key
        resp2 = client.get("/api/health/detailed")
        assert resp2.status_code == 200

        # A non-exempt API path should fail without a key
        resp3 = client.get("/api/protected")
        assert resp3.status_code == 401

        await engine.dispose()
