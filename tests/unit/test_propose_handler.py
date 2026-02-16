"""Tests for the PROPOSE handler: prompt building, model selection, execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from duh.consensus.handlers import (
    build_propose_prompt,
    handle_propose,
    select_proposer,
)
from duh.consensus.machine import (
    ChallengeResult,
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
    RoundResult,
)
from duh.core.errors import ConsensusError, InsufficientModelsError
from duh.providers.base import ModelCapability, ModelInfo

if TYPE_CHECKING:
    from tests.fixtures.providers import MockProvider


# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context with sensible defaults."""
    defaults: dict[str, object] = {
        "thread_id": "t-1",
        "question": "What is the best database for a CLI tool?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _propose_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context already in PROPOSE state (round 1)."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.PROPOSE)
    return ctx


def _make_model_info(
    provider_id: str = "mock",
    model_id: str = "strong",
    output_cost: float = 15.0,
) -> ModelInfo:
    return ModelInfo(
        provider_id=provider_id,
        model_id=model_id,
        display_name=f"Mock {model_id}",
        capabilities=ModelCapability.TEXT | ModelCapability.STREAMING,
        context_window=128_000,
        max_output_tokens=4096,
        input_cost_per_mtok=3.0,
        output_cost_per_mtok=output_cost,
    )


# ── Prompt building ──────────────────────────────────────────────


class TestBuildProposePrompt:
    def test_round_1_has_system_and_user(self) -> None:
        ctx = _propose_ctx()
        messages = build_propose_prompt(ctx)
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_round_1_user_is_question(self) -> None:
        ctx = _propose_ctx(question="What is AI?")
        messages = build_propose_prompt(ctx)
        assert messages[1].content == "What is AI?"

    def test_round_1_system_has_grounding(self) -> None:
        ctx = _propose_ctx()
        messages = build_propose_prompt(ctx)
        assert "Today's date is" in messages[0].content

    def test_round_1_system_has_proposer_instructions(self) -> None:
        ctx = _propose_ctx()
        messages = build_propose_prompt(ctx)
        assert "thoughtful expert advisor" in messages[0].content

    def test_round_2_includes_previous_context(self) -> None:
        ctx = _propose_ctx()
        ctx.current_round = 2
        ctx.round_history = [
            RoundResult(
                round_number=1,
                proposal="Initial proposal",
                proposal_model="mock:strong",
                challenges=(
                    ChallengeResult("mock:c1", "Too narrow"),
                    ChallengeResult("mock:c2", "Missing cost analysis"),
                ),
                revision="Revised answer",
                decision="Final decision from round 1",
                confidence=0.7,
            ),
        ]

        messages = build_propose_prompt(ctx)
        user = messages[1].content

        assert "Final decision from round 1" in user
        assert "Too narrow" in user
        assert "Missing cost analysis" in user
        assert "improved answer" in user

    def test_round_2_still_includes_question(self) -> None:
        ctx = _propose_ctx(question="What is AI?")
        ctx.current_round = 2
        ctx.round_history = [
            RoundResult(
                round_number=1,
                proposal="P",
                proposal_model="m",
                challenges=(),
                revision="R",
                decision="D",
                confidence=0.8,
            ),
        ]

        messages = build_propose_prompt(ctx)
        assert "What is AI?" in messages[1].content

    def test_round_1_no_history_fallback(self) -> None:
        ctx = _propose_ctx()
        ctx.current_round = 2  # Round 2 but no history
        messages = build_propose_prompt(ctx)
        # Falls back to simple question since no round_history
        assert messages[1].content == ctx.question


# ── Model selection ──────────────────────────────────────────────


class TestSelectProposer:
    async def test_selects_highest_cost_model(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        pm = ProviderManager()
        # cheap model
        cheap = MockProvider(provider_id="cheap", responses={"small": "response"})
        # expensive model
        expensive = MockProvider(provider_id="expensive", responses={"big": "response"})
        await pm.register(cheap)
        await pm.register(expensive)

        # Override model info to set different costs
        pm._model_index["cheap:small"] = _make_model_info(
            "cheap", "small", output_cost=1.0
        )
        pm._model_index["expensive:big"] = _make_model_info(
            "expensive", "big", output_cost=60.0
        )

        result = select_proposer(pm)
        assert result == "expensive:big"

    async def test_falls_back_to_first_when_all_zero_cost(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        pm = ProviderManager()
        local = MockProvider(provider_id="local", responses={"llama": "response"})
        await pm.register(local)
        # MockProvider models have cost 0.0
        result = select_proposer(pm)
        assert result == "local:llama"

    def test_no_models_raises(self) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        with pytest.raises(InsufficientModelsError, match="No models"):
            select_proposer(pm)


# ── Handler execution ────────────────────────────────────────────


class TestHandlePropose:
    async def _setup_manager(self, mock_provider: MockProvider) -> Any:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        return pm

    async def test_happy_path(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _propose_ctx()

        await handle_propose(ctx, pm, "mock:proposer")

        assert ctx.proposal is not None
        assert "PostgreSQL" in ctx.proposal
        assert ctx.proposal_model == "mock:proposer"

    async def test_returns_model_response(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _propose_ctx()

        response = await handle_propose(ctx, pm, "mock:proposer")

        assert response.content == ctx.proposal
        assert response.finish_reason == "stop"

    async def test_records_cost(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _propose_ctx()

        await handle_propose(ctx, pm, "mock:proposer")

        # MockProvider has 0 cost, but record_usage was called
        assert pm.total_cost == 0.0  # local mock = free

    async def test_passes_temperature(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _propose_ctx()

        await handle_propose(ctx, pm, "mock:proposer", temperature=0.3)

        call = mock_provider.call_log[-1]
        assert call["temperature"] == 0.3

    async def test_passes_max_tokens(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _propose_ctx()

        await handle_propose(ctx, pm, "mock:proposer", max_tokens=2048)

        call = mock_provider.call_log[-1]
        assert call["max_tokens"] == 2048

    async def test_sends_correct_prompt(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _propose_ctx(question="Why use SQLite?")

        await handle_propose(ctx, pm, "mock:proposer")

        call = mock_provider.call_log[-1]
        messages = call["messages"]
        assert messages[0].role == "system"
        assert messages[1].role == "user"
        assert "Why use SQLite?" in messages[1].content

    async def test_wrong_state_raises(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _make_ctx()  # IDLE state

        with pytest.raises(ConsensusError, match="requires PROPOSE state"):
            await handle_propose(ctx, pm, "mock:proposer")

    async def test_wrong_state_challenge_raises(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _propose_ctx()
        ctx.state = ConsensusState.CHALLENGE

        with pytest.raises(ConsensusError, match="requires PROPOSE state"):
            await handle_propose(ctx, pm, "mock:proposer")


# ── End-to-end with state machine ────────────────────────────────


class TestProposeEndToEnd:
    async def test_full_propose_flow(self, mock_provider: MockProvider) -> None:
        """IDLE -> PROPOSE -> handle_propose -> ready for CHALLENGE."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        # Transition to PROPOSE
        sm.transition(ConsensusState.PROPOSE)
        assert ctx.current_round == 1

        # Execute handler
        await handle_propose(ctx, pm, "mock:proposer")

        # Context updated
        assert ctx.proposal is not None
        assert ctx.proposal_model == "mock:proposer"

        # Can now transition to CHALLENGE (guard: proposal set)
        assert sm.can_transition(ConsensusState.CHALLENGE)
        sm.transition(ConsensusState.CHALLENGE)
        assert sm.state == ConsensusState.CHALLENGE
