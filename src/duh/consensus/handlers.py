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
    from duh.tools.registry import ToolRegistry


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

_CHALLENGE_FRAMINGS: dict[str, str] = {
    "flaw": (
        "You are a rigorous analyst reviewing another expert's answer. "
        "Your role is to find factual errors, logical flaws, and "
        "oversimplifications.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- You MUST identify at least one substantive factual or "
        "logical error.\n"
        '- DO NOT start with praise. No "This is a good answer" or '
        '"I agree with most points."\n'
        '- Start DIRECTLY with "The answer gets wrong..." or '
        '"A factual error is..."\n'
        "- For each flaw: state what's wrong, why it matters, and "
        "what the correct information is.\n"
        "- Be concrete: cite specifics, give counter-examples, "
        "provide numbers.\n\n"
        "Your challenge will be used to improve the answer."
    ),
    "alternative": (
        "You are a creative strategist reviewing another expert's answer. "
        "Your role is to propose fundamentally different approaches "
        "the answer overlooks.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- You MUST propose at least one alternative approach that "
        "could be superior.\n"
        '- DO NOT start with praise. No "This is a good answer."\n'
        '- Start DIRECTLY with "An alternative approach is..." or '
        '"The answer overlooks..."\n'
        "- For each alternative: explain the approach, when it's "
        "better, and its trade-offs vs the proposed solution.\n"
        "- Think laterally: different technologies, methodologies, "
        "or framings.\n\n"
        "Your alternatives will broaden the answer's perspective."
    ),
    "risk": (
        "You are a risk analyst reviewing another expert's answer. "
        "Your role is to identify risks, failure modes, and "
        "unintended consequences.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- You MUST identify at least two concrete risks the answer "
        "doesn't adequately address.\n"
        '- DO NOT start with praise. No "This is a good answer."\n'
        '- Start DIRECTLY with "A critical risk is..." or '
        '"The answer underestimates..."\n'
        "- For each risk: describe the scenario, its likelihood, "
        "impact, and suggested mitigation.\n"
        "- Consider: edge cases, scaling issues, security, "
        "dependencies, and second-order effects.\n\n"
        "Your risk analysis will strengthen the recommendation."
    ),
    "devils_advocate": (
        "You are a devil's advocate reviewing another expert's answer. "
        "Your role is to argue the strongest possible case against "
        "the recommendation.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "- You MUST construct a compelling argument for why the "
        "answer's recommendation is wrong.\n"
        '- DO NOT start with praise. No "This is a good answer."\n'
        '- Start DIRECTLY with "I disagree because..." or '
        '"The recommendation fails because..."\n'
        "- Argue as if you genuinely believe the opposite position.\n"
        "- Use evidence, examples, and logic to support your "
        "counter-argument.\n"
        "- If the answer recommends X, make the strongest case "
        "for not-X.\n\n"
        "Your counter-argument will stress-test the recommendation."
    ),
}

# Ordered list for round-robin assignment
_FRAMING_ORDER: list[str] = [
    "flaw",
    "alternative",
    "risk",
    "devils_advocate",
]

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


def select_proposer(
    provider_manager: ProviderManager,
    *,
    panel: list[str] | None = None,
) -> str:
    """Select the strongest available model for proposing.

    Uses output cost per million tokens as a proxy for model
    capability. Falls back to the first available model if all
    costs are zero (e.g. local models only).

    When *panel* is provided, only models whose ``model_ref`` is
    in the panel list are considered.  Models with
    ``proposer_eligible=False`` (e.g. search-grounded models)
    are always excluded from proposing.

    Returns:
        The ``model_ref`` of the selected model.

    Raises:
        InsufficientModelsError: If no eligible models remain.
    """
    models = provider_manager.list_all_models()
    if not models:
        msg = "No models available for proposal"
        raise InsufficientModelsError(msg)

    # Apply panel filter
    if panel:
        models = [m for m in models if m.model_ref in panel]

    # Exclude proposer-ineligible models
    eligible = [m for m in models if m.proposer_eligible]
    if not eligible:
        msg = "No proposer-eligible models available"
        raise InsufficientModelsError(msg)

    return max(eligible, key=lambda m: m.output_cost_per_mtok).model_ref


# ── Tool call logging ────────────────────────────────────────


def _log_tool_calls(ctx: ConsensusContext, response: ModelResponse, phase: str) -> None:
    """Log any tool calls from a response to the context."""
    if response.tool_calls:
        for tc in response.tool_calls:
            ctx.tool_calls_log.append(
                {"phase": phase, "tool": tc.name, "arguments": tc.arguments}
            )


# ── PROPOSE handler ───────────────────────────────────────────


async def handle_propose(
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
    model_ref: str,
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    tool_registry: ToolRegistry | None = None,
) -> ModelResponse:
    """Execute the PROPOSE phase of consensus.

    Builds a prompt, calls the specified model, records usage,
    and sets ``ctx.proposal`` and ``ctx.proposal_model``.

    The context must already be in PROPOSE state — the caller is
    responsible for transitioning via the state machine before
    calling this handler.

    When ``tool_registry`` is provided, uses :func:`tool_augmented_send`
    instead of a direct ``provider.send()`` call, enabling the model
    to use tools during proposal generation.

    Args:
        ctx: Consensus context (must be in PROPOSE state).
        provider_manager: For model routing and cost tracking.
        model_ref: Which model to use (e.g. ``"anthropic:claude-opus-4-6"``).
        temperature: Sampling temperature.
        max_tokens: Maximum output tokens.
        tool_registry: Optional tool registry for tool-augmented calls.

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

    if tool_registry is not None:
        from duh.tools.augmented_send import tool_augmented_send

        response = await tool_augmented_send(
            provider,
            model_id,
            messages,
            tool_registry,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        _log_tool_calls(ctx, response, "propose")
    else:
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


def build_challenge_prompt(
    ctx: ConsensusContext,
    framing: str = "flaw",
) -> list[PromptMessage]:
    """Build prompt messages for the CHALLENGE phase.

    Uses the specified framing to produce a distinct system prompt.
    Falls back to ``"flaw"`` if the framing is not recognized.

    Args:
        ctx: Consensus context with the proposal to challenge.
        framing: One of the challenge framing types.
    """
    system_text = _CHALLENGE_FRAMINGS.get(framing, _CHALLENGE_FRAMINGS["flaw"])
    system = f"{_grounding_prefix()}\n\n{system_text}"
    user_content = (
        f"Question: {ctx.question}\n\n"
        f"Answer from another expert (do NOT defer to this -- challenge it):\n"
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
    panel: list[str] | None = None,
) -> list[str]:
    """Select models for the challenge phase.

    Prefers models different from the proposer (cross-model challenge
    is more effective than self-critique). If not enough different
    models are available, fills remaining slots with the proposer
    model (same-model ensemble).

    When *panel* is provided, only models whose ``model_ref`` is
    in the panel list are considered.

    Returns:
        List of ``model_ref`` strings, length up to ``count``.

    Raises:
        InsufficientModelsError: If no models are registered.
    """
    models = provider_manager.list_all_models()
    if not models:
        msg = "No models available for challenge"
        raise InsufficientModelsError(msg)

    # Apply panel filter
    if panel:
        models = [m for m in models if m.model_ref in panel]
        if not models:
            msg = "No panel models available for challenge"
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
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
    model_ref: str,
    framing: str,
    *,
    temperature: float,
    max_tokens: int,
    tool_registry: ToolRegistry | None = None,
) -> tuple[str, str, ModelResponse]:
    """Call a single challenger model.

    Returns (model_ref, framing, response).
    """
    messages = build_challenge_prompt(ctx, framing=framing)
    provider, model_id = provider_manager.get_provider(model_ref)

    if tool_registry is not None:
        from duh.tools.augmented_send import tool_augmented_send

        response = await tool_augmented_send(
            provider,
            model_id,
            messages,
            tool_registry,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        _log_tool_calls(ctx, response, "challenge")
    else:
        response = await provider.send(
            messages, model_id, max_tokens=max_tokens, temperature=temperature
        )

    model_info = provider_manager.get_model_info(model_ref)
    provider_manager.record_usage(model_info, response.usage)
    return model_ref, framing, response


async def handle_challenge(
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
    challenger_models: list[str],
    *,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    tool_registry: ToolRegistry | None = None,
) -> list[ModelResponse]:
    """Execute the CHALLENGE phase of consensus.

    Fans out to all challenger models in parallel with differentiated
    framings assigned round-robin. Individual failures are tolerated
    -- only raises if ALL challengers fail. Flags sycophantic
    responses on the resulting ChallengeResult.

    The context must already be in CHALLENGE state.

    When ``tool_registry`` is provided, each challenger can use tools
    during challenge generation via :func:`tool_augmented_send`.

    Args:
        ctx: Consensus context (must be in CHALLENGE state).
        provider_manager: For model routing and cost tracking.
        challenger_models: List of model_ref strings to challenge with.
        temperature: Sampling temperature for challengers.
        max_tokens: Maximum output tokens per challenger.
        tool_registry: Optional tool registry for tool-augmented calls.

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

    # Assign framings round-robin
    tasks = [
        _call_challenger(
            ctx,
            provider_manager,
            ref,
            _FRAMING_ORDER[i % len(_FRAMING_ORDER)],
            temperature=temperature,
            max_tokens=max_tokens,
            tool_registry=tool_registry,
        )
        for i, ref in enumerate(challenger_models)
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    challenges: list[ChallengeResult] = []
    responses: list[ModelResponse] = []

    for result in raw_results:
        if isinstance(result, BaseException):
            continue
        model_ref, framing, response = result
        challenges.append(
            ChallengeResult(
                model_ref=model_ref,
                content=response.content,
                sycophantic=detect_sycophancy(response.content),
                framing=framing,
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


async def handle_commit(
    ctx: ConsensusContext,
    provider_manager: ProviderManager | None = None,
    *,
    classify: bool = False,
) -> None:
    """Execute the COMMIT phase of consensus.

    Extracts the decision from the revision, computes a confidence
    score based on challenge quality, and preserves dissent from
    genuine challenges.

    If ``classify=True`` and a provider_manager is given, makes an
    optional lightweight model call (cheapest model, JSON mode) to
    classify the decision into taxonomy fields (intent, category,
    genus). Falls back gracefully if classification fails.

    The context must already be in COMMIT state.

    Args:
        ctx: Consensus context (must be in COMMIT state).
        provider_manager: For taxonomy classification (optional).
        classify: Whether to attempt taxonomy classification.

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

    # Optional taxonomy classification
    if classify and provider_manager is not None:
        taxonomy = await _classify_decision(ctx, provider_manager)
        if taxonomy:
            ctx.taxonomy = taxonomy


async def _classify_decision(
    ctx: ConsensusContext,
    provider_manager: ProviderManager,
) -> dict[str, str] | None:
    """Classify a decision into taxonomy fields.

    Uses the cheapest model with JSON mode. Returns None on failure.
    """
    from duh.consensus.json_extract import JSONExtractionError, extract_json

    models = provider_manager.list_all_models()
    if not models:
        return None

    cheapest = min(models, key=lambda m: m.input_cost_per_mtok)
    provider, model_id = provider_manager.get_provider(cheapest.model_ref)

    prompt = (
        "Classify this decision into taxonomy fields. "
        "Return ONLY a JSON object with these fields:\n"
        '- "intent": one of "factual", "judgment", "creative", '
        '"strategic", "technical"\n'
        '- "category": a short topic label (e.g. "database", '
        '"security", "architecture")\n'
        '- "genus": a more specific classification (optional, '
        "can be null)\n\n"
        f"Question: {ctx.question}\n"
        f"Decision: {ctx.decision}"
    )

    try:
        response = await provider.send(
            [PromptMessage(role="user", content=prompt)],
            model_id,
            max_tokens=200,
            temperature=0.3,
            response_format="json",
        )
        data = extract_json(response.content)
        provider_manager.record_usage(cheapest, response.usage)
        return {
            "intent": str(data.get("intent", "")),
            "category": str(data.get("category", "")),
            "genus": str(data.get("genus", "")) if data.get("genus") else "",
        }
    except (JSONExtractionError, Exception):
        return None
