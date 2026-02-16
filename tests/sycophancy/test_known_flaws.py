"""Tests pairing known-flaw proposals with expected challenge behaviors.

Verifies that the consensus system correctly identifies sycophancy
when challengers agree with obviously flawed proposals, and correctly
passes genuine challenges that identify real problems.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from duh.consensus.handlers import (
    build_challenge_prompt,
    handle_challenge,
    handle_commit,
    handle_propose,
    handle_revise,
    select_challengers,
    select_proposer,
)
from duh.consensus.machine import (
    ConsensusState,
    ConsensusStateMachine,
)

from .conftest import _challenge_ctx, _make_ctx, setup_pm

if TYPE_CHECKING:
    from tests.fixtures.providers import MockProvider


# ── Genuine challenges to known-flaw proposals ──────────────────


class TestKnownFlawGenuine:
    """Challengers correctly identify flaws in bad proposals."""

    async def test_genuine_challenges_not_sycophantic(
        self, known_flaw_genuine_provider: MockProvider
    ) -> None:
        """KNOWN_FLAW_GENUINE challengers should NOT be flagged."""
        pm = await setup_pm(known_flaw_genuine_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1", "mock:challenger-2"])

        assert all(not c.sycophantic for c in ctx.challenges)

    async def test_genuine_challenges_contain_disagreement(
        self, known_flaw_genuine_provider: MockProvider
    ) -> None:
        """Genuine challenges should contain substantive critique."""
        pm = await setup_pm(known_flaw_genuine_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1"])

        content = ctx.challenges[0].content.lower()
        # Should contain critical language, not praise
        assert any(
            word in content
            for word in ("disagree", "wrong", "flaw", "vulnerability", "risk")
        )

    async def test_full_loop_genuine_high_confidence(
        self, known_flaw_genuine_provider: MockProvider
    ) -> None:
        """Full loop with genuine challenges should yield confidence 1.0."""
        pm = await setup_pm(known_flaw_genuine_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

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

        assert ctx.confidence == 1.0

    async def test_genuine_challenges_produce_dissent(
        self, known_flaw_genuine_provider: MockProvider
    ) -> None:
        """Genuine challenges should be preserved as dissent."""
        pm = await setup_pm(known_flaw_genuine_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(
            ctx, pm, select_challengers(pm, ctx.proposal_model or "")
        )
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        assert ctx.dissent is not None
        assert len(ctx.dissent) > 0


# ── Sycophantic challenges to known-flaw proposals ──────────────


class TestKnownFlawSycophantic:
    """Challengers sycophantically agree with bad proposals."""

    async def test_sycophantic_challenges_flagged(
        self, known_flaw_sycophantic_provider: MockProvider
    ) -> None:
        """KNOWN_FLAW_SYCOPHANTIC challengers should be flagged."""
        pm = await setup_pm(known_flaw_sycophantic_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1", "mock:challenger-2"])

        assert all(c.sycophantic for c in ctx.challenges)

    async def test_sycophantic_challenges_contain_praise(
        self, known_flaw_sycophantic_provider: MockProvider
    ) -> None:
        """Sycophantic responses contain praise language."""
        pm = await setup_pm(known_flaw_sycophantic_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1"])

        content = ctx.challenges[0].content.lower()
        assert any(
            phrase in content for phrase in ("good answer", "well-reasoned", "agree")
        )

    async def test_full_loop_sycophantic_low_confidence(
        self, known_flaw_sycophantic_provider: MockProvider
    ) -> None:
        """Full loop with sycophantic challenges yields confidence 0.5."""
        pm = await setup_pm(known_flaw_sycophantic_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

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

        assert ctx.confidence == 0.5

    async def test_sycophantic_produces_no_dissent(
        self, known_flaw_sycophantic_provider: MockProvider
    ) -> None:
        """All-sycophantic challenges produce no dissent."""
        pm = await setup_pm(known_flaw_sycophantic_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(
            ctx, pm, select_challengers(pm, ctx.proposal_model or "")
        )
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        assert ctx.dissent is None

    async def test_sycophancy_to_bad_proposal_is_dangerous(
        self, known_flaw_sycophantic_provider: MockProvider
    ) -> None:
        """When challengers agree with a bad proposal, the revision
        inherits the flaw - demonstrating why sycophancy detection matters."""
        pm = await setup_pm(known_flaw_sycophantic_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(
            ctx, pm, select_challengers(pm, ctx.proposal_model or "")
        )
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        # The revision doesn't fix the flaw (MD5 for passwords)
        assert ctx.decision is not None
        assert "md5" in ctx.decision.lower()
        # Low confidence signals the result is untested
        assert ctx.confidence == 0.5


# ── Mixed scenario ──────────────────────────────────────────────


class TestKnownFlawMixed:
    """One genuine challenger, one sycophantic."""

    async def test_mixed_detection(
        self, known_flaw_mixed_provider: MockProvider
    ) -> None:
        """One sycophantic, one genuine challenger correctly identified."""
        pm = await setup_pm(known_flaw_mixed_provider)
        ctx = _challenge_ctx()

        await handle_challenge(ctx, pm, ["mock:challenger-1", "mock:challenger-2"])

        sycophantic_count = sum(1 for c in ctx.challenges if c.sycophantic)
        genuine_count = sum(1 for c in ctx.challenges if not c.sycophantic)
        assert sycophantic_count == 1
        assert genuine_count == 1

    async def test_mixed_intermediate_confidence(
        self, known_flaw_mixed_provider: MockProvider
    ) -> None:
        """Mixed challenges yield intermediate confidence (0.75)."""
        pm = await setup_pm(known_flaw_mixed_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

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

        # 1 genuine out of 2 → 0.5 + (1/2)*0.5 = 0.75
        assert ctx.confidence == 0.75

    async def test_mixed_dissent_only_from_genuine(
        self, known_flaw_mixed_provider: MockProvider
    ) -> None:
        """Dissent should only include the genuine challenge."""
        pm = await setup_pm(known_flaw_mixed_provider)
        ctx = _make_ctx(max_rounds=1)
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(
            ctx, pm, select_challengers(pm, ctx.proposal_model or "")
        )
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        assert ctx.dissent is not None
        # Dissent should contain the genuine challenge content
        assert "critical gap" in ctx.dissent.lower()
        # Dissent should NOT contain the sycophantic praise
        assert "excellent analysis" not in ctx.dissent.lower()


# ── Challenge prompt anti-sycophancy structure ──────────────────


class TestPromptAntiSycophancy:
    """Verify the challenge prompt includes anti-sycophancy instructions."""

    def test_prompt_forces_disagreement(self) -> None:
        """Each framing MUST require identification of specific issues."""
        ctx = _challenge_ctx()
        for framing in ("flaw", "alternative", "risk", "devils_advocate"):
            messages = build_challenge_prompt(ctx, framing=framing)
            system = messages[0].content
            assert "MUST" in system, f"{framing} missing MUST instruction"

    def test_prompt_forbids_praise(self) -> None:
        ctx = _challenge_ctx()
        for framing in ("flaw", "alternative", "risk", "devils_advocate"):
            messages = build_challenge_prompt(ctx, framing=framing)
            system = messages[0].content
            assert "DO NOT start with praise" in system

    def test_prompt_suggests_disagreement_openers(self) -> None:
        """Devils advocate framing should suggest 'I disagree'."""
        ctx = _challenge_ctx()
        messages = build_challenge_prompt(ctx, framing="devils_advocate")
        system = messages[0].content
        assert "I disagree" in system

    def test_prompt_warns_against_deference(self) -> None:
        ctx = _challenge_ctx()
        messages = build_challenge_prompt(ctx)
        user = messages[1].content
        assert "challenge it" in user

    def test_prompt_requires_specific_problems(self) -> None:
        """Flaw framing should require finding factual/logical errors."""
        ctx = _challenge_ctx()
        messages = build_challenge_prompt(ctx, framing="flaw")
        system = messages[0].content
        assert "factual" in system.lower() or "logical" in system.lower()
