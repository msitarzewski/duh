"""Tests for Alembic migrations."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from duh.memory.models import Base


@pytest.fixture
def alembic_config(tmp_path, monkeypatch):
    """Create an Alembic config pointing to a temp SQLite DB."""
    db_path = tmp_path / "test.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    monkeypatch.setenv("DUH_DATABASE_URL", f"sqlite:///{db_path}")
    return cfg, db_path


class TestMigrations:
    def test_duplicate_legacy_slugs_fail_before_data_changes(
        self, alembic_config
    ) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "005")
        with sqlite3.connect(db_path) as connection:
            connection.execute("ALTER TABLE threads ADD COLUMN slug VARCHAR(200)")
            for thread_id in ("first", "second"):
                connection.execute(
                    "INSERT INTO threads (id,question,status,created_at,updated_at,"
                    "slug) "
                    "VALUES (?, 'preserve','active',CURRENT_TIMESTAMP,"
                    "CURRENT_TIMESTAMP,'duplicate')",
                    (thread_id,),
                )
        connection.close()
        with pytest.raises(RuntimeError, match="duplicate thread slugs"):
            command.upgrade(cfg, "head")
        with sqlite3.connect(db_path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM threads").fetchone() == (2,)
            assert connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone() == ("005",)
            assert "is_public" not in {
                row[1] for row in connection.execute("PRAGMA table_info(threads)")
            }
        connection.close()

    def test_aware_timestamps_round_trip_as_utc(self, alembic_config) -> None:
        from datetime import datetime, timedelta, timezone

        from sqlalchemy.orm import Session

        from duh.memory.models import User

        cfg, db_path = alembic_config
        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        original = datetime(2026, 1, 2, 12, 0, tzinfo=timezone(timedelta(hours=5)))
        try:
            with Session(engine) as session:
                user = User(
                    email="timezone@example.test",
                    display_name="Test",
                    is_guest=True,
                    created_at=original,
                    updated_at=original,
                )
                session.add(user)
                session.commit()
                session.refresh(user)
                assert user.created_at == datetime(2026, 1, 2, 7, 0)
                assert user.updated_at == datetime(2026, 1, 2, 7, 0)
                user.updated_at = original + timedelta(hours=1)
                session.commit()
                session.refresh(user)
                assert user.updated_at == datetime(2026, 1, 2, 8, 0)
        finally:
            engine.dispose()

    def test_head_matches_orm_and_accepts_guest(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.begin() as connection:
                assert (
                    compare_metadata(
                        MigrationContext.configure(connection), Base.metadata
                    )
                    == []
                )
                connection.exec_driver_sql(
                    "INSERT INTO users (id,email,password_hash,display_name,role,"
                    "is_active,is_guest,created_at,updated_at) "
                    "VALUES ('guest','guest@example.test',NULL,'Guest','contributor',"
                    "1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
                )
        finally:
            engine.dispose()

    def test_startup_patched_005_preserves_data_and_converges(
        self, alembic_config
    ) -> None:
        from sqlalchemy.ext.asyncio import create_async_engine

        from duh.memory.migrations import ensure_schema

        cfg, db_path = alembic_config
        command.upgrade(cfg, "005")

        async def patch_legacy():
            engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
            try:
                await ensure_schema(engine)
            finally:
                await engine.dispose()

        asyncio.run(patch_legacy())
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "INSERT INTO users (id,email,password_hash,display_name,role,"
                "is_active,is_guest,created_at,updated_at) "
                "VALUES ('owner','owner@example.test','preserved-test-hash',"
                "'Owner','contributor',1,NULL,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "INSERT INTO api_keys (id,key_hash,name,user_id,created_at) "
                "VALUES ('key','preserved-key-hash','test key','owner',"
                "CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "INSERT INTO threads (id,question,status,created_at,updated_at,"
                "is_public,slug,followups_json,usage_json) "
                "VALUES ('legacy','preserved','active',CURRENT_TIMESTAMP,"
                "CURRENT_TIMESTAMP,1,'legacy-slug','[\"follow-up\"]','{\"cost\":1}')"
            )
            connection.execute(
                "INSERT INTO threads (id,question,status,created_at,updated_at,"
                "is_public) "
                "VALUES ('null-flag','preserved','active',CURRENT_TIMESTAMP,"
                "CURRENT_TIMESTAMP,NULL)"
            )
        connection.close()
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")
        engine = create_engine(f"sqlite:///{db_path}")
        try:
            with engine.connect() as connection:
                assert (
                    compare_metadata(
                        MigrationContext.configure(connection), Base.metadata
                    )
                    == []
                )
                assert connection.exec_driver_sql(
                    "SELECT question,is_public,slug,followups_json,usage_json "
                    "FROM threads WHERE id='legacy'"
                ).one() == (
                    "preserved",
                    1,
                    "legacy-slug",
                    '["follow-up"]',
                    '{"cost":1}',
                )
                assert (
                    connection.exec_driver_sql(
                        "SELECT is_public FROM threads WHERE id='null-flag'"
                    ).scalar_one()
                    == 0
                )
                assert connection.exec_driver_sql(
                    "SELECT password_hash,is_guest FROM users WHERE id='owner'"
                ).one() == ("preserved-test-hash", 0)
                assert connection.exec_driver_sql(
                    "SELECT key_hash,user_id FROM api_keys WHERE id='key'"
                ).one() == ("preserved-key-hash", "owner")
                assert (
                    connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
                )
        finally:
            engine.dispose()

    def test_convergence_round_trip(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "005")
        engine = create_engine(f"sqlite:///{db_path}")
        assert "is_guest" not in {
            column["name"] for column in inspect(engine).get_columns("users")
        }
        engine.dispose()
        command.upgrade(cfg, "head")

    def test_downgrade_refuses_to_destroy_passwordless_users(
        self, alembic_config
    ) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "head")
        with sqlite3.connect(db_path) as connection:
            connection.execute(
                "INSERT INTO users (id,email,password_hash,display_name,role,"
                "is_active,is_guest,created_at,updated_at) "
                "VALUES ('guest','guest@example.test',NULL,'Guest','contributor',"
                "1,1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"
            )
        connection.close()
        with pytest.raises(RuntimeError, match="passwordless users"):
            command.downgrade(cfg, "005")
        with sqlite3.connect(db_path) as connection:
            assert connection.execute(
                "SELECT is_guest FROM users WHERE id='guest'"
            ).fetchone() == (1,)
        connection.close()

    def test_upgrade_to_001(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "001")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "threads" in tables
        assert "turns" in tables
        assert "contributions" in tables
        assert "turn_summaries" in tables
        assert "thread_summaries" in tables
        assert "decisions" in tables

    def test_upgrade_to_002(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "002")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Check new tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        assert "outcomes" in tables
        assert "subtasks" in tables

        # Check taxonomy columns on decisions
        cursor.execute("PRAGMA table_info(decisions)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "intent" in columns
        assert "category" in columns
        assert "genus" in columns

        conn.close()

    def test_downgrade_002_to_001(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "002")
        command.downgrade(cfg, "001")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "outcomes" not in tables
        assert "subtasks" not in tables

    def test_full_downgrade(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "002")
        command.downgrade(cfg, "base")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name != 'alembic_version'"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert len(tables) == 0

    def test_data_survives_migration(self, alembic_config) -> None:
        """Data inserted at v0.1 schema survives v0.2 upgrade."""
        cfg, db_path = alembic_config
        command.upgrade(cfg, "001")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO threads (id, question, status, created_at, "
            "updated_at) VALUES ('t1', 'Test Q', 'active', "
            "'2026-01-01', '2026-01-01')"
        )
        cursor.execute(
            "INSERT INTO turns (id, thread_id, round_number, state, "
            "created_at) VALUES ('r1', 't1', 1, 'complete', '2026-01-01')"
        )
        cursor.execute(
            "INSERT INTO decisions (id, turn_id, thread_id, content, "
            "confidence, created_at) VALUES ('d1', 'r1', 't1', "
            "'Decision text', 0.85, '2026-01-01')"
        )
        conn.commit()
        conn.close()

        # Upgrade to v0.2
        command.upgrade(cfg, "002")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT content, intent FROM decisions WHERE id='d1'")
        row = cursor.fetchone()
        conn.close()

        assert row[0] == "Decision text"
        assert row[1] is None  # New column, nullable

    def test_upgrade_head(self, alembic_config) -> None:
        """Upgrade to head works."""
        cfg, _db_path = alembic_config
        command.upgrade(cfg, "head")

    def test_re_upgrade_idempotent(self, alembic_config) -> None:
        """Running upgrade twice doesn't error."""
        cfg, _db_path = alembic_config
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")  # Should be no-op

    def test_subtasks_table_schema(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "002")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(subtasks)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "label" in columns
        assert "description" in columns
        assert "dependencies" in columns
        assert "status" in columns
        assert "sequence_order" in columns
        assert "parent_thread_id" in columns
        assert "child_thread_id" in columns

    def test_outcomes_table_schema(self, alembic_config) -> None:
        cfg, db_path = alembic_config
        command.upgrade(cfg, "002")

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(outcomes)")
        columns = {row[1]: row[2] for row in cursor.fetchall()}
        conn.close()

        assert "decision_id" in columns
        assert "thread_id" in columns
        assert "result" in columns
        assert "notes" in columns
