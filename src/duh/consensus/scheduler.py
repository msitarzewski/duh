"""Subtask scheduler -- executes decomposed subtasks respecting dependencies.

Uses ``graphlib.TopologicalSorter`` for dependency ordering and
``asyncio.gather`` for parallel execution of independent subtasks.
Each subtask runs a simplified mini-consensus (PROPOSE -> CHALLENGE ->
REVISE -> COMMIT) using the existing handlers.
"""

from __future__ import annotations

import asyncio
import graphlib
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

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
    from duh.config.schema import DuhConfig
    from duh.consensus.machine import SubtaskSpec
    from duh.providers.manager import ProviderManager


@dataclass
class SubtaskResult:
    """Result from executing a single subtask consensus."""

    label: str
    decision: str
    confidence: float


async def _run_mini_consensus(
    question: str,
    provider_manager: ProviderManager,
    *,
    max_rounds: int = 1,
) -> tuple[str, float]:
    """Run a simplified single-round consensus for one subtask.

    Executes PROPOSE -> CHALLENGE -> REVISE -> COMMIT with the
    existing handlers.

    Args:
        question: The subtask question/description.
        provider_manager: For model calls and cost tracking.
        max_rounds: Maximum consensus rounds (default 1 for subtasks).

    Returns:
        (decision, confidence) tuple.

    Raises:
        ConsensusError: If any handler phase fails.
    """
    ctx = ConsensusContext(
        thread_id=f"subtask-{uuid.uuid4().hex[:8]}",
        question=question,
        max_rounds=max_rounds,
    )
    sm = ConsensusStateMachine(ctx)

    # PROPOSE
    sm.transition(ConsensusState.PROPOSE)
    proposer_ref = select_proposer(provider_manager)
    await handle_propose(ctx, provider_manager, proposer_ref)

    # CHALLENGE
    sm.transition(ConsensusState.CHALLENGE)
    challenger_refs = select_challengers(provider_manager, proposer_ref, count=2)
    await handle_challenge(ctx, provider_manager, challenger_refs)

    # REVISE
    sm.transition(ConsensusState.REVISE)
    await handle_revise(ctx, provider_manager)

    # COMMIT
    sm.transition(ConsensusState.COMMIT)
    await handle_commit(ctx)

    return ctx.decision or "", ctx.confidence


async def _execute_subtask(
    subtask: SubtaskSpec,
    question: str,
    provider_manager: ProviderManager,
    prior_results: dict[str, SubtaskResult],
) -> SubtaskResult:
    """Execute a single subtask with context from dependencies.

    Builds an augmented question that includes the original question,
    the subtask description, and results from dependency subtasks.

    Args:
        subtask: The subtask to execute.
        question: The original top-level question.
        provider_manager: For model calls.
        prior_results: Results from already-completed subtasks.

    Returns:
        SubtaskResult for this subtask.
    """
    # Build context from dependencies
    dep_context_parts: list[str] = []
    for dep_label in subtask.dependencies:
        if dep_label in prior_results:
            dep_result = prior_results[dep_label]
            dep_context_parts.append(f"[{dep_label}]: {dep_result.decision}")

    augmented_question = (
        f"Original question: {question}\n\nYour specific subtask: {subtask.description}"
    )
    if dep_context_parts:
        dep_text = "\n".join(dep_context_parts)
        augmented_question += f"\n\nContext from prior subtasks:\n{dep_text}"

    decision, confidence = await _run_mini_consensus(
        augmented_question, provider_manager
    )

    return SubtaskResult(
        label=subtask.label,
        decision=decision,
        confidence=confidence,
    )


async def schedule_subtasks(
    subtasks: list[SubtaskSpec],
    question: str,
    config: DuhConfig,
    provider_manager: ProviderManager,
) -> list[SubtaskResult]:
    """Schedule and execute subtasks respecting dependency ordering.

    Uses ``graphlib.TopologicalSorter`` to determine execution order.
    Independent subtasks at the same level are executed concurrently
    with ``asyncio.gather`` when ``config.decompose.parallel`` is True.

    Args:
        subtasks: Validated subtask DAG from decomposition.
        question: The original top-level question.
        config: Configuration (for parallel execution setting).
        provider_manager: For model calls and cost tracking.

    Returns:
        List of SubtaskResult in completion order.

    Raises:
        ConsensusError: If any subtask consensus fails.
    """
    if not subtasks:
        msg = "No subtasks to schedule"
        raise ConsensusError(msg)

    # Build dependency graph for TopologicalSorter
    # TopologicalSorter expects {node: set_of_predecessors}
    dep_graph: dict[str, set[str]] = {}
    subtask_map: dict[str, SubtaskSpec] = {}
    for st in subtasks:
        dep_graph[st.label] = set(st.dependencies)
        subtask_map[st.label] = st

    sorter: graphlib.TopologicalSorter[str] = graphlib.TopologicalSorter(dep_graph)
    sorter.prepare()

    results: list[SubtaskResult] = []
    prior_results: dict[str, SubtaskResult] = {}
    parallel = config.decompose.parallel

    while sorter.is_active():
        ready = list(sorter.get_ready())
        if not ready:
            break

        if parallel and len(ready) > 1:
            # Execute independent subtasks concurrently
            coros = [
                _execute_subtask(
                    subtask_map[label],
                    question,
                    provider_manager,
                    prior_results,
                )
                for label in ready
            ]
            batch_results = await asyncio.gather(*coros)
            for result in batch_results:
                results.append(result)
                prior_results[result.label] = result
                sorter.done(result.label)
        else:
            # Execute sequentially
            for label in ready:
                result = await _execute_subtask(
                    subtask_map[label],
                    question,
                    provider_manager,
                    prior_results,
                )
                results.append(result)
                prior_results[result.label] = result
                sorter.done(label)

    return results
