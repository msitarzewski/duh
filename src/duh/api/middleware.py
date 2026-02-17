"""API middleware: authentication, rate limiting, CORS."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from typing import TYPE_CHECKING, ClassVar

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import Request, Response


def hash_api_key(raw_key: str) -> str:
    """Hash an API key for storage/comparison."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate X-API-Key header against stored API keys."""

    EXEMPT_PATHS: ClassVar[set[str]] = {
        "/api/health",
        "/docs",
        "/openapi.json",
        "/redoc",
    }

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Skip auth for exempt paths
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip auth if no API keys are configured (dev mode)
        db_factory = request.app.state.db_factory

        raw_key = request.headers.get("X-API-Key")
        if raw_key is None:
            # If no keys exist in DB, allow unauthenticated access
            from duh.memory.repository import MemoryRepository

            async with db_factory() as session:
                repo = MemoryRepository(session)
                keys = await repo.list_api_keys()
            if not keys:
                return await call_next(request)
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing API key. Provide X-API-Key header."},
            )

        # Validate the key
        key_hash = hash_api_key(raw_key)
        from duh.memory.repository import MemoryRepository

        async with db_factory() as session:
            repo = MemoryRepository(session)
            api_key = await repo.validate_api_key(key_hash)

        if api_key is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or revoked API key."},
            )

        # Store key info on request state for rate limiting
        request.state.api_key_id = api_key.id
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-key rate limiting using sliding window."""

    def __init__(self, app: object, rate_limit: int = 60, window: int = 60) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.rate_limit = rate_limit
        self.window = window
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Get key identifier (API key ID or IP for unauthenticated)
        key_id = getattr(request.state, "api_key_id", None) or (
            request.client.host if request.client else "unknown"
        )

        now = time.monotonic()
        # Clean old entries
        self._requests[key_id] = [
            t for t in self._requests[key_id] if now - t < self.window
        ]

        if len(self._requests[key_id]) >= self.rate_limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={"Retry-After": str(self.window)},
            )

        self._requests[key_id].append(now)
        response = await call_next(request)

        # Add rate limit headers
        remaining = self.rate_limit - len(self._requests[key_id])
        response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
