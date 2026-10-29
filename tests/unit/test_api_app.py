"""Tests for FastAPI application factory."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from duh.api.app import create_app
from duh.config.schema import DuhConfig


class TestCreateApp:
    def test_creates_fastapi_instance(self):
        config = DuhConfig()
        config.database.url = "sqlite+aiosqlite:///:memory:"
        app = create_app(config)
        assert app.title == "duh"

    def test_config_stored_on_state(self):
        config = DuhConfig()
        config.database.url = "sqlite+aiosqlite:///:memory:"
        app = create_app(config)
        assert app.state.config is config

    def test_health_endpoint(self):
        config = DuhConfig()
        config.database.url = "sqlite+aiosqlite:///:memory:"
        app = create_app(config)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestServeCommand:
    def test_serve_command_exists(self):
        from duh.cli.app import cli

        assert "serve" in [cmd.name for cmd in cli.commands.values()]


def test_app_can_exclude_execution_and_diagnostic_routes():
    app = create_app(
        DuhConfig(),
        include_engine_routes=False,
        include_frontend=False,
        include_diagnostics=False,
    )
    paths = {getattr(route, "path", None) for route in app.routes}
    assert "/api/health" in paths
    assert "/api/auth/login" in paths
    assert paths.isdisjoint(
        {
            "/api/ask",
            "/ws/ask",
            "/api/threads",
            "/api/metrics",
            "/api/health/detailed",
            "/{full_path:path}",
        }
    )


@pytest.mark.parametrize("path", ["../secret.txt", "/etc/hosts", "escape.txt"])
async def test_frontend_refuses_files_outside_dist(tmp_path, monkeypatch, path):
    from fastapi import FastAPI, HTTPException

    from duh.api import app as app_module

    dist = tmp_path / "web" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("SPA")
    secret = tmp_path / "web" / "secret.txt"
    secret.write_text("SECRET")
    (dist / "escape.txt").symlink_to(secret)
    monkeypatch.setattr(app_module, "__file__", str(tmp_path / "src/duh/api/app.py"))
    app = FastAPI()
    app_module._mount_frontend(app)
    endpoint = next(r.endpoint for r in app.routes if r.name == "spa_fallback")
    with pytest.raises(HTTPException) as exc:
        await endpoint(path)
    assert exc.value.status_code == 404


def test_frontend_assets_deep_links_and_missing_api(tmp_path, monkeypatch):
    from fastapi import FastAPI

    from duh.api import app as app_module

    dist = tmp_path / "web" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text("SPA")
    (dist / "robots.txt").write_text("ROBOTS")
    monkeypatch.setattr(app_module, "__file__", str(tmp_path / "src/duh/api/app.py"))
    app = FastAPI()
    app_module._mount_frontend(app)
    with TestClient(app) as client:
        assert client.get("/robots.txt").text == "ROBOTS"
        assert client.get("/threads/deep-link").text == "SPA"
        assert client.get("/api/missing").status_code == 404
        assert client.get("/..%2Fsecret.txt").status_code == 404


def test_cors_preflight_does_not_require_authentication():
    config = DuhConfig()
    config.database.url = "sqlite+aiosqlite:///:memory:"
    config.api.cors_origins = ["https://example.com"]
    app = create_app(config, include_frontend=False)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.options(
            "/api/ask",
            headers={
                "origin": "https://example.com",
                "access-control-request-method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "https://example.com"
        response = client.post(
            "/api/ask",
            headers={
                "origin": "https://example.com",
                "authorization": "Bearer garbage",
            },
            json={"question": "test"},
        )
        assert response.status_code == 401
        assert response.headers["access-control-allow-origin"] == "https://example.com"
