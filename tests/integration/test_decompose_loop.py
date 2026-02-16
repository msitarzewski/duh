"""Integration test: decomposition -> schedule -> synthesize.

ask --decompose -> DECOMPOSE -> schedule_subtasks -> synthesize
-> verify subtasks persisted.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from duh.config.schema import DecomposeConfig, DuhConfig
from duh.consensus.decompose import handle_decompose, validate_subtask_dag
from duh.consensus.machine import (
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
)
from duh.consensus.scheduler import schedule_subtasks
from duh.consensus.synthesis import synthesize
from duh.memory.repository import MemoryRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    defaults: dict[str, object] = {
        "thread_id": "t-decompose",
        "question": "How should I architect a microservice system?",
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


class TestDecomposeFlow:
    """DECOMPOSE -> schedule -> synthesize full flow."""

    async def test_decompose_produces_subtasks(self) -> None:
        """handle_decompose produces valid subtask specs from JSON response."""
        from tests.fixtures.providers import MockProvider

        decompose_json = json.dumps(
            {
                "subtasks": [
                    {
                        "label": "research_patterns",
                        "description": "Research common microservice patterns",
                        "dependencies": [],
                    },
                    {
                        "label": "evaluate_tools",
                        "description": "Evaluate orchestration tools",
                        "dependencies": [],
                    },
                    {
                        "label": "design_system",
                        "description": "Design the overall system architecture",
                        "dependencies": ["research_patterns", "evaluate_tools"],
                    },
                ]
            }
        )
        responses: dict[str, str] = {
            # Cheapest model returns decomposition JSON
            "decomposer": decompose_json,
            # For mini-consensus in schedule phase
            "proposer": "Use event-driven architecture with Kafka.",
            "challenger-1": "Event-driven adds complexity.",
            "challenger-2": "Consider simpler REST-based communication.",
            "reviser": "Start with REST, migrate to events as needed.",
        }
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.DECOMPOSE)

        subtasks = await handle_decompose(ctx, pm, max_subtasks=7)

        assert len(subtasks) == 3
        labels = {s.label for s in subtasks}
        assert labels == {"research_patterns", "evaluate_tools", "design_system"}
        assert ctx.subtasks == subtasks

        # DAG validation should pass
        validate_subtask_dag(subtasks)

    async def test_full_decompose_schedule_synthesize(self) -> None:
        """End-to-end: decompose -> schedule -> synthesize produces a final answer."""
        from tests.fixtures.providers import MockProvider

        decompose_json = json.dumps(
            {
                "subtasks": [
                    {
                        "label": "analyze_requirements",
                        "description": "Analyze the system requirements",
                        "dependencies": [],
                    },
                    {
                        "label": "propose_architecture",
                        "description": "Propose an architecture",
                        "dependencies": ["analyze_requirements"],
                    },
                ]
            }
        )
        responses: dict[str, str] = {
            "decomposer": decompose_json,
            "proposer": "The system needs high availability and scalability.",
            "challenger-1": "Consider the cost implications.",
            "challenger-2": "What about data consistency?",
            "reviser": "Use a balanced approach with eventual consistency.",
        }
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        # DECOMPOSE
        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.DECOMPOSE)
        subtasks = await handle_decompose(ctx, pm)

        # SCHEDULE
        config = DuhConfig(decompose=DecomposeConfig(parallel=True))
        subtask_results = await schedule_subtasks(subtasks, ctx.question, config, pm)

        assert len(subtask_results) == 2
        assert all(r.decision for r in subtask_results)
        assert all(r.confidence > 0 for r in subtask_results)

        # SYNTHESIZE
        synthesis = await synthesize(ctx.question, subtask_results, pm)

        assert synthesis.content
        assert synthesis.confidence > 0
        assert synthesis.strategy == "merge"

    async def test_subtasks_persisted_to_db(self, db_session: AsyncSession) -> None:
        """Subtasks from decomposition are correctly persisted."""
        from tests.fixtures.providers import MockProvider

        decompose_json = json.dumps(
            {
                "subtasks": [
                    {
                        "label": "step_a",
                        "description": "First step",
                        "dependencies": [],
                    },
                    {
                        "label": "step_b",
                        "description": "Second step",
                        "dependencies": ["step_a"],
                    },
                ]
            }
        )
        responses: dict[str, str] = {"decomposer": decompose_json}
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.DECOMPOSE)
        subtasks = await handle_decompose(ctx, pm)

        # Persist to DB (same pattern as CLI)
        repo = MemoryRepository(db_session)
        thread = await repo.create_thread(ctx.question)

        for i, spec in enumerate(subtasks):
            await repo.save_subtask(
                parent_thread_id=thread.id,
                label=spec.label,
                description=spec.description,
                dependencies=json.dumps(spec.dependencies),
                sequence_order=i,
            )
        await db_session.commit()

        # Verify
        saved = await repo.get_subtasks(thread.id)
        assert len(saved) == 2
        assert saved[0].label == "step_a"
        assert saved[0].dependencies == "[]"
        assert saved[1].label == "step_b"
        assert json.loads(saved[1].dependencies) == ["step_a"]
        assert saved[1].sequence_order == 1

    async def test_parallel_independent_subtasks(self) -> None:
        """Independent subtasks execute concurrently when parallel=True."""
        from tests.fixtures.providers import MockProvider

        decompose_json = json.dumps(
            {
                "subtasks": [
                    {
                        "label": "independent_a",
                        "description": "Task A (no deps)",
                        "dependencies": [],
                    },
                    {
                        "label": "independent_b",
                        "description": "Task B (no deps)",
                        "dependencies": [],
                    },
                    {
                        "label": "dependent_c",
                        "description": "Task C (depends on A and B)",
                        "dependencies": ["independent_a", "independent_b"],
                    },
                ]
            }
        )
        responses: dict[str, str] = {
            "decomposer": decompose_json,
            "proposer": "Result for this subtask.",
            "challenger-1": "A concern about the approach.",
            "challenger-2": "An alternative view.",
            "reviser": "Revised result incorporating feedback.",
        }
        provider = MockProvider(
            provider_id="mock",
            responses=responses,
            input_cost=1.0,
            output_cost=5.0,
        )
        pm = await _setup_pm(provider)

        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.DECOMPOSE)
        subtasks = await handle_decompose(ctx, pm)

        config = DuhConfig(decompose=DecomposeConfig(parallel=True))
        results = await schedule_subtasks(subtasks, ctx.question, config, pm)

        assert len(results) == 3
        labels = {r.label for r in results}
        assert labels == {"independent_a", "independent_b", "dependent_c"}
