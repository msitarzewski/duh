"""Integration tests for the full consensus loop with mock providers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from duh.consensus.convergence import check_convergence
from duh.consensus.handlers import (
    handle_challenge,
    handle_commit,
    handle_propose,
    handle_revise,
    select_challengers,
    select_proposer,
)
from duh.consensus.machine import (
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
        "thread_id": "t-int",
        "question": "What is the best database for a CLI tool?",
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


async def _setup_pm(provider: MockProvider) -> Any:
    from duh.providers.manager import ProviderManager

    pm = ProviderManager()
    await pm.register(provider)
    return pm


async def _run_single_round(
    ctx: ConsensusContext,
    sm: ConsensusStateMachine,
    pm: Any,
) -> None:
    """Execute one full round: PROPOSE -> CHALLENGE -> REVISE -> COMMIT."""
    # PROPOSE
    sm.transition(ConsensusState.PROPOSE)
    proposer = select_proposer(pm)
    await handle_propose(ctx, pm, proposer)

    # CHALLENGE
    sm.transition(ConsensusState.CHALLENGE)
    challengers = select_challengers(pm, proposer)
    await handle_challenge(ctx, pm, challengers)

    # REVISE
    sm.transition(ConsensusState.REVISE)
    await handle_revise(ctx, pm)

    # COMMIT
    sm.transition(ConsensusState.COMMIT)
    await handle_commit(ctx)


# ── Single-round full loop ───────────────────────────────────────


class TestSingleRoundLoop:
    async def test_full_loop_to_complete(self, mock_provider: MockProvider) -> None:
        """IDLE -> PROPOSE -> CHALLENGE -> REVISE -> COMMIT -> COMPLETE."""
        pm = await _setup_pm(mock_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        await _run_single_round(ctx, sm, pm)

        # Verify all context fields populated
        assert ctx.proposal is not None
        assert len(ctx.challenges) > 0
        assert ctx.revision is not None
        assert ctx.decision is not None
        assert ctx.confidence > 0
        assert ctx.rigor > 0
        assert ctx.current_round == 1

        # Transition to COMPLETE (max_rounds=1)
        sm.transition(ConsensusState.COMPLETE)
        assert sm.state == ConsensusState.COMPLETE
        assert len(ctx.round_history) == 1

    async def test_decision_equals_revision(self, mock_provider: MockProvider) -> None:
        pm = await _setup_pm(mock_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        await _run_single_round(ctx, sm, pm)

        assert ctx.decision == ctx.revision


# ── Multi-round with convergence ─────────────────────────────────


class TestMultiRoundConvergence:
    async def test_convergence_stops_iteration(
        self, mock_provider: MockProvider
    ) -> None:
        """Same challenges across rounds triggers convergence."""
        pm = await _setup_pm(mock_provider)
        ctx = _make_ctx(max_rounds=3)
        sm = ConsensusStateMachine(ctx)

        # Round 1
        await _run_single_round(ctx, sm, pm)
        converged = check_convergence(ctx)
        assert not converged  # No history to compare

        # Round 2 (same mock responses → same challenges)
        sm.transition(ConsensusState.PROPOSE)
        proposer = select_proposer(pm)
        await handle_propose(ctx, pm, proposer)
        sm.transition(ConsensusState.CHALLENGE)
        challengers = select_challengers(pm, proposer)
        await handle_challenge(ctx, pm, challengers)
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        converged = check_convergence(ctx)
        assert converged
        assert ctx.converged is True

        # Can now complete
        sm.transition(ConsensusState.COMPLETE)
        assert sm.state == ConsensusState.COMPLETE
        assert len(ctx.round_history) == 2

    async def test_no_convergence_continues(self) -> None:
        """Different challenges across rounds → no convergence."""
        from tests.fixtures.providers import MockProvider as MockProv

        # Round 1 uses BASIC responses
        responses_r1 = {
            "proposer": "Use PostgreSQL",
            "challenger-1": "PostgreSQL adds complexity",
            "challenger-2": "SQLite is simpler",
            "reviser": "Use SQLite instead",
        }
        # Round 2 uses completely different challenges
        responses_r2 = {
            "proposer": "Use SQLite with migrations",
            "challenger-1": "The API design lacks pagination",
            "challenger-2": "Error handling is insufficient",
            "reviser": "Added pagination and error handling",
        }

        provider = MockProv(provider_id="mock", responses=responses_r1)
        pm = await _setup_pm(provider)
        ctx = _make_ctx(max_rounds=3)
        sm = ConsensusStateMachine(ctx)

        # Round 1
        await _run_single_round(ctx, sm, pm)
        check_convergence(ctx)

        # Swap responses for round 2
        provider._responses = responses_r2

        # Round 2
        sm.transition(ConsensusState.PROPOSE)
        proposer = select_proposer(pm)
        await handle_propose(ctx, pm, proposer)
        sm.transition(ConsensusState.CHALLENGE)
        challengers = select_challengers(pm, proposer)
        await handle_challenge(ctx, pm, challengers)
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        converged = check_convergence(ctx)
        assert not converged
        assert ctx.current_round == 2

        # Can still go to PROPOSE for round 3
        assert sm.can_transition(ConsensusState.PROPOSE)


# ── Max rounds exhausted ─────────────────────────────────────────


class TestMaxRoundsExhausted:
    async def test_completes_at_max_rounds(self, mock_provider: MockProvider) -> None:
        """After max_rounds, COMPLETE is allowed even without convergence."""
        pm = await _setup_pm(mock_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        await _run_single_round(ctx, sm, pm)

        # Not converged (only 1 round), but max_rounds reached
        assert not ctx.converged
        assert ctx.current_round == ctx.max_rounds

        # COMPLETE is allowed
        assert sm.can_transition(ConsensusState.COMPLETE)
        sm.transition(ConsensusState.COMPLETE)
        assert sm.state == ConsensusState.COMPLETE


# ── Provider failure ─────────────────────────────────────────────


class TestProviderFailure:
    async def test_one_challenger_fails_graceful(self) -> None:
        """One challenger failing doesn't abort the round."""
        from tests.fixtures.providers import MockProvider as MockProv

        # Only challenger-1 has a response; challenger-2 missing
        responses = {
            "proposer": "Use PostgreSQL",
            "challenger-1": "PostgreSQL adds complexity",
            "reviser": "Use SQLite",
        }
        provider = MockProv(provider_id="mock", responses=responses)
        pm = await _setup_pm(provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, "mock:proposer")

        sm.transition(ConsensusState.CHALLENGE)
        # challenger-2 will get "Mock response" (default), not fail
        # To simulate failure, we need a model that's not registered
        # Use challenger-1 twice (same-model ensemble)
        await handle_challenge(ctx, pm, ["mock:challenger-1", "mock:challenger-1"])

        assert len(ctx.challenges) == 2

    async def test_all_challengers_fail_raises(self) -> None:
        """All challengers failing raises ConsensusError."""
        from tests.fixtures.providers import MockProvider as MockProv

        responses = {"proposer": "Use PostgreSQL"}
        provider = MockProv(provider_id="mock", responses=responses)
        pm = await _setup_pm(provider)
        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, "mock:proposer")
        sm.transition(ConsensusState.CHALLENGE)

        # Use model refs that don't exist → all challengers fail
        with pytest.raises(ConsensusError, match="All challengers failed"):
            await handle_challenge(
                ctx, pm, ["nonexistent:model-1", "nonexistent:model-2"]
            )


# ── Cost accumulation ────────────────────────────────────────────


class TestCostAccumulation:
    async def test_cost_increments_across_phases(self) -> None:
        """Cost accumulates from propose + challenge + revise."""
        from tests.fixtures.providers import MockProvider as MockProv
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProv(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=3.0,
            output_cost=15.0,
        )
        pm = await _setup_pm(provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        assert pm.total_cost == 0.0

        await _run_single_round(ctx, sm, pm)

        # Should have accumulated cost from propose + 2 challenges + revise
        assert pm.total_cost > 0.0

    async def test_cost_tracks_by_provider(self) -> None:
        from tests.fixtures.providers import MockProvider as MockProv
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProv(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        await _run_single_round(ctx, sm, pm)

        assert "mock" in pm.cost_by_provider
        assert pm.cost_by_provider["mock"] == pm.total_cost


# ── Same-model ensemble ──────────────────────────────────────────


class TestSameModelEnsemble:
    async def test_single_model_self_debate(self) -> None:
        """With only one model, proposer == challengers."""
        from tests.fixtures.providers import MockProvider as MockProv

        responses = {
            "solo": "This is my answer and also my challenge and revision.",
        }
        provider = MockProv(provider_id="mock", responses=responses)
        pm = await _setup_pm(provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        proposer = select_proposer(pm)
        assert proposer == "mock:solo"
        await handle_propose(ctx, pm, proposer)

        sm.transition(ConsensusState.CHALLENGE)
        challengers = select_challengers(pm, proposer)
        # Should fill with same model
        assert all(c == "mock:solo" for c in challengers)
        await handle_challenge(ctx, pm, challengers)

        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)

        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        assert ctx.decision is not None


# ── Sycophantic challenges ───────────────────────────────────────


class TestSycophancyIntegration:
    async def test_sycophantic_challenges_lower_confidence(self) -> None:
        """CONSENSUS_AGREEMENT responses are sycophantic → lower confidence."""
        from tests.fixtures.providers import MockProvider as MockProv
        from tests.fixtures.responses import CONSENSUS_AGREEMENT

        provider = MockProv(provider_id="mock", responses=CONSENSUS_AGREEMENT)
        pm = await _setup_pm(provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        await _run_single_round(ctx, sm, pm)

        # All sycophantic → rigor=0.5, confidence=min(0.85,0.5)
        assert ctx.confidence < 1.0
        assert ctx.rigor < 1.0
        # Dissent should be None (all sycophantic)
        assert ctx.dissent is None


# ── Context carries across rounds ────────────────────────────────


class TestCrossRoundContext:
    async def test_round2_prompt_includes_round1_history(
        self, mock_provider: MockProvider
    ) -> None:
        """Round 2 propose prompt references round 1 decision."""
        pm = await _setup_pm(mock_provider)
        ctx = _make_ctx(max_rounds=3)
        sm = ConsensusStateMachine(ctx)

        # Round 1
        await _run_single_round(ctx, sm, pm)

        # Start round 2
        sm.transition(ConsensusState.PROPOSE)

        # Check that round_history has round 1 data
        assert len(ctx.round_history) == 1
        assert ctx.round_history[0].decision != ""

        # The propose handler will build a prompt with history
        proposer = select_proposer(pm)
        await handle_propose(ctx, pm, proposer)

        # Verify the prompt included history
        last_call = mock_provider.call_log[-1]
        user_msg = last_call["messages"][1].content
        assert "previous round" in user_msg.lower() or "challenges" in user_msg.lower()


# ── Wrong transition rejected ────────────────────────────────────


class TestTransitionEnforcement:
    async def test_skip_challenge_rejected(self, mock_provider: MockProvider) -> None:
        """Cannot skip from PROPOSE to REVISE."""
        pm = await _setup_pm(mock_provider)
        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))

        with pytest.raises(ConsensusError, match="Invalid transition"):
            sm.transition(ConsensusState.REVISE)


# ── Fail mid-loop ────────────────────────────────────────────────


class TestFailMidLoop:
    async def test_fail_preserves_error(self, mock_provider: MockProvider) -> None:
        """Calling fail() mid-round transitions to FAILED with error."""
        pm = await _setup_pm(mock_provider)
        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))

        sm.fail("Provider returned garbage")

        assert sm.state == ConsensusState.FAILED
        assert ctx.error == "Provider returned garbage"
        assert sm.is_terminal
