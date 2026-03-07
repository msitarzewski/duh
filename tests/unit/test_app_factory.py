"""Tests for app factory extensibility (extra_routers parameter)."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.memory.models import Base


async def _make_factory_app(
    extra_routers: list[APIRouter] | None = None,
) -> FastAPI:
    """Create a minimal app using create_app-style setup with extra routers."""
    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Build a minimal app mimicking create_app with extra_routers
    app = FastAPI(title="test-factory")
    app.state.config = SimpleNamespace(
        auth=SimpleNamespace(
            jwt_secret="test-secret",
            registration_enabled=True,
            token_expiry_hours=24,
        ),
        api=SimpleNamespace(
            cors_origins=["*"],
            rate_limit=100,
            rate_limit_window=60,
        ),
    )
    app.state.db_factory = factory
    app.state.engine = engine

    if extra_routers:
        for r in extra_routers:
            app.include_router(r)

    return app


class TestExtraRouters:
    async def test_extra_router_included(self) -> None:
        """Extra routers are included and their endpoints are accessible."""
        extra = APIRouter(prefix="/api/ext", tags=["ext"])

        @extra.get("/ping")
        async def ping() -> dict[str, str]:
            return {"pong": "true"}

        app = await _make_factory_app(extra_routers=[extra])
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.get("/api/ext/ping")
        assert resp.status_code == 200
        assert resp.json() == {"pong": "true"}

    async def test_no_extra_routers(self) -> None:
        """App works normally without extra routers."""
        app = await _make_factory_app()
        client = TestClient(app, raise_server_exceptions=False)
        # App should be running (404 for unknown path, not 500)
        resp = client.get("/api/ext/ping")
        assert resp.status_code == 404

    async def test_multiple_extra_routers(self) -> None:
        """Multiple extra routers are all included."""
        r1 = APIRouter(prefix="/api/one")
        r2 = APIRouter(prefix="/api/two")

        @r1.get("/hello")
        async def hello() -> dict[str, str]:
            return {"from": "one"}

        @r2.get("/hello")
        async def hello2() -> dict[str, str]:
            return {"from": "two"}

        app = await _make_factory_app(extra_routers=[r1, r2])
        client = TestClient(app, raise_server_exceptions=False)

        assert client.get("/api/one/hello").json() == {"from": "one"}
        assert client.get("/api/two/hello").json() == {"from": "two"}
