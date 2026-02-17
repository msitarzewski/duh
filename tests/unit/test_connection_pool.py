"""Tests for connection pooling optimization (T5).

Verifies:
- SQLite in-memory uses StaticPool
- SQLite file uses NullPool
- PostgreSQL uses configured pool settings (pool_size, max_overflow, etc.)
- pool_pre_ping=True enabled for PostgreSQL
- Repository queries use selectinload for eager loading
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from duh.config.schema import DatabaseConfig, DuhConfig


def _mock_engine():
    """Create a mock async engine with proper async context managers."""
    engine = MagicMock()
    conn = AsyncMock()
    conn.run_sync = AsyncMock()
    engine.begin.return_value.__aenter__ = AsyncMock(return_value=conn)
    engine.begin.return_value.__aexit__ = AsyncMock(return_value=False)
    return engine


# ── SQLite Memory: StaticPool ────────────────────────────────


class TestSQLiteMemoryUsesStaticPool:
    @pytest.mark.asyncio
    async def test_sqlite_memory_uses_static_pool(self) -> None:
        """In-memory SQLite must use StaticPool so all queries share one connection."""
        from duh.cli.app import _create_db

        config = DuhConfig(
            database=DatabaseConfig(url="sqlite+aiosqlite:///:memory:")
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
            from sqlalchemy.pool import StaticPool

            assert call_kwargs.get("poolclass") is StaticPool
            assert call_kwargs.get("connect_args") == {"check_same_thread": False}
            # Should NOT have pool_size for sqlite memory
            assert "pool_size" not in call_kwargs
            assert "pool_pre_ping" not in call_kwargs


# ── SQLite File: NullPool ────────────────────────────────────


class TestSQLiteFileUsesNullPool:
    @pytest.mark.asyncio
    async def test_sqlite_file_uses_null_pool(self, tmp_path) -> None:
        """File-based SQLite must use NullPool (no connection pooling)."""
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
            assert "pool_pre_ping" not in call_kwargs


# ── PostgreSQL: Configured Pool ──────────────────────────────


class TestPostgreSQLUsesConfiguredPoolSize:
    @pytest.mark.asyncio
    async def test_postgresql_uses_configured_pool_size(self) -> None:
        """PostgreSQL uses QueuePool with user-configured pool_size and max_overflow."""
        from duh.cli.app import _create_db

        config = DuhConfig(
            database=DatabaseConfig(
                url="postgresql+asyncpg://user:pass@localhost/duh",
                pool_size=20,
                max_overflow=40,
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
            assert call_kwargs["pool_size"] == 20
            assert call_kwargs["max_overflow"] == 40
            assert call_kwargs["pool_timeout"] == 45
            assert call_kwargs["pool_recycle"] == 7200
            # Should NOT have poolclass for postgresql (uses default QueuePool)
            assert "poolclass" not in call_kwargs

    @pytest.mark.asyncio
    async def test_postgresql_default_pool_settings(self) -> None:
        """PostgreSQL with default pool settings."""
        from duh.cli.app import _create_db

        config = DuhConfig(
            database=DatabaseConfig(
                url="postgresql+asyncpg://localhost/duh",
            )
        )

        mock_engine = _mock_engine()
        with patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            return_value=mock_engine,
        ) as mock_create:
            await _create_db(config)

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["pool_size"] == 5  # default
            assert call_kwargs["max_overflow"] == 10  # default
            assert call_kwargs["pool_timeout"] == 30  # default
            assert call_kwargs["pool_recycle"] == 3600  # default


# ── pool_pre_ping for PostgreSQL ─────────────────────────────


class TestPoolPrePingEnabledForPostgreSQL:
    @pytest.mark.asyncio
    async def test_pool_pre_ping_enabled_for_postgresql(self) -> None:
        """PostgreSQL connections must use pool_pre_ping=True."""
        from duh.cli.app import _create_db

        config = DuhConfig(
            database=DatabaseConfig(
                url="postgresql+asyncpg://user:pass@localhost/duh",
            )
        )

        mock_engine = _mock_engine()
        with patch(
            "sqlalchemy.ext.asyncio.create_async_engine",
            return_value=mock_engine,
        ) as mock_create:
            await _create_db(config)

            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs.get("pool_pre_ping") is True

    @pytest.mark.asyncio
    async def test_pool_pre_ping_not_set_for_sqlite(self, tmp_path) -> None:
        """SQLite should NOT set pool_pre_ping (irrelevant for NullPool/StaticPool)."""
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

            call_kwargs = mock_create.call_args.kwargs
            assert "pool_pre_ping" not in call_kwargs


# ── Repository uses selectinload ─────────────────────────────


class TestRepositoryUsesSelectinload:
    @pytest.mark.asyncio
    async def test_get_thread_uses_selectinload(self, db_session) -> None:
        """get_thread eagerly loads turns, contributions, decisions, summaries."""
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("test question")

        # Create a turn with a contribution
        turn = await repo.create_turn(thread.id, 1, "PROPOSE")
        await repo.add_contribution(
            turn.id, "test:model", "proposer", "test content"
        )
        await db_session.commit()

        # Load the thread (should eagerly load turns and contributions)
        loaded = await repo.get_thread(thread.id)
        assert loaded is not None
        assert len(loaded.turns) == 1
        assert len(loaded.turns[0].contributions) == 1
        assert loaded.turns[0].contributions[0].content == "test content"

    @pytest.mark.asyncio
    async def test_get_turn_uses_selectinload(self, db_session) -> None:
        """get_turn eagerly loads contributions, decision, summary."""
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("test question")
        turn = await repo.create_turn(thread.id, 1, "PROPOSE")
        await repo.add_contribution(
            turn.id, "test:model", "proposer", "test content"
        )
        await db_session.commit()

        loaded = await repo.get_turn(turn.id)
        assert loaded is not None
        assert len(loaded.contributions) == 1

    @pytest.mark.asyncio
    async def test_get_decisions_with_outcomes_uses_selectinload(
        self, db_session
    ) -> None:
        """get_decisions_with_outcomes eagerly loads outcome relationship."""
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("test question")
        turn = await repo.create_turn(thread.id, 1, "COMMIT")
        decision = await repo.save_decision(
            turn.id, thread.id, "test decision", 0.9
        )
        await repo.save_outcome(decision.id, thread.id, "success", notes="worked")
        await db_session.commit()

        decisions = await repo.get_decisions_with_outcomes(thread.id)
        assert len(decisions) == 1
        assert decisions[0].outcome is not None
        assert decisions[0].outcome.result == "success"

    @pytest.mark.asyncio
    async def test_get_all_decisions_for_space_uses_selectinload(
        self, db_session
    ) -> None:
        """get_all_decisions_for_space eagerly loads outcome and thread."""
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("test question")
        turn = await repo.create_turn(thread.id, 1, "COMMIT")
        decision = await repo.save_decision(
            turn.id,
            thread.id,
            "test decision",
            0.9,
            category="technical",
            genus="architecture",
        )
        await repo.save_outcome(decision.id, thread.id, "success")
        await db_session.commit()

        decisions = await repo.get_all_decisions_for_space()
        assert len(decisions) == 1
        assert decisions[0].outcome is not None
        assert decisions[0].thread is not None
        assert decisions[0].thread.question == "test question"
