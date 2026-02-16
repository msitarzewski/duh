"""Tests for context builder: token estimation, assembly, budget."""

from __future__ import annotations

from typing import TYPE_CHECKING

from duh.memory.context import build_context, estimate_tokens

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Fake models for pure-function tests ──────────────────────────


class _FakeSummary:
    def __init__(self, summary: str) -> None:
        self.summary = summary


class _FakeThread:
    def __init__(self, summary: str | None = None) -> None:
        self.summary = _FakeSummary(summary) if summary else None


class _FakeDecision:
    def __init__(
        self,
        content: str,
        confidence: float = 1.0,
        dissent: str | None = None,
    ) -> None:
        self.content = content
        self.confidence = confidence
        self.dissent = dissent


# ── Token estimation ─────────────────────────────────────────────


class TestEstimateTokens:
    def test_empty_string(self) -> None:
        assert estimate_tokens("") == 0

    def test_short_string(self) -> None:
        # "hello" = 5 chars → 5 // 4 = 1
        assert estimate_tokens("hello") == 1

    def test_longer_string(self) -> None:
        # 40 chars → 40 // 4 = 10
        text = "a" * 40
        assert estimate_tokens(text) == 10

    def test_minimum_one_token(self) -> None:
        # 1 char → max(1, 0) = 1
        assert estimate_tokens("x") == 1


# ── build_context ────────────────────────────────────────────────


class TestBuildContext:
    def test_empty_inputs(self) -> None:
        result = build_context(None, [])  # type: ignore[arg-type]
        assert result == ""

    def test_thread_with_no_summary(self) -> None:
        thread = _FakeThread(summary=None)
        result = build_context(thread, [])  # type: ignore[arg-type]
        assert result == ""

    def test_thread_summary_included(self) -> None:
        thread = _FakeThread(summary="We discussed database options.")
        result = build_context(thread, [])  # type: ignore[arg-type]
        assert "Previous conversation summary:" in result
        assert "We discussed database options." in result

    def test_decisions_included(self) -> None:
        decisions = [
            _FakeDecision("Use SQLite for v0.1", confidence=0.9),
        ]
        result = build_context(None, decisions)  # type: ignore[arg-type]
        assert "Relevant past decisions:" in result
        assert "Use SQLite for v0.1" in result
        assert "90%" in result

    def test_decision_confidence_formatted(self) -> None:
        decisions = [
            _FakeDecision("Use Redis", confidence=0.75),
        ]
        result = build_context(None, decisions)  # type: ignore[arg-type]
        assert "75% confidence" in result

    def test_decisions_with_dissent(self) -> None:
        decisions = [
            _FakeDecision(
                "Use PostgreSQL",
                confidence=0.8,
                dissent="SQLite would be simpler",
            ),
        ]
        result = build_context(None, decisions)  # type: ignore[arg-type]
        assert "Dissent:" in result
        assert "SQLite would be simpler" in result

    def test_multiple_decisions_ordered(self) -> None:
        decisions = [
            _FakeDecision("First decision", confidence=1.0),
            _FakeDecision("Second decision", confidence=0.5),
        ]
        result = build_context(None, decisions)  # type: ignore[arg-type]
        first_pos = result.index("First decision")
        second_pos = result.index("Second decision")
        assert first_pos < second_pos

    def test_thread_summary_before_decisions(self) -> None:
        thread = _FakeThread(summary="Prior discussion of databases.")
        decisions = [
            _FakeDecision("Use SQLite", confidence=1.0),
        ]
        result = build_context(thread, decisions)  # type: ignore[arg-type]
        summary_pos = result.index("Previous conversation summary:")
        decisions_pos = result.index("Relevant past decisions:")
        assert summary_pos < decisions_pos


# ── Token budget ─────────────────────────────────────────────────


class TestTokenBudget:
    def test_budget_truncates_decisions(self) -> None:
        """With a tiny budget, not all decisions fit."""
        decisions = [
            _FakeDecision("Short", confidence=1.0),
            _FakeDecision("x" * 1000, confidence=0.5),
        ]
        # Very small budget: only first decision should fit
        result = build_context(
            None,
            decisions,
            max_tokens=30,  # type: ignore[arg-type]
        )
        assert "Short" in result
        assert "x" * 1000 not in result

    def test_budget_excludes_summary_if_too_large(self) -> None:
        """Summary that exceeds budget is skipped entirely."""
        thread = _FakeThread(summary="x" * 10000)
        result = build_context(
            thread,
            [],
            max_tokens=10,  # type: ignore[arg-type]
        )
        assert result == ""

    def test_generous_budget_includes_everything(self) -> None:
        thread = _FakeThread(summary="Brief summary.")
        decisions = [
            _FakeDecision("Decision A", confidence=1.0),
            _FakeDecision("Decision B", confidence=0.8),
        ]
        result = build_context(
            thread,
            decisions,
            max_tokens=10000,  # type: ignore[arg-type]
        )
        assert "Brief summary." in result
        assert "Decision A" in result
        assert "Decision B" in result


# ── DB integration ───────────────────────────────────────────────


class TestContextBuilderDB:
    async def test_with_real_db_objects(self, db_session: AsyncSession) -> None:
        """Build context from actual ORM objects."""
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(db_session)

        thread = await repo.create_thread("What database to use?")
        turn = await repo.create_turn(thread.id, round_number=1, state="commit")
        await repo.save_decision(
            turn_id=turn.id,
            thread_id=thread.id,
            content="Use SQLite for v0.1",
            confidence=0.9,
            dissent="PostgreSQL has better concurrency",
        )
        await repo.save_thread_summary(
            thread.id,
            summary="Discussed database options for CLI tool.",
            model_ref="mock:summarizer",
        )
        await db_session.commit()

        # Reload thread with eager loading
        loaded = await repo.get_thread(thread.id)
        assert loaded is not None
        decisions = await repo.get_decisions(thread.id)

        result = build_context(loaded, decisions)

        assert "Discussed database options" in result
        assert "Use SQLite for v0.1" in result
        assert "90%" in result
        assert "PostgreSQL has better concurrency" in result
