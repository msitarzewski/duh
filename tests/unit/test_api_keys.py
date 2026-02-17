"""Tests for APIKey model and repository methods."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest

from duh.core.errors import StorageError
from duh.memory.models import APIKey
from duh.memory.repository import MemoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


# ── Model ───────────────────────────────────────────────────────


class TestAPIKeyModel:
    async def test_create_instance(self, db_session: AsyncSession):
        key = APIKey(name="test-key", key_hash=_hash("secret"))
        db_session.add(key)
        await db_session.flush()

        assert key.id is not None
        assert len(key.id) == 36
        assert key.name == "test-key"
        assert key.key_hash == _hash("secret")
        assert key.created_at is not None
        assert key.revoked_at is None


# ── create_api_key ──────────────────────────────────────────────


class TestCreateAPIKey:
    async def test_creates_key(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        api_key = await repo.create_api_key("my-key", _hash("k1"))
        await db_session.commit()

        assert api_key.id is not None
        assert len(api_key.id) == 36
        assert api_key.name == "my-key"
        assert api_key.key_hash == _hash("k1")
        assert api_key.created_at is not None
        assert api_key.revoked_at is None


# ── validate_api_key ────────────────────────────────────────────


class TestValidateAPIKey:
    async def test_finds_valid_key(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        created = await repo.create_api_key("valid", _hash("k1"))
        await db_session.commit()

        found = await repo.validate_api_key(_hash("k1"))
        assert found is not None
        assert found.id == created.id

    async def test_returns_none_for_missing(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        assert await repo.validate_api_key(_hash("nonexistent")) is None

    async def test_returns_none_for_revoked(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        created = await repo.create_api_key("to-revoke", _hash("k2"))
        await db_session.commit()

        await repo.revoke_api_key(created.id)
        await db_session.commit()

        assert await repo.validate_api_key(_hash("k2")) is None


# ── revoke_api_key ──────────────────────────────────────────────


class TestRevokeAPIKey:
    async def test_sets_revoked_at(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        created = await repo.create_api_key("rev", _hash("k3"))
        await db_session.commit()

        revoked = await repo.revoke_api_key(created.id)
        await db_session.commit()

        assert revoked.revoked_at is not None

    async def test_raises_for_missing_id(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        with pytest.raises(StorageError, match="not found"):
            await repo.revoke_api_key("no-such-id")


# ── list_api_keys ───────────────────────────────────────────────


class TestListAPIKeys:
    async def test_returns_all_keys(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        await repo.create_api_key("a", _hash("k1"))
        await repo.create_api_key("b", _hash("k2"))
        await db_session.commit()

        keys = await repo.list_api_keys()
        assert len(keys) == 2

    async def test_ordered_by_created_at_desc(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        await repo.create_api_key("first", _hash("k1"))
        await repo.create_api_key("second", _hash("k2"))
        await db_session.commit()

        keys = await repo.list_api_keys()
        assert keys[0].name == "second"
        assert keys[1].name == "first"

    async def test_empty_when_none(self, db_session: AsyncSession):
        repo = MemoryRepository(db_session)
        keys = await repo.list_api_keys()
        assert keys == []
