"""FastAPI application factory for the duh REST API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from duh.config.schema import DuhConfig


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler: set up DB + providers on startup, tear down on shutdown."""
    from duh.cli.app import _create_db, _setup_providers

    config: DuhConfig = app.state.config
    factory, engine = await _create_db(config)
    pm = await _setup_providers(config)

    app.state.db_factory = factory
    app.state.engine = engine
    app.state.provider_manager = pm

    yield

    await engine.dispose()


def create_app(config: DuhConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    from duh.config.loader import load_config

    if config is None:
        config = load_config()

    app = FastAPI(
        title="duh",
        description="Multi-model consensus engine API",
        version="0.3.0",
        lifespan=lifespan,
    )
    app.state.config = config

    # ── Middleware (Starlette runs in reverse order of addition) ──
    from fastapi.middleware.cors import CORSMiddleware

    from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware

    # CORS (outermost — added first, runs last)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting (runs after auth so api_key_id is available)
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit=config.api.rate_limit,
        window=config.api.rate_limit_window,
    )

    # API key auth (added last — runs first)
    app.add_middleware(APIKeyMiddleware)

    # Health endpoint
    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # Routes
    from duh.api.routes.ask import router as ask_router
    from duh.api.routes.crud import router as crud_router
    from duh.api.routes.threads import router as threads_router
    from duh.api.routes.ws import router as ws_router

    app.include_router(ask_router)
    app.include_router(crud_router)
    app.include_router(threads_router)
    app.include_router(ws_router)

    return app
