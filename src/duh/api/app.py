"""FastAPI application factory for the duh REST API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import APIRouter, FastAPI, HTTPException

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Callable
    from contextlib import AbstractAsyncContextManager as AsyncContextManager

    from duh.config.schema import DuhConfig


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan handler: set up DB + providers on startup, tear down on shutdown."""
    from duh.cli.app import _create_db, _setup_providers, _setup_tools

    config: DuhConfig = app.state.config
    factory, engine = await _create_db(config)
    try:
        pm = await _setup_providers(config)
        app.state.db_factory = factory
        app.state.engine = engine
        app.state.provider_manager = pm
        app.state.tool_registry = _setup_tools(config)

        extra = getattr(app.state, "extra_lifespan", None)
        if extra is not None:
            async with extra(app):
                yield
        else:
            yield
    finally:
        await engine.dispose()


def create_app(
    config: DuhConfig | None = None,
    extra_routers: list[APIRouter] | None = None,
    extra_lifespan: Callable[[FastAPI], AsyncContextManager[None]] | None = None,
    *,
    include_engine_routes: bool = True,
    include_frontend: bool = True,
    include_diagnostics: bool = True,
    include_api_key_middleware: bool = True,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Application configuration. Loaded from defaults if None.
        extra_routers: Additional routers registered after built-in routes
            but before the frontend static file mount.
        extra_lifespan: Additional async context manager composed with the
            built-in lifespan. Runs after DB/provider setup.
        include_engine_routes: Mount consensus and stored-data endpoints.
        include_frontend: Mount the bundled frontend and SPA fallback.
        include_diagnostics: Mount metrics and detailed provider health checks.
        include_api_key_middleware: Authenticate the engine API globally. Hosts
            that omit engine routes can use their own router dependencies.
    """
    from duh.config.loader import load_config

    if config is None:
        config = load_config()

    app = FastAPI(
        title="duh",
        description="Multi-model consensus engine API",
        version="0.6.0",
        lifespan=lifespan,
    )
    app.state.config = config
    app.state.extra_lifespan = extra_lifespan

    # ── Middleware (Starlette runs in reverse order of addition) ──
    from fastapi.middleware.cors import CORSMiddleware

    from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware

    # Rate limiting (runs after auth so api_key_id is available)
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit=config.api.rate_limit,
        window=config.api.rate_limit_window,
    )

    # API key auth (added last — runs first)
    if include_api_key_middleware:
        app.add_middleware(APIKeyMiddleware)

    # Added last so preflight and authentication errors receive CORS headers.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.api.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    from duh.api.routes.ask import router as ask_router
    from duh.api.routes.crud import router as crud_router
    from duh.api.routes.threads import router as threads_router
    from duh.api.routes.ws import router as ws_router

    if include_engine_routes:
        app.include_router(ask_router)
        app.include_router(crud_router)
        app.include_router(threads_router)
        app.include_router(ws_router)

    from duh.api.auth import router as auth_router
    from duh.api.health import health
    from duh.api.health import router as health_router
    from duh.api.metrics import router as metrics_router

    app.include_router(auth_router)
    if include_diagnostics:
        app.include_router(health_router)
        app.include_router(metrics_router)
    else:
        app.add_api_route("/api/health", health, tags=["health"])

    # Extra routers from external packages
    if extra_routers:
        for r in extra_routers:
            app.include_router(r)

    # ── Static file serving for web UI ──
    if include_frontend:
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
    dist_dir = dist_dir.resolve()

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
        if full_path in {"api", "ws"} or full_path.startswith(("api/", "ws/")):
            raise HTTPException(status_code=404, detail="Not found")
        requested = (dist_dir / full_path).resolve()
        if not requested.is_relative_to(dist_dir):
            raise HTTPException(status_code=404, detail="Not found")
        if requested.is_file():
            return FileResponse(str(requested))
        return FileResponse(str(index_html))
