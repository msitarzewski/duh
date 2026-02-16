"""Summary generator — turn and thread summaries via fast model.

Generates concise summaries for storage in the memory layer.
Uses the cheapest available model since summaries are
cost-sensitive, not quality-sensitive.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from duh.core.errors import InsufficientModelsError
from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.providers.base import ModelResponse
    from duh.providers.manager import ProviderManager

_SUMMARIZER_SYSTEM = (
    "You are a concise summarizer. Produce a brief summary "
    "(2-4 sentences) capturing the key points, decision, and "
    "any notable dissent. Do not editorialize or add opinions. "
    "Just distill the essential information."
)


def select_summarizer(provider_manager: ProviderManager) -> str:
    """Select the cheapest available model for summarization.

    Uses input cost per million tokens as proxy — summaries
    process a lot of input but produce short output.

    Returns:
        The ``model_ref`` of the cheapest model.

    Raises:
        InsufficientModelsError: If no models are registered.
    """
    models = provider_manager.list_all_models()
    if not models:
        msg = "No models available for summarization"
        raise InsufficientModelsError(msg)
    return min(models, key=lambda m: m.input_cost_per_mtok).model_ref


def build_turn_summary_prompt(
    question: str,
    proposal: str,
    challenges: list[str],
    revision: str,
    decision: str,
) -> list[PromptMessage]:
    """Build prompt for summarizing a single consensus turn."""
    challenges_text = "\n".join(f"- {c}" for c in challenges)
    user_content = (
        f"Question: {question}\n\n"
        f"Proposal: {proposal}\n\n"
        f"Challenges:\n{challenges_text}\n\n"
        f"Revision: {revision}\n\n"
        f"Decision: {decision}\n\n"
        "Summarize this consensus round in 2-4 sentences."
    )
    return [
        PromptMessage(role="system", content=_SUMMARIZER_SYSTEM),
        PromptMessage(role="user", content=user_content),
    ]


def build_thread_summary_prompt(
    question: str,
    decisions: list[str],
) -> list[PromptMessage]:
    """Build prompt for summarizing an entire thread."""
    decisions_text = "\n".join(f"Round {i + 1}: {d}" for i, d in enumerate(decisions))
    user_content = (
        f"Question: {question}\n\n"
        f"Decisions across rounds:\n{decisions_text}\n\n"
        "Summarize the overall conversation and final outcome "
        "in 2-4 sentences."
    )
    return [
        PromptMessage(role="system", content=_SUMMARIZER_SYSTEM),
        PromptMessage(role="user", content=user_content),
    ]


async def generate_turn_summary(
    provider_manager: ProviderManager,
    question: str,
    proposal: str,
    challenges: list[str],
    revision: str,
    decision: str,
    *,
    model_ref: str | None = None,
    max_tokens: int = 512,
) -> ModelResponse:
    """Generate a summary for a single consensus turn.

    Args:
        provider_manager: For model routing and cost tracking.
        question: The original question.
        proposal: The proposal text.
        challenges: List of challenge content strings.
        revision: The revision text.
        decision: The committed decision text.
        model_ref: Model to use. Defaults to cheapest available.
        max_tokens: Maximum output tokens for the summary.

    Returns:
        The :class:`ModelResponse` containing the summary.
    """
    ref = model_ref if model_ref is not None else select_summarizer(provider_manager)
    messages = build_turn_summary_prompt(
        question, proposal, challenges, revision, decision
    )
    provider, model_id = provider_manager.get_provider(ref)
    response = await provider.send(
        messages, model_id, max_tokens=max_tokens, temperature=0.3
    )
    model_info = provider_manager.get_model_info(ref)
    provider_manager.record_usage(model_info, response.usage)
    return response


async def generate_thread_summary(
    provider_manager: ProviderManager,
    question: str,
    decisions: list[str],
    *,
    model_ref: str | None = None,
    max_tokens: int = 512,
) -> ModelResponse:
    """Generate a summary for an entire thread.

    Args:
        provider_manager: For model routing and cost tracking.
        question: The original question.
        decisions: List of decision content strings across rounds.
        model_ref: Model to use. Defaults to cheapest available.
        max_tokens: Maximum output tokens for the summary.

    Returns:
        The :class:`ModelResponse` containing the summary.
    """
    ref = model_ref if model_ref is not None else select_summarizer(provider_manager)
    messages = build_thread_summary_prompt(question, decisions)
    provider, model_id = provider_manager.get_provider(ref)
    response = await provider.send(
        messages, model_id, max_tokens=max_tokens, temperature=0.3
    )
    model_info = provider_manager.get_model_info(ref)
    provider_manager.record_usage(model_info, response.usage)
    return response
