"""Tests for PostgreSQL configuration and async driver support."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from duh.config.schema import DatabaseConfig, DuhConfig

# ─── DatabaseConfig Defaults ─────────────────────────────────


class TestDatabaseConfigDefaults:
    def test_database_config_defaults(self):
        cfg = DatabaseConfig()
        assert cfg.url == "sqlite+aiosqlite:///~/.local/share/duh/duh.db"
        assert cfg.pool_size == 5
        assert cfg.max_overflow == 10
        assert cfg.pool_timeout == 30
        assert cfg.pool_recycle == 3600

    def test_database_config_postgresql_url(self):
        cfg = DatabaseConfig(
            url="postgresql+asyncpg://user:pass@localhost/duh"
        )
        assert cfg.url == "postgresql+asyncpg://user:pass@localhost/duh"
        assert cfg.pool_size == 5
        assert cfg.max_overflow == 10

    def test_database_config_custom_pool(self):
        cfg = DatabaseConfig(
            url="postgresql+asyncpg://localhost/duh",
            pool_size=20,
            max_overflow=40,
            pool_timeout=60,
            pool_recycle=1800,
        )
        assert cfg.pool_size == 20
        assert cfg.max_overflow == 40
        assert cfg.pool_timeout == 60
        assert cfg.pool_recycle == 1800


def _mock_engine():
    """Create a mock async engine with proper async context managers."""
    engine = MagicMock()
    conn = AsyncMock()
    conn.run_sync = AsyncMock()
    engine.begin.return_value.__aenter__ = AsyncMock(return_value=conn)
    engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    return engine


# ─── _create_db Pool Behavior ────────────────────────────────


class TestCreateDbPoolBehavior:
    @pytest.mark.asyncio
    async def test_create_db_sqlite_uses_null_pool(self, tmp_path):
        """Verify NullPool is used for sqlite URLs."""
        from duh.cli.app import _create_db

        config = DuhConfig(
            database=DatabaseConfig(
                url=f"sqlite+aiosqlite:///{tmp_path}/test.db"
            )
        )

        mock_engine = _mock_engine()
        with patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            return_value=mock_engine,
        ) as mock_create, patch(
            "sqlalchemy.event.listens_for",
            return_value=lambda fn: fn,
        ):
            await _create_db(config)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            from sqlalchemy.pool import NullPool

            assert call_kwargs.get("poolclass") is NullPool
            # Should NOT have pool_size for sqlite
            assert "pool_size" not in call_kwargs

    @pytest.mark.asyncio
    async def test_create_db_postgresql_uses_queue_pool(self):
        """Verify pool settings are applied for postgresql URLs."""
        from duh.cli.app import _create_db

        config = DuhConfig(
            database=DatabaseConfig(
                url="postgresql+asyncpg://user:pass@localhost/duh",
                pool_size=15,
                max_overflow=25,
                pool_timeout=45,
                pool_recycle=7200,
            )
        )

        mock_engine = _mock_engine()
        with patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            return_value=mock_engine,
        ) as mock_create:
            await _create_db(config)

            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["pool_size"] == 15
            assert call_kwargs["max_overflow"] == 25
            assert call_kwargs["pool_timeout"] == 45
            assert call_kwargs["pool_recycle"] == 7200
            # Should NOT have poolclass for postgresql
            assert "poolclass" not in call_kwargs


# ─── Alembic Async Driver Detection ─────────────────────────


class TestAlembicAsyncDrivers:
    def test_alembic_env_detects_async_drivers(self):
        """Verify asyncpg is in the async drivers list in alembic/env.py."""
        import ast
        from pathlib import Path

        env_path = Path(__file__).resolve().parents[2] / "alembic" / "env.py"
        source = env_path.read_text()
        tree = ast.parse(source)

        # Find _ASYNC_DRIVERS assignment
        async_drivers = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "_ASYNC_DRIVERS":
                        async_drivers = ast.literal_eval(node.value)

        assert async_drivers is not None, "_ASYNC_DRIVERS not found in alembic/env.py"
        assert "asyncpg" in async_drivers
        assert "aiosqlite" in async_drivers

    def test_is_async_url_logic(self):
        """Verify the _is_async_url logic works for asyncpg URLs."""
        # Replicate the logic from alembic/env.py to test it directly
        async_drivers = {"aiosqlite", "asyncpg", "aiomysql"}

        def _is_async_url(url: str) -> bool:
            return any(f"+{d}" in url for d in async_drivers)

        assert _is_async_url("postgresql+asyncpg://localhost/duh") is True
        assert _is_async_url("sqlite+aiosqlite:///test.db") is True
        assert _is_async_url("postgresql://localhost/duh") is False
        assert _is_async_url("mysql+aiomysql://localhost/duh") is True
