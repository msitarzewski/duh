"""SQLAlchemy models for conversation memory.

Layer 1 (Operational): Thread, Turn, Contribution, TurnSummary, ThreadSummary.
Layer 2 (Institutional): Decision.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> str:
    """Generate a UUID4 string for primary keys."""
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    """Current UTC time for timestamps."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for all duh models."""


# ── Users ────────────────────────────────────────────────────────


class User(Base):
    """A registered user."""

    __tablename__ = "users"
    __table_args__ = (Index("ix_users_email", "email", unique=True),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="contributor")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    threads: Mapped[list[Thread]] = relationship(back_populates="user")


# ── Layer 1: Operational ─────────────────────────────────────────


class Thread(Base):
    """A conversation / consensus session."""

    __tablename__ = "threads"
    __table_args__ = (
        Index("ix_threads_status", "status"),
        Index("ix_threads_created_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="active")
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User | None] = relationship(back_populates="threads")
    turns: Mapped[list[Turn]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="Turn.round_number",
    )
    summary: Mapped[ThreadSummary | None] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        uselist=False,
    )
    decisions: Mapped[list[Decision]] = relationship(viewonly=True)


class Turn(Base):
    """One round of consensus (PROPOSE -> CHALLENGE -> REVISE -> COMMIT)."""

    __tablename__ = "turns"
    __table_args__ = (
        Index("ix_turns_thread_round", "thread_id", "round_number", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    round_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )

    thread: Mapped[Thread] = relationship(back_populates="turns")
    contributions: Mapped[list[Contribution]] = relationship(
        back_populates="turn",
        cascade="all, delete-orphan",
    )
    summary: Mapped[TurnSummary | None] = relationship(
        back_populates="turn",
        cascade="all, delete-orphan",
        uselist=False,
    )
    decision: Mapped[Decision | None] = relationship(
        back_populates="turn",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Contribution(Base):
    """A single model's output within a turn."""

    __tablename__ = "contributions"
    __table_args__ = (Index("ix_contributions_turn_role", "turn_id", "role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id"), index=True)
    model_ref: Mapped[str] = mapped_column(String(100), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    turn: Mapped[Turn] = relationship(back_populates="contributions")


class TurnSummary(Base):
    """LLM-generated summary of a single turn."""

    __tablename__ = "turn_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    model_ref: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    turn: Mapped[Turn] = relationship(back_populates="summary")


class ThreadSummary(Base):
    """LLM-generated summary of an entire thread."""

    __tablename__ = "thread_summaries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), unique=True)
    summary: Mapped[str] = mapped_column(Text)
    model_ref: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    thread: Mapped[Thread] = relationship(back_populates="summary")


# ── Layer 2: Institutional ───────────────────────────────────────


class Decision(Base):
    """Committed decision from a consensus turn."""

    __tablename__ = "decisions"
    __table_args__ = (
        Index("ix_decisions_thread_created", "thread_id", "created_at"),
        Index("ix_decisions_category_genus", "category", "genus"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id"), unique=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True, default=None
    )
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    dissent: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, default=None
    )
    genus: Mapped[str | None] = mapped_column(String(50), nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    turn: Mapped[Turn] = relationship(back_populates="decision")
    thread: Mapped[Thread] = relationship()
    outcome: Mapped[Outcome | None] = relationship(
        back_populates="decision",
        uselist=False,
    )


class Outcome(Base):
    """Tracked outcome of a decision."""

    __tablename__ = "outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    decision_id: Mapped[str] = mapped_column(ForeignKey("decisions.id"), unique=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    result: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    decision: Mapped[Decision] = relationship(back_populates="outcome")
    thread: Mapped[Thread] = relationship()


class Subtask(Base):
    """A decomposed subtask linked to a parent thread."""

    __tablename__ = "subtasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    parent_thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    child_thread_id: Mapped[str | None] = mapped_column(
        ForeignKey("threads.id"), nullable=True, default=None
    )
    label: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    dependencies: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(20), default="pending")
    sequence_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

    parent_thread: Mapped[Thread] = relationship(foreign_keys=[parent_thread_id])
    child_thread: Mapped[Thread | None] = relationship(foreign_keys=[child_thread_id])


class Vote(Base):
    """A single model's vote in the voting protocol."""

    __tablename__ = "votes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    model_ref: Mapped[str] = mapped_column(String(100))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    thread: Mapped[Thread] = relationship()


class APIKey(Base):
    """API key for REST API authentication."""

    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, default=None
    )
