"""Tests for the CHALLENGE handler: prompts, selection, sycophancy, execution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from duh.consensus.handlers import (
    build_challenge_prompt,
    detect_sycophancy,
    handle_challenge,
    select_challengers,
)
from duh.consensus.machine import (
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
)
from duh.core.errors import ConsensusError, InsufficientModelsError
from duh.providers.base import ModelCapability, ModelInfo

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


def _challenge_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context in CHALLENGE state with a proposal set."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.PROPOSE)
    ctx.proposal = "We should use PostgreSQL for everything."
    ctx.proposal_model = "mock:proposer"
    sm.transition(ConsensusState.CHALLENGE)
    return ctx


def _make_model_info(
    provider_id: str = "mock",
    model_id: str = "model",
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


class TestBuildChallengePrompt:
    def test_has_system_and_user(self) -> None:
        ctx = _challenge_ctx()
        messages = build_challenge_prompt(ctx)
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_system_has_adversarial_framing(self) -> None:
        ctx = _challenge_ctx()
        messages = build_challenge_prompt(ctx)
        system = messages[0].content
        assert "MUST disagree" in system
        assert "DO NOT start with praise" in system

    def test_system_has_grounding(self) -> None:
        ctx = _challenge_ctx()
        messages = build_challenge_prompt(ctx)
        assert "Today's date is" in messages[0].content

    def test_user_includes_question(self) -> None:
        ctx = _challenge_ctx(question="Why use SQLite?")
        messages = build_challenge_prompt(ctx)
        assert "Why use SQLite?" in messages[1].content

    def test_user_includes_proposal(self) -> None:
        ctx = _challenge_ctx()
        ctx.proposal = "My specific proposal text"
        messages = build_challenge_prompt(ctx)
        assert "My specific proposal text" in messages[1].content

    def test_user_has_challenge_framing(self) -> None:
        ctx = _challenge_ctx()
        messages = build_challenge_prompt(ctx)
        assert "do NOT defer" in messages[1].content


# ── Model selection ──────────────────────────────────────────────


class TestSelectChallengers:
    async def test_prefers_different_models(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        pm = ProviderManager()
        p1 = MockProvider(provider_id="a", responses={"m1": "r"})
        p2 = MockProvider(provider_id="b", responses={"m2": "r"})
        await pm.register(p1)
        await pm.register(p2)

        result = select_challengers(pm, "a:m1", count=1)
        assert result == ["b:m2"]

    async def test_fills_with_proposer_when_needed(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        pm = ProviderManager()
        p1 = MockProvider(provider_id="only", responses={"m1": "r"})
        await pm.register(p1)

        result = select_challengers(pm, "only:m1", count=2)
        assert result == ["only:m1", "only:m1"]

    async def test_sorts_by_cost_descending(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        pm = ProviderManager()
        p1 = MockProvider(provider_id="cheap", responses={"c": "r"})
        p2 = MockProvider(provider_id="mid", responses={"m": "r"})
        p3 = MockProvider(provider_id="exp", responses={"e": "r"})
        await pm.register(p1)
        await pm.register(p2)
        await pm.register(p3)

        pm._model_index["cheap:c"] = _make_model_info("cheap", "c", 1.0)
        pm._model_index["mid:m"] = _make_model_info("mid", "m", 10.0)
        pm._model_index["exp:e"] = _make_model_info("exp", "e", 60.0)

        result = select_challengers(pm, "exp:e", count=2)
        assert result[0] == "mid:m"
        assert result[1] == "cheap:c"

    def test_no_models_raises(self) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        with pytest.raises(InsufficientModelsError, match="No models"):
            select_challengers(pm, "any:model")


# ── Sycophancy detection ─────────────────────────────────────────


class TestDetectSycophancy:
    def test_detects_praise_opener(self) -> None:
        assert detect_sycophancy("Great answer! The proposal is solid.") is True

    def test_detects_agreement(self) -> None:
        assert detect_sycophancy("I largely agree with the proposal.") is True

    def test_detects_no_flaws(self) -> None:
        text = "No significant flaws found in this analysis."
        assert detect_sycophancy(text) is True

    def test_detects_sound_proposal(self) -> None:
        assert detect_sycophancy("The proposal is sound and well-reasoned.") is True

    def test_passes_genuine_challenge(self) -> None:
        text = "I disagree with the choice of PostgreSQL because..."
        assert detect_sycophancy(text) is False

    def test_passes_critical_opener(self) -> None:
        text = "A critical gap is the lack of cost analysis."
        assert detect_sycophancy(text) is False

    def test_case_insensitive(self) -> None:
        assert detect_sycophancy("GREAT ANSWER! Everything looks good.") is True

    def test_only_checks_opening(self) -> None:
        # Praise phrase after 200 chars should not trigger
        text = "I disagree strongly. " + "x" * 200 + " Great answer though."
        assert detect_sycophancy(text) is False


# ── Handler execution ────────────────────────────────────────────


class TestHandleChallenge:
    async def _setup_manager(self, mock_provider: MockProvider) -> Any:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)
        return pm

    async def test_happy_path_two_challengers(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _challenge_ctx()

        responses = await handle_challenge(
            ctx, pm, ["mock:challenger-1", "mock:challenger-2"]
        )

        assert len(responses) == 2
        assert len(ctx.challenges) == 2
        assert ctx.challenges[0].model_ref == "mock:challenger-1"
        assert ctx.challenges[1].model_ref == "mock:challenger-2"

    async def test_challenge_content_from_mock(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1"])

        assert "flaw" in ctx.challenges[0].content.lower()

    async def test_records_cost(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1", "mock:challenger-2"])

        # MockProvider has 0 cost but record_usage was called for each
        assert pm.total_cost == 0.0

    async def test_wrong_state_raises(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _make_ctx()  # IDLE state

        with pytest.raises(ConsensusError, match="requires CHALLENGE state"):
            await handle_challenge(ctx, pm, ["mock:challenger-1"])

    async def test_no_proposal_raises(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _make_ctx()
        ctx.state = ConsensusState.CHALLENGE
        ctx.proposal = None

        with pytest.raises(ConsensusError, match="requires a proposal"):
            await handle_challenge(ctx, pm, ["mock:challenger-1"])

    async def test_one_failure_graceful(self) -> None:
        """If one challenger fails, others still succeed."""
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        # One healthy, one unhealthy
        healthy = MockProvider(
            provider_id="good", responses={"m1": "I disagree because..."}
        )
        pm = ProviderManager()
        await pm.register(healthy)

        ctx = _challenge_ctx()

        # Call with one valid model and one that doesn't exist
        # The non-existent model will raise ModelNotFoundError in gather
        responses = await handle_challenge(ctx, pm, ["good:m1", "good:nonexistent"])

        # Only the successful one should be in results
        assert len(responses) == 1
        assert len(ctx.challenges) == 1
        assert ctx.challenges[0].model_ref == "good:m1"

    async def test_all_failures_raises(self) -> None:
        """If all challengers fail, raises ConsensusError."""
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        pm = ProviderManager()
        p = MockProvider(provider_id="p", responses={"m": "r"})
        await pm.register(p)

        ctx = _challenge_ctx()

        with pytest.raises(ConsensusError, match="All challengers failed"):
            await handle_challenge(ctx, pm, ["p:nonexistent", "p:also-bad"])

    async def test_sycophancy_flagged(self) -> None:
        """Sycophantic responses are flagged on ChallengeResult."""
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_AGREEMENT

        pm = ProviderManager()
        agreeable = MockProvider(provider_id="agree", responses=CONSENSUS_AGREEMENT)
        await pm.register(agreeable)

        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["agree:challenger-1", "agree:challenger-2"])

        # CONSENSUS_AGREEMENT challengers say "No significant flaws" and
        # "The proposal is sound" — both should be flagged
        assert any(c.sycophantic for c in ctx.challenges)

    async def test_genuine_challenge_not_flagged(
        self, mock_provider: MockProvider
    ) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1"])

        # CONSENSUS_BASIC challenger-1 starts with "The flaw in..."
        assert ctx.challenges[0].sycophantic is False

    async def test_passes_temperature(self, mock_provider: MockProvider) -> None:
        pm = await self._setup_manager(mock_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1"], temperature=0.9)

        call = mock_provider.call_log[-1]
        assert call["temperature"] == 0.9


# ── End-to-end with state machine ────────────────────────────────


class TestChallengeEndToEnd:
    async def test_full_challenge_flow(self, mock_provider: MockProvider) -> None:
        """PROPOSE -> CHALLENGE -> handle_challenge -> ready for REVISE."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        await pm.register(mock_provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        # PROPOSE phase
        sm.transition(ConsensusState.PROPOSE)
        ctx.proposal = "Use PostgreSQL"
        ctx.proposal_model = "mock:proposer"

        # CHALLENGE phase
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(ctx, pm, ["mock:challenger-1", "mock:challenger-2"])

        # Context updated
        assert len(ctx.challenges) == 2

        # Can now transition to REVISE (guard: challenges non-empty)
        assert sm.can_transition(ConsensusState.REVISE)
        sm.transition(ConsensusState.REVISE)
        assert sm.state == ConsensusState.REVISE
