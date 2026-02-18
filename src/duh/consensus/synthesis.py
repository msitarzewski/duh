"""Synthesis handler -- combines subtask results into a final answer.

After decomposition and scheduling, this module merges all subtask
results into a coherent final response using the strongest available model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from duh.core.errors import ConsensusError
from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.consensus.scheduler import SubtaskResult
    from duh.providers.manager import ProviderManager


@dataclass
class SynthesisResult:
    """Result of synthesizing subtask results into a final answer."""

    content: str
    confidence: float
    strategy: str
    rigor: float = 0.0


def _build_merge_prompt(
    question: str,
    subtask_results: list[SubtaskResult],
) -> list[PromptMessage]:
    """Build prompt for the merge synthesis strategy.

    Instructs the model to combine all subtask results into a
    comprehensive answer.

    Args:
        question: The original top-level question.
        subtask_results: Results from all subtasks.

    Returns:
        Prompt messages for the synthesis model call.
    """
    parts: list[str] = []
    for r in subtask_results:
        parts.append(f"## {r.label} (confidence: {r.confidence:.2f})\n{r.decision}")
    subtask_text = "\n\n".join(parts)

    system = (
        "You are an expert synthesizer. You are given a question that was "
        "broken into subtasks, each answered independently. Your job is to "
        "combine these subtask answers into a single, coherent, comprehensive "
        "final answer.\n\n"
        "Rules:\n"
        "- Integrate all subtask results into a unified response\n"
        "- Resolve any contradictions between subtask answers\n"
        "- Ensure the final answer directly addresses the original question\n"
        "- Do not mention the decomposition process or subtasks\n"
        "- Produce a clear, well-structured answer"
    )

    user = (
        f"Original question: {question}\n\n"
        f"Subtask results:\n\n{subtask_text}\n\n"
        "Synthesize these into a single comprehensive answer to the "
        "original question."
    )

    return [
        PromptMessage(role="system", content=system),
        PromptMessage(role="user", content=user),
    ]


def _build_prioritize_prompt(
    question: str,
    subtask_results: list[SubtaskResult],
) -> list[PromptMessage]:
    """Build prompt for the prioritize synthesis strategy.

    Instructs the model to weight subtask results by confidence,
    giving more emphasis to higher-confidence answers.

    Args:
        question: The original top-level question.
        subtask_results: Results from all subtasks.

    Returns:
        Prompt messages for the synthesis model call.
    """
    # Sort by confidence descending for emphasis
    sorted_results = sorted(subtask_results, key=lambda r: r.confidence, reverse=True)

    parts: list[str] = []
    for r in sorted_results:
        parts.append(f"## {r.label} (confidence: {r.confidence:.2f})\n{r.decision}")
    subtask_text = "\n\n".join(parts)

    system = (
        "You are an expert synthesizer. You are given a question that was "
        "broken into subtasks, each answered independently with a confidence "
        "score. Your job is to combine these into a final answer, giving MORE "
        "weight to higher-confidence subtask answers.\n\n"
        "Rules:\n"
        "- Higher-confidence subtask results should dominate the final answer\n"
        "- Lower-confidence results should be included but with caveats\n"
        "- If high and low confidence results contradict, prefer the "
        "high-confidence version\n"
        "- Ensure the final answer directly addresses the original question\n"
        "- Do not mention the decomposition process or confidence scores\n"
        "- Produce a clear, well-structured answer"
    )

    user = (
        f"Original question: {question}\n\n"
        f"Subtask results (ordered by confidence, highest first):\n\n"
        f"{subtask_text}\n\n"
        "Synthesize these into a single comprehensive answer, prioritizing "
        "higher-confidence results."
    )

    return [
        PromptMessage(role="system", content=system),
        PromptMessage(role="user", content=user),
    ]


async def synthesize(
    question: str,
    subtask_results: list[SubtaskResult],
    provider_manager: ProviderManager,
    *,
    strategy: str = "merge",
) -> SynthesisResult:
    """Synthesize subtask results into a final answer.

    Uses the strongest available model (highest output cost) to
    produce a coherent answer from all subtask results.

    Args:
        question: The original top-level question.
        subtask_results: Results from all completed subtasks.
        provider_manager: For model routing and cost tracking.
        strategy: Synthesis strategy -- "merge" (equal weight) or
            "prioritize" (weight by confidence).

    Returns:
        SynthesisResult with the final answer, aggregate confidence,
        and the strategy used.

    Raises:
        ConsensusError: If no models available, no subtask results,
            or the model call fails.
    """
    if not subtask_results:
        msg = "No subtask results to synthesize"
        raise ConsensusError(msg)

    models = provider_manager.list_all_models()
    if not models:
        msg = "No models available for synthesis"
        raise ConsensusError(msg)

    # Use strongest model (highest output cost) for synthesis
    strongest = max(models, key=lambda m: m.output_cost_per_mtok)
    provider, model_id = provider_manager.get_provider(strongest.model_ref)

    if strategy == "prioritize":
        messages = _build_prioritize_prompt(question, subtask_results)
    else:
        messages = _build_merge_prompt(question, subtask_results)

    try:
        response = await provider.send(
            messages,
            model_id,
            max_tokens=4096,
            temperature=0.5,
        )
    except Exception as exc:
        msg = f"Synthesis model call failed: {exc}"
        raise ConsensusError(msg) from exc

    provider_manager.record_usage(strongest, response.usage)

    # Aggregate confidence: weighted average of subtask confidences
    total_conf = sum(r.confidence for r in subtask_results)
    avg_confidence = total_conf / len(subtask_results) if subtask_results else 0.0
    avg_rigor = (
        sum(r.rigor for r in subtask_results) / len(subtask_results)
        if subtask_results
        else 0.0
    )

    return SynthesisResult(
        content=response.content,
        confidence=avg_confidence,
        strategy=strategy,
        rigor=avg_rigor,
    )
