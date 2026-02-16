"""Tests for Alembic migrations."""

from __future__ import annotations

import sqlite3

import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture
def alembic_config(tmp_path):
    """Create an Alembic config pointing to a temp SQLite DB."""
    db_path = tmp_path / "test.db"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg, db_path


class TestMigrations:
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
