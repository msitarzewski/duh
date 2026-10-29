"""Subtask scheduler -- executes decomposed subtasks respecting dependencies.

Uses ``graphlib.TopologicalSorter`` for dependency ordering and
``asyncio.gather`` for parallel execution of independent subtasks.
Each subtask runs a simplified mini-consensus (PROPOSE -> CHALLENGE ->
REVISE -> COMMIT) using the existing handlers.
"""

from __future__ import annotations

import graphlib
from dataclasses import dataclass
from typing import TYPE_CHECKING

from duh.core.errors import ConsensusError, ProviderError
from duh.providers.base import gather_provider_calls

if TYPE_CHECKING:
    from duh.cli.display import ConsensusDisplay
    from duh.config.schema import DuhConfig
    from duh.consensus.machine import SubtaskSpec
    from duh.providers.manager import ProviderManager


@dataclass
class SubtaskResult:
    """Result from executing a single subtask consensus."""

    label: str
    decision: str
    confidence: float
    rigor: float = 0.0
    cost: float = 0.0


async def _run_mini_consensus(
    question: str,
    provider_manager: ProviderManager,
    *,
    max_rounds: int = 1,
    display: ConsensusDisplay | None = None,
) -> tuple[str, float, float]:
    """Execute a subtask using the same engine as interactive consumers."""
    from duh.config.schema import DuhConfig
    from duh.consensus.engine import (
        ConsensusEvent,
        EngineOptions,
        PhaseCompleted,
        RoundCommitted,
        run_consensus,
    )

    async def consume(event: ConsensusEvent) -> None:
        if display is None:
            return
        if isinstance(event, PhaseCompleted):
            if event.phase == "PROPOSE":
                display.show_propose(event.model or "", event.content or "")
            elif event.phase == "CHALLENGE":
                display.show_challenges(list(event.challenges))
            elif event.phase == "REVISE":
                display.show_revise(event.model or "", event.content or "")
        elif isinstance(event, RoundCommitted):
            display.show_commit(
                event.round.confidence, event.round.rigor, event.round.dissent
            )

    result = await run_consensus(
        question,
        DuhConfig(),
        provider_manager,
        options=EngineOptions(max_rounds=max_rounds, overview=False, followups=False),
        emit=consume,
    )
    return result.decision, result.confidence, result.rigor


async def _execute_subtask(
    subtask: SubtaskSpec,
    question: str,
    provider_manager: ProviderManager,
    prior_results: dict[str, SubtaskResult],
    *,
    display: ConsensusDisplay | None = None,
) -> SubtaskResult:
    """Execute a single subtask with context from dependencies.

    Builds an augmented question that includes the original question,
    the subtask description, and results from dependency subtasks.

    Args:
        subtask: The subtask to execute.
        question: The original top-level question.
        provider_manager: For model calls.
        prior_results: Results from already-completed subtasks.
        display: Optional display for real-time progress output.

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

    with provider_manager.usage_scope(child=True):
        cost_before = provider_manager.total_cost
        decision, confidence, rigor = await _run_mini_consensus(
            augmented_question, provider_manager, display=display
        )
        subtask_cost = provider_manager.total_cost - cost_before

    return SubtaskResult(
        label=subtask.label,
        decision=decision,
        confidence=confidence,
        rigor=rigor,
        cost=subtask_cost,
    )


async def schedule_subtasks(
    subtasks: list[SubtaskSpec],
    question: str,
    config: DuhConfig,
    provider_manager: ProviderManager,
    *,
    display: ConsensusDisplay | None = None,
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
        display: Optional display for real-time progress output.

    Returns:
        List of SubtaskResult in completion order.

    Raises:
        ConsensusError: If any subtask consensus fails.
    """
    with provider_manager.usage_scope():
        return await _schedule_subtasks_scoped(
            subtasks, question, config, provider_manager, display=display
        )


async def _schedule_subtasks_scoped(
    subtasks: list[SubtaskSpec],
    question: str,
    config: DuhConfig,
    provider_manager: ProviderManager,
    *,
    display: ConsensusDisplay | None = None,
) -> list[SubtaskResult]:

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
    total = len(subtasks)
    completed = 0

    while sorter.is_active():
        ready = list(sorter.get_ready())
        if not ready:
            break

        if parallel and len(ready) > 1:
            # Execute independent subtasks concurrently
            # Display headers for each (display is not used during parallel
            # execution to avoid interleaved output)
            coros = [
                _execute_subtask(
                    subtask_map[label],
                    question,
                    provider_manager,
                    prior_results,
                )
                for label in ready
            ]
            batch_results = await gather_provider_calls(
                coros, recover_provider_errors=False
            )
            for result in batch_results:
                if isinstance(result, ProviderError):
                    raise result
                completed += 1
                if display:
                    display.subtask_footer(result.label, completed, total, result.cost)
                results.append(result)
                prior_results[result.label] = result
                sorter.done(result.label)
        else:
            # Execute sequentially with full display
            for label in ready:
                completed += 1
                subtask = subtask_map[label]
                if display:
                    display.subtask_header(
                        subtask.label,
                        completed,
                        total,
                        subtask.dependencies,
                    )
                result = await _execute_subtask(
                    subtask,
                    question,
                    provider_manager,
                    prior_results,
                    display=display,
                )
                if display:
                    display.subtask_footer(result.label, completed, total, result.cost)
                results.append(result)
                prior_results[result.label] = result
                sorter.done(label)

    return results
