"""Integration test: full flow with taxonomy classification and outcome persistence.

ask -> commit with classify=True -> feedback -> verify taxonomy + outcome persisted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

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
from duh.memory.repository import MemoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    defaults: dict[str, object] = {
        "thread_id": "t-tax",
        "question": "What database should I use for a CLI tool?",
        "max_rounds": 1,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


async def _setup_pm(provider: Any) -> Any:
    from duh.providers.manager import ProviderManager

    pm = ProviderManager()
    await pm.register(provider)
    return pm


# ── Tests ────────────────────────────────────────────────────────


class TestTaxonomyClassificationFlow:
    """Full consensus loop with taxonomy classification + DB persistence."""

    async def test_commit_with_classify_populates_taxonomy(
        self,
    ) -> None:
        """classify=True sets ctx.taxonomy when classification succeeds."""
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        # PROPOSE -> CHALLENGE -> REVISE
        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(ctx, pm, select_challengers(pm, select_proposer(pm)))
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)

        # COMMIT with classify=True, patching the classifier to return valid taxonomy
        taxonomy_result = {
            "intent": "technical",
            "category": "database",
            "genus": "storage",
        }
        sm.transition(ConsensusState.COMMIT)
        with patch(
            "duh.consensus.handlers._classify_decision",
            new_callable=AsyncMock,
            return_value=taxonomy_result,
        ):
            await handle_commit(ctx, pm, classify=True)

        assert ctx.decision is not None
        assert ctx.confidence > 0
        assert ctx.taxonomy is not None
        assert ctx.taxonomy["intent"] == "technical"
        assert ctx.taxonomy["category"] == "database"
        assert ctx.taxonomy["genus"] == "storage"

    async def test_commit_classify_fails_gracefully(self) -> None:
        """classify=True falls back gracefully when classification fails."""
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(ctx, pm, select_challengers(pm, select_proposer(pm)))
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)

        # classify=True but mock returns non-JSON -> classification fails silently
        await handle_commit(ctx, pm, classify=True)

        assert ctx.decision is not None
        # Taxonomy is None because mock doesn't return valid JSON for classify
        assert ctx.taxonomy is None

    async def test_full_flow_persist_taxonomy_and_outcome(
        self, db_session: AsyncSession
    ) -> None:
        """Complete flow: consensus -> save taxonomy -> save outcome -> verify."""
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(
            provider_id="mock",
            responses=CONSENSUS_BASIC,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        # Full round: PROPOSE -> CHALLENGE -> REVISE -> COMMIT(classify)
        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(ctx, pm, select_challengers(pm, select_proposer(pm)))
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)

        taxonomy_result = {
            "intent": "technical",
            "category": "database",
            "genus": "storage-choice",
        }
        sm.transition(ConsensusState.COMMIT)
        with patch(
            "duh.consensus.handlers._classify_decision",
            new_callable=AsyncMock,
            return_value=taxonomy_result,
        ):
            await handle_commit(ctx, pm, classify=True)

        sm.transition(ConsensusState.COMPLETE)

        # Persist to DB
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread(ctx.question)
        turn = await repo.create_turn(thread.id, 1, "COMMIT")

        # Save decision with taxonomy
        taxonomy = ctx.taxonomy or {}
        decision = await repo.save_decision(
            turn.id,
            thread.id,
            ctx.decision or "",
            ctx.confidence,
            dissent=ctx.dissent,
            intent=taxonomy.get("intent"),
            category=taxonomy.get("category"),
            genus=taxonomy.get("genus"),
        )

        # Save outcome (feedback)
        await repo.save_outcome(decision.id, thread.id, "success", notes="Worked well")
        await db_session.commit()

        # Verify taxonomy persisted
        decisions = await repo.get_decisions(thread.id)
        assert len(decisions) == 1
        saved = decisions[0]
        assert saved.intent == "technical"
        assert saved.category == "database"
        assert saved.genus == "storage-choice"

        # Verify outcome persisted
        outcomes = await repo.get_outcomes_for_thread(thread.id)
        assert len(outcomes) == 1
        assert outcomes[0].result == "success"
        assert outcomes[0].notes == "Worked well"

        # Verify get_decisions_with_outcomes works
        dec_with_outcomes = await repo.get_decisions_with_outcomes(thread.id)
        assert len(dec_with_outcomes) == 1
        assert dec_with_outcomes[0].outcome is not None
        assert dec_with_outcomes[0].outcome.result == "success"

    async def test_commit_without_classify_no_taxonomy(self) -> None:
        """classify=False means no taxonomy on context."""
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)

        sm.transition(ConsensusState.PROPOSE)
        await handle_propose(ctx, pm, select_proposer(pm))
        sm.transition(ConsensusState.CHALLENGE)
        await handle_challenge(ctx, pm, select_challengers(pm, select_proposer(pm)))
        sm.transition(ConsensusState.REVISE)
        await handle_revise(ctx, pm)
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)

        assert ctx.decision is not None
        assert ctx.taxonomy is None
