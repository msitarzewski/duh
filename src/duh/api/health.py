"""Health check endpoints."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter(tags=["health"])

_START_TIME = time.monotonic()


@router.get("/api/health")
async def health() -> dict[str, str]:
    """Basic health check -- always returns quickly."""
    return {"status": "ok"}


@router.get("/api/health/detailed")
async def health_detailed(request: Request) -> dict[str, Any]:
    """Detailed health check with component status."""
    from duh import __version__

    checks: dict[str, Any] = {
        "status": "ok",
        "version": __version__,
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "components": {},
    }

    # Database check
    try:
        db_factory = request.app.state.db_factory
        async with db_factory() as session:
            from sqlalchemy import text

            await session.execute(text("SELECT 1"))
        checks["components"]["database"] = {"status": "ok"}
    except Exception as e:
        checks["components"]["database"] = {"status": "error", "detail": str(e)}
        checks["status"] = "degraded"

    # Provider health checks
    pm = getattr(request.app.state, "provider_manager", None)
    if pm is not None:
        provider_statuses: dict[str, dict[str, str]] = {}
        for pid, provider in pm._providers.items():
            try:
                healthy = await provider.health_check()
                provider_statuses[pid] = {"status": "ok" if healthy else "unhealthy"}
            except Exception:
                provider_statuses[pid] = {"status": "error"}
        checks["components"]["providers"] = provider_statuses

        # If all providers are unhealthy, status is degraded
        if provider_statuses and all(
            v["status"] != "ok" for v in provider_statuses.values()
        ):
            checks["status"] = "degraded"

    return checks
