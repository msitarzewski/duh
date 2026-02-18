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
        version="0.5.0",
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

    # Routes
    from duh.api.routes.ask import router as ask_router
    from duh.api.routes.crud import router as crud_router
    from duh.api.routes.threads import router as threads_router
    from duh.api.routes.ws import router as ws_router

    app.include_router(ask_router)
    app.include_router(crud_router)
    app.include_router(threads_router)
    app.include_router(ws_router)

    from duh.api.auth import router as auth_router
    from duh.api.health import router as health_router
    from duh.api.metrics import router as metrics_router

    app.include_router(auth_router)
    app.include_router(health_router)
    app.include_router(metrics_router)

    # ── Static file serving for web UI ──
    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Mount web UI static files with SPA fallback if dist/ exists."""
    from pathlib import Path

    # Look for web/dist relative to project root
    candidates = [
        # dev: src/duh/api -> project root
        Path(__file__).resolve().parents[3] / "web" / "dist",
        Path("/app/web/dist"),  # docker
    ]
    dist_dir: Path | None = None
    for p in candidates:
        if p.is_dir() and (p / "index.html").exists():
            dist_dir = p
            break

    if dist_dir is None:
        return

    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    # Serve assets with cache headers
    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(assets_dir)),
            name="static-assets",
        )

    index_html = dist_dir / "index.html"

    # SPA fallback: serve index.html for any non-API, non-asset path
    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        """Serve the SPA index.html for client-side routing."""
        # Check if the requested file exists in dist/
        requested = dist_dir / full_path
        if requested.is_file():
            return FileResponse(str(requested))
        return FileResponse(str(index_html))
