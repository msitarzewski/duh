"""Load tests for the duh REST API.

Measures p50/p95/p99 latency, error rates under concurrent load,
and rate limiting behavior. Uses httpx AsyncClient with ASGITransport
for direct ASGI testing (no network required).

Run with:  uv run python -m pytest tests/load/test_load.py -v -m load -s
"""

from __future__ import annotations

import asyncio
import statistics
import time
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.api.metrics import MetricsRegistry
from duh.memory.models import Base

if TYPE_CHECKING:
    from fastapi import FastAPI


# ── Helpers ─────────────────────────────────────────────────────


async def _make_load_app(
    *,
    rate_limit: int = 1000,
    rate_limit_window: int = 60,
) -> FastAPI:
    """Create a FastAPI app with in-memory DB for load testing.

    Follows the pattern from tests/unit/test_auth.py:_make_auth_app.
    Uses a high default rate limit to avoid throttling during latency tests.
    """
    from fastapi import FastAPI

    from duh.api.auth import router as auth_router
    from duh.api.health import router as health_router
    from duh.api.metrics import router as metrics_router
    from duh.api.middleware import APIKeyMiddleware, RateLimitMiddleware
    from duh.api.routes.threads import router as threads_router

    engine = create_async_engine("sqlite+aiosqlite://")

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    app = FastAPI(title="duh-load-test")
    app.state.config = SimpleNamespace(
        auth=SimpleNamespace(
            jwt_secret="load-test-secret",
            registration_enabled=True,
            token_expiry_hours=24,
        ),
        api=SimpleNamespace(
            cors_origins=["http://localhost:3000"],
            rate_limit=rate_limit,
            rate_limit_window=rate_limit_window,
        ),
    )
    app.state.db_factory = factory
    app.state.engine = engine

    # Middleware (reverse order: auth runs first, then rate-limit)
    app.add_middleware(
        RateLimitMiddleware,
        rate_limit=rate_limit,
        window=rate_limit_window,
    )
    app.add_middleware(APIKeyMiddleware)

    app.include_router(health_router)
    app.include_router(metrics_router)
    app.include_router(threads_router)
    app.include_router(auth_router)

    return app


def _percentile(data: list[float], pct: float) -> float:
    """Return the value at the given percentile (0-100)."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * pct / 100)
    idx = min(idx, len(sorted_data) - 1)
    return sorted_data[idx]


def _report_latencies(
    label: str,
    latencies: list[float],
) -> None:
    """Print a summary of latency distribution."""
    p50 = statistics.median(latencies)
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    mean = statistics.mean(latencies)
    print(
        f"\n  {label}: "
        f"p50={p50:.1f}ms  p95={p95:.1f}ms  p99={p99:.1f}ms  "
        f"mean={mean:.1f}ms  n={len(latencies)}"
    )


# ── Latency tests ──────────────────────────────────────────────


@pytest.mark.load
async def test_health_endpoint_latency():
    """Measure p50/p95/p99 latency for GET /api/health."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            resp = await client.get("/api/health")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert resp.status_code == 200

    _report_latencies("GET /api/health", latencies)
    assert statistics.median(latencies) < 100, "p50 latency should be under 100ms"
    await app.state.engine.dispose()


@pytest.mark.load
async def test_health_detailed_endpoint_latency():
    """Measure p50/p95/p99 latency for GET /api/health/detailed."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            resp = await client.get("/api/health/detailed")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert resp.status_code == 200

    _report_latencies("GET /api/health/detailed", latencies)
    assert statistics.median(latencies) < 200, "p50 latency should be under 200ms"
    await app.state.engine.dispose()


@pytest.mark.load
async def test_threads_endpoint_latency():
    """Measure p50/p95/p99 latency for GET /api/threads (empty list)."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            resp = await client.get("/api/threads")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert resp.status_code == 200

    _report_latencies("GET /api/threads", latencies)
    assert statistics.median(latencies) < 200, "p50 latency should be under 200ms"
    await app.state.engine.dispose()


@pytest.mark.load
async def test_metrics_endpoint_latency():
    """Measure p50/p95/p99 latency for GET /api/metrics."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies: list[float] = []
        for _ in range(100):
            start = time.perf_counter()
            resp = await client.get("/api/metrics")
            elapsed = (time.perf_counter() - start) * 1000
            latencies.append(elapsed)
            assert resp.status_code == 200

    _report_latencies("GET /api/metrics", latencies)
    assert statistics.median(latencies) < 100, "p50 latency should be under 100ms"
    await app.state.engine.dispose()


# ── Concurrent request tests ───────────────────────────────────


async def _run_concurrent(
    client: AsyncClient,
    method: str,
    url: str,
    concurrency: int,
) -> tuple[list[float], list[int]]:
    """Fire `concurrency` requests in parallel, return (latencies, status_codes)."""

    async def _single_request() -> tuple[float, int]:
        start = time.perf_counter()
        if method == "GET":
            resp = await client.get(url)
        else:
            resp = await client.post(url)
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, resp.status_code

    results = await asyncio.gather(*[_single_request() for _ in range(concurrency)])
    latencies = [r[0] for r in results]
    status_codes = [r[1] for r in results]
    return latencies, status_codes


@pytest.mark.load
async def test_concurrent_health_10():
    """10 concurrent requests to /api/health -- all should succeed."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies, codes = await _run_concurrent(client, "GET", "/api/health", 10)

    _report_latencies("10 concurrent GET /api/health", latencies)
    error_count = sum(1 for c in codes if c >= 500)
    error_rate = error_count / len(codes)
    print(f"  Error rate: {error_rate:.1%} ({error_count}/{len(codes)})")
    assert error_rate < 0.01, f"Error rate {error_rate:.1%} exceeds 1%"
    await app.state.engine.dispose()


@pytest.mark.load
async def test_concurrent_health_50():
    """50 concurrent requests to /api/health -- error rate < 1%."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies, codes = await _run_concurrent(client, "GET", "/api/health", 50)

    _report_latencies("50 concurrent GET /api/health", latencies)
    error_count = sum(1 for c in codes if c >= 500)
    error_rate = error_count / len(codes)
    print(f"  Error rate: {error_rate:.1%} ({error_count}/{len(codes)})")
    assert error_rate < 0.01, f"Error rate {error_rate:.1%} exceeds 1%"
    await app.state.engine.dispose()


@pytest.mark.load
async def test_concurrent_health_100():
    """100 concurrent requests to /api/health -- error rate < 1%."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies, codes = await _run_concurrent(client, "GET", "/api/health", 100)

    _report_latencies("100 concurrent GET /api/health", latencies)
    error_count = sum(1 for c in codes if c >= 500)
    error_rate = error_count / len(codes)
    print(f"  Error rate: {error_rate:.1%} ({error_count}/{len(codes)})")
    assert error_rate < 0.01, f"Error rate {error_rate:.1%} exceeds 1%"
    await app.state.engine.dispose()


@pytest.mark.load
async def test_concurrent_threads_50():
    """50 concurrent requests to /api/threads -- error rate < 1%."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        latencies, codes = await _run_concurrent(client, "GET", "/api/threads", 50)

    _report_latencies("50 concurrent GET /api/threads", latencies)
    error_count = sum(1 for c in codes if c >= 500)
    error_rate = error_count / len(codes)
    print(f"  Error rate: {error_rate:.1%} ({error_count}/{len(codes)})")
    assert error_rate < 0.01, f"Error rate {error_rate:.1%} exceeds 1%"
    await app.state.engine.dispose()


@pytest.mark.load
async def test_concurrent_mixed_endpoints_50():
    """50 concurrent requests across health, threads, and metrics."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    endpoints = ["/api/health", "/api/threads", "/api/metrics"]

    async def _single_request(url: str) -> tuple[float, int]:
        start = time.perf_counter()
        resp = await client.get(url)
        elapsed = (time.perf_counter() - start) * 1000
        return elapsed, resp.status_code

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [_single_request(endpoints[i % len(endpoints)]) for i in range(50)]
        results = await asyncio.gather(*tasks)

    latencies = [r[0] for r in results]
    codes = [r[1] for r in results]

    _report_latencies("50 concurrent mixed endpoints", latencies)
    error_count = sum(1 for c in codes if c >= 500)
    error_rate = error_count / len(codes)
    print(f"  Error rate: {error_rate:.1%} ({error_count}/{len(codes)})")
    assert error_rate < 0.01, f"Error rate {error_rate:.1%} exceeds 1%"
    await app.state.engine.dispose()


# ── Rate limiting under load ───────────────────────────────────


@pytest.mark.load
async def test_rate_limiting_under_load():
    """Verify rate limiter triggers when limit is exceeded under concurrent load.

    Sets a low rate limit (10 req/60s) and fires 25 requests concurrently.
    Expects some requests to get 429 Too Many Requests.
    """
    MetricsRegistry.reset()
    app = await _make_load_app(rate_limit=10, rate_limit_window=60)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        _latencies, codes = await _run_concurrent(client, "GET", "/api/health", 25)

    ok_count = sum(1 for c in codes if c == 200)
    limited_count = sum(1 for c in codes if c == 429)

    print(f"\n  Rate limit test: {ok_count} OK, {limited_count} rate-limited")
    print("  Rate limit: 10 req/60s, sent 25 requests concurrently")

    # The rate limiter should have allowed at most 10 requests
    assert ok_count <= 10, f"Expected at most 10 OK responses, got {ok_count}"
    assert limited_count >= 15, (
        f"Expected at least 15 rate-limited, got {limited_count}"
    )
    await app.state.engine.dispose()


@pytest.mark.load
async def test_rate_limit_headers_present():
    """Verify rate limit response headers are present under load."""
    MetricsRegistry.reset()
    app = await _make_load_app(rate_limit=100, rate_limit_window=60)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert "x-ratelimit-limit" in resp.headers
        assert "x-ratelimit-remaining" in resp.headers
        assert resp.headers["x-ratelimit-limit"] == "100"

    await app.state.engine.dispose()


# ── Sustained throughput ───────────────────────────────────────


@pytest.mark.load
async def test_sustained_throughput():
    """Run 5 bursts of 20 concurrent requests, verify consistent performance."""
    MetricsRegistry.reset()
    app = await _make_load_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]

    burst_p50s: list[float] = []

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for burst_num in range(5):
            latencies, codes = await _run_concurrent(client, "GET", "/api/health", 20)
            error_count = sum(1 for c in codes if c >= 500)
            assert error_count == 0, f"Burst {burst_num}: {error_count} errors"

            p50 = statistics.median(latencies)
            burst_p50s.append(p50)
            _report_latencies(f"Burst {burst_num + 1}/5", latencies)

    # Verify no significant degradation across bursts
    # Last burst p50 should not be more than 5x the first burst p50
    if burst_p50s[0] > 0:
        degradation = burst_p50s[-1] / burst_p50s[0]
        print(f"\n  Degradation ratio (last/first): {degradation:.2f}x")
        assert degradation < 5.0, (
            f"Performance degradation: {degradation:.2f}x "
            f"(first p50={burst_p50s[0]:.1f}ms, last p50={burst_p50s[-1]:.1f}ms)"
        )

    await app.state.engine.dispose()
