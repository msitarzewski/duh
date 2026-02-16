"""Decomposition handler -- breaks complex questions into subtask DAGs.

Decomposes a question into 2-7 subtasks with dependency relationships,
validates the DAG is acyclic, and populates ``ctx.subtasks``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from duh.consensus.json_extract import JSONExtractionError, extract_json
from duh.consensus.machine import ConsensusState, SubtaskSpec
from duh.core.errors import ConsensusError
from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.consensus.machine import ConsensusContext
    from duh.providers.manager import ProviderManager


# ── Prompt building ──────────────────────────────────────────


def build_decompose_prompt(
    question: str,
    max_subtasks: int = 7,
) -> list[PromptMessage]:
    """Build prompt messages for the DECOMPOSE phase.

    Asks the model to break the question into a DAG of subtasks
    returned as JSON.

    Args:
        question: The user's question to decompose.
        max_subtasks: Maximum number of subtasks allowed.

    Returns:
        Prompt messages requesting JSON subtask decomposition.
    """
    system = (
        "You are an expert at breaking complex questions into smaller, "
        "manageable subtasks. Decompose the given question into a directed "
        "acyclic graph (DAG) of subtasks.\n\n"
        'Return ONLY a JSON object with a single key "subtasks" containing '
        "an array of subtask objects. Each subtask object must have:\n"
        '- "label": a short unique identifier (e.g. "research_options", '
        '"compare_costs")\n'
        '- "description": a clear description of what this subtask should answer\n'
        '- "dependencies": an array of labels this subtask depends on '
        "(empty array if independent)\n\n"
        "Rules:\n"
        f"- Produce between 2 and {max_subtasks} subtasks\n"
        "- Dependencies must reference labels of other subtasks in the list\n"
        "- The DAG must be acyclic (no circular dependencies)\n"
        "- At least one subtask must have no dependencies (a root task)\n"
        "- Labels must be unique\n"
    )

    user = f"Decompose this question into subtasks:\n\n{question}"

    return [
        PromptMessage(role="system", content=system),
        PromptMessage(role="user", content=user),
    ]


# ── DAG validation ───────────────────────────────────────────


def validate_subtask_dag(
    subtasks: list[SubtaskSpec],
    *,
    max_subtasks: int = 7,
) -> None:
    """Validate that a list of subtasks forms a valid DAG.

    Checks:
    1. Count is within bounds (2 to max_subtasks inclusive).
    2. Labels are unique.
    3. All dependency references point to existing labels.
    4. The graph is acyclic (topological sort via set-based Kahn's algorithm).

    Args:
        subtasks: The subtask specifications to validate.
        max_subtasks: Upper bound on subtask count.

    Raises:
        ConsensusError: If the DAG is invalid.
    """
    count = len(subtasks)
    if count < 2:
        msg = f"Too few subtasks: {count} (minimum 2)"
        raise ConsensusError(msg)
    if count > max_subtasks:
        msg = f"Too many subtasks: {count} (maximum {max_subtasks})"
        raise ConsensusError(msg)

    # Unique labels
    labels = [s.label for s in subtasks]
    label_set = set(labels)
    if len(label_set) != len(labels):
        msg = "Duplicate subtask labels"
        raise ConsensusError(msg)

    # All dependencies reference existing labels
    for subtask in subtasks:
        for dep in subtask.dependencies:
            if dep not in label_set:
                msg = f"Subtask '{subtask.label}' depends on unknown label '{dep}'"
                raise ConsensusError(msg)
            if dep == subtask.label:
                msg = f"Subtask '{subtask.label}' has self-dependency"
                raise ConsensusError(msg)

    # Cycle detection via topological sort (Kahn's algorithm)
    in_degree: dict[str, int] = {s.label: 0 for s in subtasks}
    adjacency: dict[str, list[str]] = {s.label: [] for s in subtasks}
    for subtask in subtasks:
        for dep in subtask.dependencies:
            adjacency[dep].append(subtask.label)
            in_degree[subtask.label] += 1

    queue = [label for label, degree in in_degree.items() if degree == 0]
    if not queue:
        msg = "Cycle detected: no root subtasks (all have dependencies)"
        raise ConsensusError(msg)

    visited = 0
    while queue:
        node = queue.pop(0)
        visited += 1
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if visited != count:
        msg = "Cycle detected in subtask dependency graph"
        raise ConsensusError(msg)


# ── JSON parsing ─────────────────────────────────────────────


def _parse_subtasks(data: dict[str, Any]) -> list[SubtaskSpec]:
    """Parse subtask specs from extracted JSON.

    Args:
        data: Parsed JSON dict, expected to have a "subtasks" key.

    Returns:
        List of SubtaskSpec objects.

    Raises:
        ConsensusError: If the JSON structure is invalid.
    """
    raw_subtasks = data.get("subtasks")
    if not isinstance(raw_subtasks, list):
        msg = "Expected 'subtasks' array in JSON response"
        raise ConsensusError(msg)

    result: list[SubtaskSpec] = []
    for i, item in enumerate(raw_subtasks):
        if not isinstance(item, dict):
            msg = f"Subtask {i} is not a JSON object"
            raise ConsensusError(msg)

        label = item.get("label")
        if not isinstance(label, str) or not label.strip():
            msg = f"Subtask {i} missing or invalid 'label'"
            raise ConsensusError(msg)

        description = item.get("description")
        if not isinstance(description, str) or not description.strip():
            msg = f"Subtask {i} missing or invalid 'description'"
            raise ConsensusError(msg)

        deps = item.get("dependencies", [])
        if not isinstance(deps, list):
            msg = f"Subtask {i} 'dependencies' must be an array"
            raise ConsensusError(msg)

        dep_strs: list[str] = []
        for dep in deps:
            if not isinstance(dep, str):
                msg = f"Subtask {i} has non-string dependency"
                raise ConsensusError(msg)
            dep_strs.append(dep)

        result.append(
            SubtaskSpec(
                label=label.strip(),
                description=description.strip(),
                dependencies=dep_strs,
            )
        )

    return result


# ── Handler ──────────────────────────────────────────────────


async def handle_decompose(
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
    *,
    max_subtasks: int = 7,
) -> list[SubtaskSpec]:
    """Execute the DECOMPOSE phase of consensus.

    Calls the cheapest model with JSON mode to decompose the question
    into a subtask DAG, validates the result, and populates
    ``ctx.subtasks``.

    The context must already be in DECOMPOSE state. The caller is
    responsible for transitioning via the state machine before calling
    this handler.

    Args:
        ctx: Consensus context (must be in DECOMPOSE state).
        provider_manager: For model routing and cost tracking.
        max_subtasks: Maximum number of subtasks allowed.

    Returns:
        The list of validated SubtaskSpec objects.

    Raises:
        ConsensusError: If context is not in DECOMPOSE state, or if
            decomposition fails (invalid JSON, invalid DAG, etc.).
    """
    if ctx.state != ConsensusState.DECOMPOSE:
        msg = f"handle_decompose requires DECOMPOSE state, got {ctx.state.value}"
        raise ConsensusError(msg)

    models = provider_manager.list_all_models()
    if not models:
        msg = "No models available for decomposition"
        raise ConsensusError(msg)

    # Use cheapest model for decomposition (utility task)
    cheapest = min(models, key=lambda m: m.input_cost_per_mtok)
    provider, model_id = provider_manager.get_provider(cheapest.model_ref)

    messages = build_decompose_prompt(ctx.question, max_subtasks=max_subtasks)

    try:
        response = await provider.send(
            messages,
            model_id,
            max_tokens=2048,
            temperature=0.3,
            response_format="json",
        )
    except Exception as exc:
        msg = f"Decomposition model call failed: {exc}"
        raise ConsensusError(msg) from exc

    provider_manager.record_usage(cheapest, response.usage)

    # Parse and validate
    try:
        data = extract_json(response.content)
    except JSONExtractionError as exc:
        msg = f"Failed to extract JSON from decomposition response: {exc}"
        raise ConsensusError(msg) from exc

    subtasks = _parse_subtasks(data)
    validate_subtask_dag(subtasks, max_subtasks=max_subtasks)

    ctx.subtasks = subtasks
    return subtasks
