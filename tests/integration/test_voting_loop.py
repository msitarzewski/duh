"""Integration test: voting protocol with persistence.

ask --protocol voting -> run_voting -> verify votes persisted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from duh.consensus.voting import VotingAggregation, run_voting
from duh.memory.repository import MemoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ──────────────────────────────────────────────────────


async def _setup_pm(provider: Any) -> Any:
    from duh.providers.manager import ProviderManager

    pm = ProviderManager()
    await pm.register(provider)
    return pm


# ── Tests ────────────────────────────────────────────────────────


class TestVotingFlow:
    """Voting protocol: fan-out -> aggregate -> persist."""

    async def test_majority_aggregation(self) -> None:
        """Multiple models vote, majority aggregation selects best."""
        from tests.fixtures.providers import MockProvider

        responses = {
            "model-a": "PostgreSQL is the best choice for reliability.",
            "model-b": "SQLite is simpler and sufficient for this use case.",
            "model-c": "PostgreSQL for scale, SQLite for simplicity.",
        }
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        result = await run_voting(
            "What database should I use?", pm, aggregation="majority"
        )

        assert isinstance(result, VotingAggregation)
        assert len(result.votes) == 3
        assert result.decision
        assert result.strategy == "majority"
        assert result.confidence > 0

    async def test_weighted_aggregation(self) -> None:
        """Weighted aggregation synthesizes by capability weight."""
        from tests.fixtures.providers import MockProvider

        responses = {
            "model-a": "Use Kubernetes for orchestration.",
            "model-b": "Docker Compose is sufficient for small teams.",
        }
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        result = await run_voting(
            "How should I deploy my service?", pm, aggregation="weighted"
        )

        assert isinstance(result, VotingAggregation)
        assert len(result.votes) == 2
        assert result.decision
        assert result.strategy == "weighted"
        assert result.confidence > 0

    async def test_single_model_no_aggregation(self) -> None:
        """With one model, voting returns its answer directly."""
        from tests.fixtures.providers import MockProvider

        responses = {"solo": "The only answer."}
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        result = await run_voting("Question?", pm)

        assert len(result.votes) == 1
        assert result.decision == "The only answer."
        assert result.confidence == 1.0

    async def test_votes_persisted_to_db(self, db_session: AsyncSession) -> None:
        """Votes from the voting protocol persist correctly to DB."""
        from tests.fixtures.providers import MockProvider

        responses = {
            "voter-a": "Answer from voter A.",
            "voter-b": "Answer from voter B.",
        }
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        result = await run_voting("Best framework?", pm, aggregation="majority")

        # Persist to DB (same pattern as CLI)
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread("Best framework?")
        thread.status = "complete"

        for vote in result.votes:
            await repo.save_vote(thread.id, vote.model_ref, vote.content)

        # Save aggregated decision
        if result.decision:
            turn = await repo.create_turn(thread.id, 1, "COMMIT")
            await repo.save_decision(
                turn.id,
                thread.id,
                result.decision,
                result.confidence,
            )
        await db_session.commit()

        # Verify votes
        saved_votes = await repo.get_votes(thread.id)
        assert len(saved_votes) == 2
        vote_refs = {v.model_ref for v in saved_votes}
        assert vote_refs == {"mock:voter-a", "mock:voter-b"}

        # Verify decision
        decisions = await repo.get_decisions(thread.id)
        assert len(decisions) == 1
        assert decisions[0].confidence == result.confidence

    async def test_no_models_returns_empty(self) -> None:
        """Voting with no models returns empty aggregation."""
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()

        result = await run_voting("Question?", pm)

        assert len(result.votes) == 0
        assert result.decision == ""
        assert result.confidence == 0.0

    async def test_cost_tracked_across_votes(self) -> None:
        """Cost accumulates from all voter calls + aggregation."""
        from tests.fixtures.providers import MockProvider

        responses = {
            "model-a": "Answer A.",
            "model-b": "Answer B.",
        }
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=3.0,
            output_cost=15.0,
        )
        pm = await _setup_pm(provider)

        assert pm.total_cost == 0.0

        await run_voting("What is best?", pm)

        # Should have cost from 2 votes + 1 aggregation
        assert pm.total_cost > 0.0
