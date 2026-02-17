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
        "/api/health/detailed",
        "/api/metrics",
        "/api/auth/register",
        "/api/auth/login",
        "/docs",
        "/openapi.json",
        "/redoc",
    }
    EXEMPT_PREFIXES: ClassVar[list[str]] = [
        "/api/share/",
    ]

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path

        # Skip auth for exempt paths
        if path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip auth for exempt prefixes
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return await call_next(request)

        # Skip auth for non-API paths (frontend static files)
        if not path.startswith("/api/") and not path.startswith("/ws/"):
            return await call_next(request)

        # Accept JWT Bearer token as alternative to API key
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Decode JWT and set user_id on request.state for rate limiting
            token = auth_header.split(" ", 1)[1]
            try:
                config = request.app.state.config
                from duh.api.auth import decode_token

                payload = decode_token(token, config.auth.jwt_secret)
                request.state.user_id = payload.get("sub")
            except Exception:
                # Let the auth dependency handle full validation;
                # middleware just extracts user_id if possible.
                pass
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
        # Get key identifier: prefer user_id (JWT), then api_key_id, then IP
        user_id = getattr(request.state, "user_id", None)
        api_key_id = getattr(request.state, "api_key_id", None)
        ip_addr = request.client.host if request.client else "unknown"
        key_id = user_id or api_key_id or ip_addr

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

        # Add rate limit identity headers
        if user_id:
            response.headers["X-RateLimit-Key"] = f"user:{user_id}"
        elif api_key_id:
            response.headers["X-RateLimit-Key"] = f"api_key:{api_key_id}"
        else:
            response.headers["X-RateLimit-Key"] = f"ip:{ip_addr}"

        return response
