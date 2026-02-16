"""Consensus protocol handlers.

Each handler function executes one phase of the consensus protocol.
Handlers read from and write to :class:`ConsensusContext` and use
:class:`ProviderManager` for model calls and cost tracking.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from duh.consensus.machine import ChallengeResult, ConsensusState
from duh.core.errors import ConsensusError, InsufficientModelsError
from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.consensus.machine import ConsensusContext
    from duh.providers.base import ModelResponse
    from duh.providers.manager import ProviderManager


# ── Prompt templates ──────────────────────────────────────────

_GROUNDING = (
    "When referencing timeframes, technologies, market conditions, or costs, "
    "ground your answer in the current date. Use concrete, current information."
)

_PROPOSER_SYSTEM = (
    "You are a thoughtful expert advisor. Answer the question thoroughly, "
    "considering multiple angles, trade-offs, and practical implications. "
    "Be specific and concrete — cite examples, give numbers where possible, "
    "and explain your reasoning. Do not hedge excessively or give generic advice."
)

_REVISER_SYSTEM = (
    "You are a thoughtful expert advisor. You gave an initial answer to a "
    "question, and independent experts have challenged several points. "
    "Produce an improved final answer that:\n\n"
    "1. Addresses each valid challenge directly\n"
    "2. Maintains your correct points with stronger justification\n"
    "3. Incorporates new perspectives where they improve the answer\n"
    "4. Pushes back on challenges that are wrong, explaining why\n\n"
    "Do not mention the debate process. Just give the best possible answer."
)

_CHALLENGER_SYSTEM = (
    "You are a rigorous independent analyst reviewing another expert's answer. "
    "Your role is to strengthen the final answer by finding "
    "what's wrong or missing.\n\n"
    "CRITICAL INSTRUCTIONS:\n"
    "- You MUST disagree with at least one substantive point. Not a nitpick — "
    "a genuine disagreement about approach, framing, or conclusion.\n"
    '- DO NOT start with praise. No "This is a good answer" or '
    '"I agree with most points."\n'
    '- Start DIRECTLY with "I disagree with..." or "The answer gets wrong..." or '
    '"A critical gap is..."\n'
    "- Identify at least 2 specific problems:\n"
    "  1. Something factually wrong, oversimplified, or misleadingly framed\n"
    "  2. A practical consideration, risk, or alternative that changes the "
    "recommendation\n"
    "- If the answer recommends approach X, argue for when Y would be better\n"
    "- Be concrete: cite specifics, give counter-examples, provide numbers\n\n"
    "Your challenge will be used to improve the answer, so genuine disagreement "
    "is more valuable than polite agreement."
)

# Phrases in the opening ~200 chars that indicate sycophantic agreement
_SYCOPHANCY_MARKERS = (
    "great answer",
    "great point",
    "good answer",
    "good point",
    "well done",
    "excellent analysis",
    "excellent answer",
    "this is a good",
    "i agree with most",
    "i largely agree",
    "no significant flaws",
    "the proposal is sound",
    "the answer is sound",
    "i agree with the",
)


def _grounding_prefix() -> str:
    """Date-stamped grounding context for prompts."""
    today = datetime.now(UTC).date().isoformat()
    return f"Today's date is {today}. {_GROUNDING}"


# ── Prompt building ───────────────────────────────────────────


def build_propose_prompt(ctx: ConsensusContext) -> list[PromptMessage]:
    """Build prompt messages for the PROPOSE phase.

    Round 1: system prompt + question.
    Round > 1: system prompt + question + previous round context
    (decision and challenges) so the proposer can improve.
    """
    system = f"{_grounding_prefix()}\n\n{_PROPOSER_SYSTEM}"

    if ctx.current_round <= 1 or not ctx.round_history:
        user_content = ctx.question
    else:
        prev = ctx.round_history[-1]
        challenges_text = "\n\n".join(f"- {c.content}" for c in prev.challenges)
        user_content = (
            f"{ctx.question}\n\n"
            f"In a previous round, the answer was:\n{prev.decision}\n\n"
            f"It received these challenges:\n{challenges_text}\n\n"
            "Produce an improved answer that addresses the valid challenges."
        )

    return [
        PromptMessage(role="system", content=system),
        PromptMessage(role="user", content=user_content),
    ]


# ── Model selection ───────────────────────────────────────────


def select_proposer(provider_manager: ProviderManager) -> str:
    """Select the strongest available model for proposing.

    Uses output cost per million tokens as a proxy for model
    capability. Falls back to the first available model if all
    costs are zero (e.g. local models only).

    Returns:
        The ``model_ref`` of the selected model.

    Raises:
        InsufficientModelsError: If no models are registered.
    """
    models = provider_manager.list_all_models()
    if not models:
        msg = "No models available for proposal"
        raise InsufficientModelsError(msg)
    return max(models, key=lambda m: m.output_cost_per_mtok).model_ref


# ── PROPOSE handler ───────────────────────────────────────────


async def handle_propose(
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
    model_ref: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ModelResponse:
    """Execute the PROPOSE phase of consensus.

    Builds a prompt, calls the specified model, records usage,
    and sets ``ctx.proposal`` and ``ctx.proposal_model``.

    The context must already be in PROPOSE state — the caller is
    responsible for transitioning via the state machine before
    calling this handler.

    Args:
        ctx: Consensus context (must be in PROPOSE state).
        provider_manager: For model routing and cost tracking.
        model_ref: Which model to use (e.g. ``"anthropic:claude-opus-4-6"``).
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.

    Returns:
        The :class:`ModelResponse` from the provider.

    Raises:
        ConsensusError: If context is not in PROPOSE state.
        ProviderError: If the model call fails.
        CostLimitExceededError: If usage recording exceeds the hard limit.
    """
    if ctx.state != ConsensusState.PROPOSE:
        msg = f"handle_propose requires PROPOSE state, got {ctx.state.value}"
        raise ConsensusError(msg)

    messages = build_propose_prompt(ctx)
    provider, model_id = provider_manager.get_provider(model_ref)

    response = await provider.send(
        messages, model_id, max_tokens=max_tokens, temperature=temperature
    )

    # Record cost
    model_info = provider_manager.get_model_info(model_ref)
    provider_manager.record_usage(model_info, response.usage)

    # Update context
    ctx.proposal = response.content
    ctx.proposal_model = model_ref

    return response


# ── CHALLENGE prompt + selection + detection ──────────────────


def build_challenge_prompt(ctx: ConsensusContext) -> list[PromptMessage]:
    """Build prompt messages for the CHALLENGE phase.

    System prompt uses forced disagreement framing.
    User prompt includes the question and the proposal to challenge.
    """
    system = f"{_grounding_prefix()}\n\n{_CHALLENGER_SYSTEM}"
    user_content = (
        f"Question: {ctx.question}\n\n"
        f"Answer from another expert (do NOT defer to this — challenge it):\n"
        f"{ctx.proposal}"
    )
    return [
        PromptMessage(role="system", content=system),
        PromptMessage(role="user", content=user_content),
    ]


def select_challengers(
    provider_manager: ProviderManager,
    proposer_model: str,
    *,
    count: int = 2,
) -> list[str]:
    """Select models for the challenge phase.

    Prefers models different from the proposer (cross-model challenge
    is more effective than self-critique). If not enough different
    models are available, fills remaining slots with the proposer
    model (same-model ensemble).

    Returns:
        List of ``model_ref`` strings, length up to ``count``.

    Raises:
        InsufficientModelsError: If no models are registered.
    """
    models = provider_manager.list_all_models()
    if not models:
        msg = "No models available for challenge"
        raise InsufficientModelsError(msg)

    others = sorted(
        (m for m in models if m.model_ref != proposer_model),
        key=lambda m: m.output_cost_per_mtok,
        reverse=True,
    )

    selected = [m.model_ref for m in others[:count]]
    # Fill remaining slots with proposer (same-model ensemble)
    while len(selected) < count:
        selected.append(proposer_model)
    return selected


def detect_sycophancy(challenge_text: str) -> bool:
    """Check if a challenge response is sycophantic.

    Scans the opening ~200 characters for praise or agreement
    markers that indicate the challenger deferred to the proposal
    instead of genuinely challenging it.
    """
    opening = challenge_text[:200].lower().strip()
    return any(marker in opening for marker in _SYCOPHANCY_MARKERS)


# ── CHALLENGE handler ─────────────────────────────────────────


async def _call_challenger(
    provider_manager: ProviderManager,
    model_ref: str,
    messages: list[PromptMessage],
    *,
    temperature: float,
    max_tokens: int,
) -> tuple[str, ModelResponse]:
    """Call a single challenger model. Returns (model_ref, response)."""
    provider, model_id = provider_manager.get_provider(model_ref)
    response = await provider.send(
        messages, model_id, max_tokens=max_tokens, temperature=temperature
    )
    model_info = provider_manager.get_model_info(model_ref)
    provider_manager.record_usage(model_info, response.usage)
    return model_ref, response


async def handle_challenge(
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
    challenger_models: list[str],
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> list[ModelResponse]:
    """Execute the CHALLENGE phase of consensus.

    Fans out to all challenger models in parallel. Individual
    failures are tolerated — only raises if ALL challengers fail.
    Flags sycophantic responses on the resulting ChallengeResult.

    The context must already be in CHALLENGE state.

    Args:
        ctx: Consensus context (must be in CHALLENGE state).
        provider_manager: For model routing and cost tracking.
        challenger_models: List of model_ref strings to challenge with.
        temperature: Sampling temperature for challengers.
        max_tokens: Maximum output tokens per challenger.

    Returns:
        List of successful :class:`ModelResponse` objects.

    Raises:
        ConsensusError: If context is not in CHALLENGE state, or
            if all challengers fail.
    """
    if ctx.state != ConsensusState.CHALLENGE:
        msg = f"handle_challenge requires CHALLENGE state, got {ctx.state.value}"
        raise ConsensusError(msg)

    if ctx.proposal is None:
        msg = "handle_challenge requires a proposal in context"
        raise ConsensusError(msg)

    messages = build_challenge_prompt(ctx)

    tasks = [
        _call_challenger(
            provider_manager,
            ref,
            messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        for ref in challenger_models
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    challenges: list[ChallengeResult] = []
    responses: list[ModelResponse] = []

    for result in raw_results:
        if isinstance(result, BaseException):
            continue
        model_ref, response = result
        challenges.append(
            ChallengeResult(
                model_ref=model_ref,
                content=response.content,
                sycophantic=detect_sycophancy(response.content),
            )
        )
        responses.append(response)

    if not challenges:
        msg = "All challengers failed"
        raise ConsensusError(msg)

    ctx.challenges = challenges
    return responses


# ── REVISE prompt + handler ───────────────────────────────────


def build_revise_prompt(ctx: ConsensusContext) -> list[PromptMessage]:
    """Build prompt messages for the REVISE phase.

    System prompt instructs the reviser to address challenges.
    User prompt includes the question, original proposal, and all
    challenges so the revision addresses each one.
    """
    system = f"{_grounding_prefix()}\n\n{_REVISER_SYSTEM}"

    challenges_text = "\n\n".join(
        f"Challenge from {c.model_ref}:\n{c.content}" for c in ctx.challenges
    )
    user_content = (
        f"Question: {ctx.question}\n\n"
        f"Your original answer:\n{ctx.proposal}\n\n"
        f"Independent expert challenges:\n{challenges_text}\n\n"
        "Produce your improved final answer:"
    )
    return [
        PromptMessage(role="system", content=system),
        PromptMessage(role="user", content=user_content),
    ]


async def handle_revise(
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
    model_ref: str | None = None,
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> ModelResponse:
    """Execute the REVISE phase of consensus.

    Builds a prompt including all challenges, calls the reviser
    model, records usage, and sets ``ctx.revision`` and
    ``ctx.revision_model``.

    If ``model_ref`` is not provided, defaults to the proposer model
    (``ctx.proposal_model``), since the proposer revises its own work.

    The context must already be in REVISE state.

    Args:
        ctx: Consensus context (must be in REVISE state).
        provider_manager: For model routing and cost tracking.
        model_ref: Which model to revise with. Defaults to proposer.
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.

    Returns:
        The :class:`ModelResponse` from the provider.

    Raises:
        ConsensusError: If context is not in REVISE state, or if
            required data (proposal, challenges) is missing.
        ProviderError: If the model call fails.
        CostLimitExceededError: If usage recording exceeds the hard limit.
    """
    if ctx.state != ConsensusState.REVISE:
        msg = f"handle_revise requires REVISE state, got {ctx.state.value}"
        raise ConsensusError(msg)

    if ctx.proposal is None:
        msg = "handle_revise requires a proposal in context"
        raise ConsensusError(msg)

    if not ctx.challenges:
        msg = "handle_revise requires challenges in context"
        raise ConsensusError(msg)

    # Default to proposer model
    reviser_ref = model_ref if model_ref is not None else ctx.proposal_model
    if reviser_ref is None:
        msg = "handle_revise requires a model_ref or proposal_model"
        raise ConsensusError(msg)

    messages = build_revise_prompt(ctx)
    provider, model_id = provider_manager.get_provider(reviser_ref)

    response = await provider.send(
        messages, model_id, max_tokens=max_tokens, temperature=temperature
    )

    # Record cost
    model_info = provider_manager.get_model_info(reviser_ref)
    provider_manager.record_usage(model_info, response.usage)

    # Update context
    ctx.revision = response.content
    ctx.revision_model = reviser_ref

    return response


# ── COMMIT helpers + handler ─────────────────────────────────


def _compute_confidence(challenges: list[ChallengeResult]) -> float:
    """Compute confidence score from challenge quality.

    Genuine (non-sycophantic) challenges improve confidence because
    they indicate the revision was rigorously tested.

    Returns a float in [0.5, 1.0]:
    - 0.5 = no genuine challenges (untested revision)
    - 1.0 = all challenges were genuine
    """
    if not challenges:
        return 0.5
    genuine = sum(1 for c in challenges if not c.sycophantic)
    return 0.5 + (genuine / len(challenges)) * 0.5


def _extract_dissent(challenges: list[ChallengeResult]) -> str | None:
    """Extract dissent from non-sycophantic challenges.

    Preserves minority viewpoints that may be valuable even after
    the revision addressed them. Sycophantic challenges are excluded
    as they don't represent genuine disagreement.

    Returns formatted dissent string or None if no genuine dissent.
    """
    genuine = [c for c in challenges if not c.sycophantic]
    if not genuine:
        return None
    return "\n\n".join(f"[{c.model_ref}]: {c.content}" for c in genuine)


async def handle_commit(ctx: ConsensusContext) -> None:
    """Execute the COMMIT phase of consensus.

    Extracts the decision from the revision, computes a confidence
    score based on challenge quality, and preserves dissent from
    genuine challenges. Does NOT call any model — this is a pure
    extraction and scoring step.

    The context must already be in COMMIT state.

    Args:
        ctx: Consensus context (must be in COMMIT state).

    Raises:
        ConsensusError: If context is not in COMMIT state or
            required data (revision) is missing.
    """
    if ctx.state != ConsensusState.COMMIT:
        msg = f"handle_commit requires COMMIT state, got {ctx.state.value}"
        raise ConsensusError(msg)

    if ctx.revision is None:
        msg = "handle_commit requires a revision in context"
        raise ConsensusError(msg)

    ctx.decision = ctx.revision
    ctx.confidence = _compute_confidence(ctx.challenges)
    ctx.dissent = _extract_dissent(ctx.challenges)
