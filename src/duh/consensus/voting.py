"""Voting protocol: parallel model fan-out with aggregation strategies.

Models answer a question independently and in parallel. A meta-judge
(the strongest model by output cost) then picks the best answer
(majority) or synthesises all answers into one (weighted).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.providers.base import ModelInfo, ModelResponse
    from duh.providers.manager import ProviderManager

logger = logging.getLogger(__name__)

# ── Data classes ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class VoteResult:
    """A single model's independent answer."""

    model_ref: str
    content: str
    confidence: float = 0.0
    rigor: float = 0.5


@dataclass(frozen=True, slots=True)
class VotingAggregation:
    """Aggregated result from the voting protocol."""

    votes: tuple[VoteResult, ...]
    decision: str
    strategy: str
    confidence: float
    rigor: float = 0.5


# ── Internal helpers ─────────────────────────────────────────────


async def _collect_vote(
    question: str,
    model_info: ModelInfo,
    provider_manager: ProviderManager,
) -> VoteResult | Exception:
    """Send *question* to one model and return a VoteResult."""
    provider, model_id = provider_manager.get_provider(model_info.model_ref)
    messages = [
        PromptMessage(role="user", content=question),
    ]
    try:
        response: ModelResponse = await provider.send(
            messages, model_id, temperature=0.7
        )
        provider_manager.record_usage(model_info, response.usage)
        return VoteResult(
            model_ref=model_info.model_ref,
            content=response.content,
        )
    except Exception as exc:
        logger.warning("Vote failed for %s: %s", model_info.model_ref, exc)
        return exc


def _strongest_model(models: list[ModelInfo]) -> ModelInfo:
    """Return the model with the highest output cost (capability proxy)."""
    return max(models, key=lambda m: m.output_cost_per_mtok)


async def _aggregate_majority(
    question: str,
    votes: list[VoteResult],
    provider_manager: ProviderManager,
    strongest: ModelInfo,
) -> VotingAggregation:
    """Use the strongest model as meta-judge to pick the best answer."""
    numbered = "\n\n".join(
        f"--- Answer {i + 1} (from {v.model_ref}) ---\n{v.content}"
        for i, v in enumerate(votes)
    )
    system_prompt = (
        "You are selecting the best answer from multiple experts. "
        "Read all the answers below and return the best answer, "
        "improving it if possible. Do not mention that you are selecting "
        "from multiple answers."
    )
    user_prompt = (
        f"Original question: {question}\n\n"
        f"Expert answers:\n{numbered}\n\n"
        "Return the best answer with any improvements."
    )
    messages = [
        PromptMessage(role="system", content=system_prompt),
        PromptMessage(role="user", content=user_prompt),
    ]
    provider, model_id = provider_manager.get_provider(strongest.model_ref)
    response = await provider.send(messages, model_id, temperature=0.3)
    provider_manager.record_usage(strongest, response.usage)

    return VotingAggregation(
        votes=tuple(votes),
        decision=response.content,
        strategy="majority",
        confidence=0.8,
    )


async def _aggregate_weighted(
    question: str,
    votes: list[VoteResult],
    provider_manager: ProviderManager,
    strongest: ModelInfo,
) -> VotingAggregation:
    """Use the strongest model to synthesise all answers, weighting by capability."""
    numbered = "\n\n".join(
        f"--- Answer {i + 1} (from {v.model_ref}, "
        f"capability weight: "
        f"{_capability_weight(v.model_ref, provider_manager):.2f}"
        f") ---\n{v.content}"
        for i, v in enumerate(votes)
    )
    system_prompt = (
        "You are synthesising answers from multiple experts into a single "
        "comprehensive response. Higher-capability-weight answers should be "
        "given more influence. Do not mention weights or that you are merging "
        "answers."
    )
    user_prompt = (
        f"Original question: {question}\n\n"
        f"Expert answers with capability weights:\n{numbered}\n\n"
        "Synthesise into one comprehensive answer."
    )
    messages = [
        PromptMessage(role="system", content=system_prompt),
        PromptMessage(role="user", content=user_prompt),
    ]
    provider, model_id = provider_manager.get_provider(strongest.model_ref)
    response = await provider.send(messages, model_id, temperature=0.3)
    provider_manager.record_usage(strongest, response.usage)

    return VotingAggregation(
        votes=tuple(votes),
        decision=response.content,
        strategy="weighted",
        confidence=0.85,
    )


def _capability_weight(model_ref: str, pm: ProviderManager) -> float:
    """Return a normalised capability weight (output cost as proxy)."""
    info = pm.get_model_info(model_ref)
    return info.output_cost_per_mtok


# ── Public API ───────────────────────────────────────────────────


async def run_voting(
    question: str,
    provider_manager: ProviderManager,
    *,
    aggregation: str = "majority",
) -> VotingAggregation:
    """Fan out *question* to all models and aggregate answers.

    Args:
        question: The user's question.
        provider_manager: Manages providers and cost tracking.
        aggregation: ``"majority"`` (meta-judge picks best) or
            ``"weighted"`` (synthesis weighted by capability).

    Returns:
        A :class:`VotingAggregation` with the final decision.
    """
    models = provider_manager.list_all_models()
    if not models:
        return VotingAggregation(
            votes=(),
            decision="",
            strategy=aggregation,
            confidence=0.0,
        )

    # Fan out to all models in parallel
    tasks = [_collect_vote(question, m, provider_manager) for m in models]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Filter successful votes
    votes: list[VoteResult] = [r for r in results if isinstance(r, VoteResult)]

    if not votes:
        return VotingAggregation(
            votes=(),
            decision="",
            strategy=aggregation,
            confidence=0.0,
        )

    # Single model — no aggregation needed
    if len(votes) == 1:
        v = votes[0]
        return VotingAggregation(
            votes=(v,),
            decision=v.content,
            strategy=aggregation,
            confidence=1.0,
        )

    strongest = _strongest_model(models)
    if aggregation == "weighted":
        return await _aggregate_weighted(question, votes, provider_manager, strongest)
    # Default: majority
    return await _aggregate_majority(question, votes, provider_manager, strongest)
