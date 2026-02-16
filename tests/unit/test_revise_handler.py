"""Tests for the REVISE handler: prompt building, execution, context update."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from duh.consensus.handlers import build_revise_prompt, handle_revise
from duh.consensus.machine import (
    ChallengeResult,
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
)
from duh.core.errors import ConsensusError

if TYPE_CHECKING:
    from tests.fixtures.providers import MockProvider


# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    defaults: dict[str, object] = {
        "thread_id": "t-1",
        "question": "What is the best database for a CLI tool?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _revise_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context in REVISE state with proposal + challenges set."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.PROPOSE)
    ctx.proposal = "We should use PostgreSQL for everything."
    ctx.proposal_model = "mock:proposer"
    sm.transition(ConsensusState.CHALLENGE)
    ctx.challenges = [
        ChallengeResult("mock:challenger-1", "PostgreSQL adds complexity."),
        ChallengeResult("mock:challenger-2", "SQLite is simpler for CLI."),
    ]
    sm.transition(ConsensusState.REVISE)
    return ctx


# ── Prompt building ──────────────────────────────────────────────


class TestBuildRevisePrompt:
    def test_has_system_and_user(self) -> None:
        ctx = _revise_ctx()
        messages = build_revise_prompt(ctx)
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_system_has_grounding(self) -> None:
        ctx = _revise_ctx()
        messages = build_revise_prompt(ctx)
        assert "Today's date is" in messages[0].content

    def test_system_has_reviser_instructions(self) -> None:
        ctx = _revise_ctx()
        messages = build_revise_prompt(ctx)
        system = messages[0].content
        assert "Addresses each valid challenge" in system
        assert "Pushes back on challenges that are wrong" in system

    def test_user_includes_question(self) -> None:
        ctx = _revise_ctx(question="Why use SQLite?")
        messages = build_revise_prompt(ctx)
        assert "Why use SQLite?" in messages[1].content

    def test_user_includes_proposal(self) -> None:
        ctx = _revise_ctx()
        messages = build_revise_prompt(ctx)
        assert "PostgreSQL for everything" in messages[1].content

    def test_user_includes_all_challenges(self) -> None:
        ctx = _revise_ctx()
        messages = build_revise_prompt(ctx)
        user = messages[1].content
        assert "PostgreSQL adds complexity" in user
        assert "SQLite is simpler" in user

    def test_user_includes_challenge_model_refs(self) -> None:
        ctx = _revise_ctx()
        messages = build_revise_prompt(ctx)
        user = messages[1].content
        assert "mock:challenger-1" in user
        assert "mock:challenger-2" in user

    def test_user_ends_with_instruction(self) -> None:
        ctx = _revise_ctx()
        messages = build_revise_prompt(ctx)
        assert messages[1].content.strip().endswith("improved final answer:")


# ── Handler execution ────────────────────────────────────────────


class TestHandleRevise:
    async def _setup_manager(self, mock_provider: MockProvider) -> Any:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        return pm

    async def test_happy_path(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx()

        await handle_revise(ctx, pm, "mock:reviser")

        assert ctx.revision is not None
        assert "SQLite" in ctx.revision
        assert ctx.revision_model == "mock:reviser"

    async def test_returns_model_response(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx()

        response = await handle_revise(ctx, pm, "mock:reviser")

        assert response.content == ctx.revision
        assert response.finish_reason == "stop"

    async def test_defaults_to_proposer_model(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx()
        ctx.proposal_model = "mock:proposer"

        await handle_revise(ctx, pm)

        assert ctx.revision_model == "mock:proposer"

    async def test_explicit_model_overrides_proposer(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx()
        ctx.proposal_model = "mock:proposer"

        await handle_revise(ctx, pm, "mock:reviser")

        assert ctx.revision_model == "mock:reviser"

    async def test_records_cost(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx()

        await handle_revise(ctx, pm, "mock:reviser")

        assert pm.total_cost == 0.0  # mock = free

    async def test_passes_temperature(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx()

        await handle_revise(ctx, pm, "mock:reviser", temperature=0.5)

        call = mock_provider.call_log[-1]
        assert call["temperature"] == 0.5

    async def test_passes_max_tokens(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx()

        await handle_revise(ctx, pm, "mock:reviser", max_tokens=2048)

        call = mock_provider.call_log[-1]
        assert call["max_tokens"] == 2048

    async def test_sends_correct_prompt(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _revise_ctx(question="Why use SQLite?")

        await handle_revise(ctx, pm, "mock:reviser")

        call = mock_provider.call_log[-1]
        messages = call["messages"]
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert "Why use SQLite?" in messages[1].content
        assert "PostgreSQL adds complexity" in messages[1].content

    async def test_wrong_state_raises(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _make_ctx()  # IDLE state

        with pytest.raises(ConsensusError, match="requires REVISE state"):
            await handle_revise(ctx, pm, "mock:reviser")

    async def test_no_proposal_raises(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _make_ctx()
        ctx.state = ConsensusState.REVISE
        ctx.proposal = None

        with pytest.raises(ConsensusError, match="requires a proposal"):
            await handle_revise(ctx, pm, "mock:reviser")

    async def test_no_challenges_raises(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _make_ctx()
        ctx.state = ConsensusState.REVISE
        ctx.proposal = "Some proposal"
        ctx.challenges = []

        with pytest.raises(ConsensusError, match="requires challenges"):
            await handle_revise(ctx, pm, "mock:reviser")

    async def test_no_model_and_no_proposer_raises(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _make_ctx()
        ctx.state = ConsensusState.REVISE
        ctx.proposal = "Some proposal"
        ctx.proposal_model = None
        ctx.challenges = [ChallengeResult("m", "c")]

        with pytest.raises(ConsensusError, match="requires a model_ref"):
            await handle_revise(ctx, pm)


# ── End-to-end with state machine ────────────────────────────────


class TestReviseEndToEnd:
    async def test_full_revise_flow(self, mock_provider: MockProvider) -> None:
        """PROPOSE -> CHALLENGE -> REVISE -> handle -> ready for COMMIT."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        # PROPOSE
        sm.transition(ConsensusState.PROPOSE)
        ctx.proposal = "Use PostgreSQL"
        ctx.proposal_model = "mock:proposer"

        # CHALLENGE
        sm.transition(ConsensusState.CHALLENGE)
        ctx.challenges = [
            ChallengeResult("mock:challenger-1", "Too complex"),
        ]

        # REVISE
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm, "mock:reviser")

        # Context updated
        assert ctx.revision is not None
        assert ctx.revision_model == "mock:reviser"

        # Can now transition to COMMIT (guard: revision set)
        assert sm.can_transition(ConsensusState.COMMIT)
        sm.transition(ConsensusState.COMMIT)
        assert sm.state == ConsensusState.COMMIT
