"""Tests for lightweight Prometheus metrics module."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from duh.api.metrics import (
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset the global metrics registry before each test."""
    MetricsRegistry.reset()
    yield
    MetricsRegistry.reset()


class TestCounter:
    def test_counter_inc(self):
        c = Counter("test_total", "A test counter")
        c.inc()
        c.inc(3.0)
        text = c.collect()
        assert "test_total 4" in text

    def test_counter_labels(self):
        c = Counter("req_total", "Requests", labels=["method", "status"])
        c.inc(method="GET", status="200")
        c.inc(method="GET", status="200")
        c.inc(method="POST", status="201")
        text = c.collect()
        assert "# HELP req_total Requests" in text
        assert "# TYPE req_total counter" in text
        assert 'req_total{method="GET",status="200"} 2' in text
        assert 'req_total{method="POST",status="201"} 1' in text


class TestHistogram:
    def test_histogram_observe(self):
        h = Histogram("dur", "Duration", buckets=[0.1, 0.5, 1.0])
        h.observe(0.05)  # fits in 0.1, 0.5, 1.0
        h.observe(0.3)  # fits in 0.5, 1.0
        h.observe(0.8)  # fits in 1.0
        h.observe(2.0)  # exceeds all buckets

        text = h.collect()
        # Cumulative counts: 0.1→1, 0.5→2, 1.0→3, +Inf→4
        assert 'dur_bucket{le="0.1"} 1' in text
        assert 'dur_bucket{le="0.5"} 2' in text
        assert 'dur_bucket{le="1"} 3' in text
        assert 'dur_bucket{le="+Inf"} 4' in text

    def test_histogram_collect(self):
        h = Histogram("lat", "Latency", buckets=[0.01, 0.1])
        h.observe(0.005)
        h.observe(0.05)
        text = h.collect()
        assert "# HELP lat Latency" in text
        assert "# TYPE lat histogram" in text
        assert 'lat_bucket{le="0.01"} 1' in text
        assert 'lat_bucket{le="0.1"} 2' in text
        assert 'lat_bucket{le="+Inf"} 2' in text
        assert "lat_sum 0.055" in text
        assert "lat_count 2" in text


class TestGauge:
    def test_gauge_set_inc_dec(self):
        g = Gauge("conn", "Connections")
        g.set(5.0)
        text = g.collect()
        assert "conn 5" in text

        g.inc(3.0)
        text = g.collect()
        assert "conn 8" in text

        g.dec(2.0)
        text = g.collect()
        assert "conn 6" in text

        g.inc()
        text = g.collect()
        assert "conn 7" in text

        g.dec()
        text = g.collect()
        assert "conn 6" in text


class TestMetricsRegistry:
    def test_registry_collect_all(self):
        c = Counter("app_total", "App counter")
        g = Gauge("app_gauge", "App gauge")
        c.inc(10.0)
        g.set(42.0)

        registry = MetricsRegistry.get()
        output = registry.collect_all()
        assert "app_total 10" in output
        assert "app_gauge 42" in output
        assert "# HELP app_total" in output
        assert "# HELP app_gauge" in output


class TestMetricsEndpoint:
    def test_metrics_endpoint(self):
        from duh.api.app import create_app
        from duh.config.schema import DuhConfig

        config = DuhConfig()
        config.database.url = "sqlite+aiosqlite:///:memory:"
        app = create_app(config)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        assert "text/plain" in resp.headers["content-type"]

    async def test_metrics_no_auth_required(self):
        """Metrics endpoint is exempt from API key middleware."""
        import hashlib

        from fastapi import FastAPI
        from sqlalchemy import event
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

        from duh.api.metrics import router as metrics_router
        from duh.api.middleware import APIKeyMiddleware
        from duh.memory.models import Base
        from duh.memory.repository import MemoryRepository

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
        app.include_router(metrics_router)

        @app.get("/api/protected")
        async def protected():
            return {"ok": True}

        client = TestClient(app, raise_server_exceptions=False)

        # Without API key, metrics should still be accessible
        resp = client.get("/api/metrics")
        assert resp.status_code == 200

        # A non-exempt API path should fail without a key
        resp2 = client.get("/api/protected")
        assert resp2.status_code == 401
