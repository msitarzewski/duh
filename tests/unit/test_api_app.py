"""Tests for FastAPI application factory."""

from __future__ import annotations

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
