"""Tests for summary generator: model selection, prompts, generation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from duh.core.errors import InsufficientModelsError
from duh.memory.summary import (
    build_thread_summary_prompt,
    build_turn_summary_prompt,
    generate_thread_summary,
    generate_turn_summary,
    select_summarizer,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.fixtures.providers import MockProvider


# ── Model selection ──────────────────────────────────────────────


class TestSelectSummarizer:
    async def _make_pm(self, mock_provider: MockProvider) -> Any:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        return pm

    async def test_selects_cheapest_by_input_cost(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._make_pm(mock_provider)
        ref = select_summarizer(pm)
        # All mock models have 0 cost, so any is valid
        models = pm.list_all_models()
        model_refs = [m.model_ref for m in models]
        assert ref in model_refs

    async def test_prefers_cheapest(self, mock_provider: MockProvider) -> None:
        """With varying costs, picks the lowest input cost."""
        from duh.providers.manager import ProviderManager

        # Register two providers with different costs
        from tests.fixtures.providers import MockProvider as MockProv
        from tests.fixtures.responses import MINIMAL

        cheap = MockProv(
            provider_id="cheap",
            responses=MINIMAL,
            input_cost=0.5,
            output_cost=1.0,
        )
        expensive = MockProv(
            provider_id="expensive",
            responses=MINIMAL,
            input_cost=10.0,
            output_cost=50.0,
        )
        pm = ProviderManager()
        await pm.register(cheap)
        await pm.register(expensive)

        ref = select_summarizer(pm)
        assert ref.startswith("cheap:")

    async def test_no_models_raises(self) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        with pytest.raises(InsufficientModelsError):
            select_summarizer(pm)


# ── Turn summary prompt ──────────────────────────────────────────


class TestBuildTurnSummaryPrompt:
    def test_has_system_and_user(self) -> None:
        msgs = build_turn_summary_prompt(
            "Q?", "proposal", ["challenge"], "revision", "decision"
        )
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"

    def test_system_has_summarizer_instructions(self) -> None:
        msgs = build_turn_summary_prompt(
            "Q?", "proposal", ["challenge"], "revision", "decision"
        )
        assert "concise summarizer" in msgs[0].content

    def test_user_includes_all_parts(self) -> None:
        msgs = build_turn_summary_prompt(
            "What DB?",
            "Use PostgreSQL",
            ["Too complex", "Try SQLite"],
            "Use SQLite instead",
            "SQLite for v0.1",
        )
        user = msgs[1].content
        assert "What DB?" in user
        assert "Use PostgreSQL" in user
        assert "Too complex" in user
        assert "Try SQLite" in user
        assert "Use SQLite instead" in user
        assert "SQLite for v0.1" in user


# ── Thread summary prompt ────────────────────────────────────────


class TestBuildThreadSummaryPrompt:
    def test_has_system_and_user(self) -> None:
        msgs = build_thread_summary_prompt("Q?", ["decision 1"])
        assert len(msgs) == 2
        assert msgs[0].role == "system"
        assert msgs[1].role == "user"

    def test_user_includes_question_and_decisions(self) -> None:
        msgs = build_thread_summary_prompt(
            "What framework?",
            ["Use Django", "Switch to FastAPI"],
        )
        user = msgs[1].content
        assert "What framework?" in user
        assert "Use Django" in user
        assert "Switch to FastAPI" in user
        assert "Round 1" in user
        assert "Round 2" in user


# ── Generate turn summary ────────────────────────────────────────


class TestGenerateTurnSummary:
    async def _make_pm(self, mock_provider: MockProvider) -> Any:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        return pm

    async def test_happy_path(self, mock_provider: MockProvider) -> None:
        pm = await self._make_pm(mock_provider)
        response = await generate_turn_summary(
            pm,
            "What DB?",
            "Use PostgreSQL",
            ["Too complex"],
            "Use SQLite",
            "SQLite for v0.1",
            model_ref="mock:reviser",
        )
        assert response.content
        assert response.finish_reason == "stop"

    async def test_records_cost(self, mock_provider: MockProvider) -> None:
        pm = await self._make_pm(mock_provider)
        await generate_turn_summary(
            pm,
            "Q?",
            "P",
            ["C"],
            "R",
            "D",
            model_ref="mock:reviser",
        )
        # Mock models are free
        assert pm.total_cost == 0.0

    async def test_defaults_to_cheapest(self, mock_provider: MockProvider) -> None:
        pm = await self._make_pm(mock_provider)
        response = await generate_turn_summary(pm, "Q?", "P", ["C"], "R", "D")
        assert response.content

    async def test_explicit_model_override(self, mock_provider: MockProvider) -> None:
        pm = await self._make_pm(mock_provider)
        response = await generate_turn_summary(
            pm,
            "Q?",
            "P",
            ["C"],
            "R",
            "D",
            model_ref="mock:proposer",
        )
        # Should use proposer's canned response
        assert "PostgreSQL" in response.content


# ── Generate thread summary ──────────────────────────────────────


class TestGenerateThreadSummary:
    async def _make_pm(self, mock_provider: MockProvider) -> Any:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        return pm

    async def test_happy_path(self, mock_provider: MockProvider) -> None:
        pm = await self._make_pm(mock_provider)
        response = await generate_thread_summary(
            pm,
            "What DB?",
            ["SQLite for v0.1"],
            model_ref="mock:reviser",
        )
        assert response.content
        assert response.finish_reason == "stop"

    async def test_records_cost(self, mock_provider: MockProvider) -> None:
        pm = await self._make_pm(mock_provider)
        await generate_thread_summary(
            pm,
            "Q?",
            ["D"],
            model_ref="mock:reviser",
        )
        assert pm.total_cost == 0.0


# ── Regeneration (upsert) ───────────────────────────────────────


class TestRegeneration:
    async def test_save_twice_replaces(self, db_session: AsyncSession) -> None:
        """Repository upsert ensures regeneration, not append."""
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Q?")
        turn = await repo.create_turn(thread.id, round_number=1, state="commit")

        # First save
        s1 = await repo.save_turn_summary(turn.id, "First summary", "mock:model")
        # Second save (regeneration)
        s2 = await repo.save_turn_summary(turn.id, "Updated summary", "mock:model")
        await db_session.commit()

        # Same record updated, not a new one
        assert s1.id == s2.id
        assert s2.summary == "Updated summary"

        # Verify only one summary exists
        loaded = await repo.get_turn(turn.id)
        assert loaded is not None
        assert loaded.summary is not None
        assert loaded.summary.summary == "Updated summary"


# ── E2E: generate + persist ─────────────────────────────────────


class TestSummaryEndToEnd:
    async def test_generate_and_persist(
        self,
        mock_provider: MockProvider,
        db_session: AsyncSession,
    ) -> None:
        """Generate a summary and persist it via repository."""
        from duh.memory.repository import MemoryRepository
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)

        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("What DB?")
        turn = await repo.create_turn(thread.id, round_number=1, state="commit")

        response = await generate_turn_summary(
            pm,
            "What DB?",
            "Use PostgreSQL",
            ["Too complex"],
            "Use SQLite",
            "SQLite for v0.1",
            model_ref="mock:reviser",
        )

        await repo.save_turn_summary(turn.id, response.content, "mock:reviser")
        await db_session.commit()

        loaded = await repo.get_turn(turn.id)
        assert loaded is not None
        assert loaded.summary is not None
        assert loaded.summary.summary == response.content
