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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow, onupdate=_utcnow
    )

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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    turn_id: Mapped[str] = mapped_column(ForeignKey("turns.id"), unique=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    dissent: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    turn: Mapped[Turn] = relationship(back_populates="decision")
    thread: Mapped[Thread] = relationship()
