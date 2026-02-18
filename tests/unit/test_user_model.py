"""Tests for User model and user_id foreign keys."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.exc import IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from duh.memory.models import APIKey, Decision, Thread, Turn, User


def _make_user(
    email: str = "alice@example.com",
    password_hash: str = "hashed_pw_placeholder",
    display_name: str = "Alice",
    **kwargs: object,
) -> User:
    return User(
        email=email,
        password_hash=password_hash,
        display_name=display_name,
        **kwargs,
    )


def _make_thread(question: str = "What is AI?", **kwargs: object) -> Thread:
    return Thread(question=question, **kwargs)


def _make_turn(thread: Thread, round_number: int = 1, state: str = "propose") -> Turn:
    return Turn(thread=thread, round_number=round_number, state=state)


# ── User Creation ────────────────────────────────────────────────


class TestUserCreation:
    async def test_user_creation(self, db_session: AsyncSession) -> None:
        user = _make_user()
        db_session.add(user)
        await db_session.commit()

        assert user.id is not None
        assert len(user.id) == 36
        assert user.email == "alice@example.com"
        assert user.password_hash == "hashed_pw_placeholder"
        assert user.display_name == "Alice"
        assert user.created_at is not None
        assert user.updated_at is not None

    async def test_user_defaults(self, db_session: AsyncSession) -> None:
        user = _make_user()
        db_session.add(user)
        await db_session.commit()

        assert user.role == "contributor"
        assert user.is_active is True

    async def test_user_email_unique(self, db_session: AsyncSession) -> None:
        user1 = _make_user(email="dup@example.com")
        db_session.add(user1)
        await db_session.commit()

        user2 = _make_user(email="dup@example.com", display_name="Bob")
        db_session.add(user2)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ── Relationships ────────────────────────────────────────────────


class TestUserRelationships:
    async def test_thread_user_relationship(self, db_session: AsyncSession) -> None:
        user = _make_user()
        thread = _make_thread(user=user)
        db_session.add(thread)
        await db_session.commit()

        assert thread.user_id == user.id
        assert thread.user is user
        assert thread in user.threads

    async def test_decision_user_id(self, db_session: AsyncSession) -> None:
        user = _make_user()
        db_session.add(user)
        await db_session.flush()

        thread = _make_thread()
        turn = _make_turn(thread)
        decision = Decision(
            turn=turn,
            thread=thread,
            content="Answer",
            confidence=0.8,
            user_id=user.id,
        )
        db_session.add(decision)
        await db_session.commit()

        assert decision.user_id == user.id

    async def test_api_key_user_id(self, db_session: AsyncSession) -> None:
        user = _make_user()
        db_session.add(user)
        await db_session.flush()

        key_hash = hashlib.sha256(b"test-key").hexdigest()
        api_key = APIKey(
            key_hash=key_hash,
            name="test-key",
            user_id=user.id,
        )
        db_session.add(api_key)
        await db_session.commit()

        assert api_key.user_id == user.id


# ── Backward Compatibility ───────────────────────────────────────


class TestNullableUserId:
    async def test_thread_without_user(self, db_session: AsyncSession) -> None:
        thread = _make_thread()
        db_session.add(thread)
        await db_session.commit()

        assert thread.user_id is None
        assert thread.user is None

    async def test_decision_without_user(self, db_session: AsyncSession) -> None:
        thread = _make_thread()
        turn = _make_turn(thread)
        decision = Decision(turn=turn, thread=thread, content="Answer", confidence=0.8)
        db_session.add(decision)
        await db_session.commit()

        assert decision.user_id is None

    async def test_api_key_without_user(self, db_session: AsyncSession) -> None:
        key_hash = hashlib.sha256(b"orphan-key").hexdigest()
        api_key = APIKey(key_hash=key_hash, name="orphan")
        db_session.add(api_key)
        await db_session.commit()

        assert api_key.user_id is None
