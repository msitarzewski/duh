"""Question refinement: pre-consensus clarification step.

Uses the most capable (most expensive) model to evaluate whether a
question is ambiguous and, if so, generate clarifying questions.  A
second call rewrites the original question incorporating the user's
answers.  This is the user's first impression — it must be exceptional.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from duh.consensus.json_extract import JSONExtractionError, extract_json
from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.providers.manager import ProviderManager

logger = logging.getLogger(__name__)


async def analyze_question(
    question: str,
    provider_manager: ProviderManager,
    *,
    max_questions: int = 4,
) -> dict[str, Any]:
    """Evaluate whether *question* needs clarification.

    Returns ``{"needs_refinement": false}`` when the question is specific
    enough, or ``{"needs_refinement": true, "questions": [...]}`` with up
    to *max_questions* clarifying questions otherwise.

    On any failure (no models, JSON parse error, provider error) the
    function returns ``{"needs_refinement": false}`` so consensus can
    proceed uninterrupted.
    """
    models = provider_manager.list_all_models()
    if not models:
        return {"needs_refinement": False}

    best = max(models, key=lambda m: m.input_cost_per_mtok)
    provider, model_id = provider_manager.get_provider(best.model_ref)

    prompt = (
        "You are an expert question analyst and strategic thinker. Your job "
        "is to determine whether a question contains enough context for a "
        "panel of experts to give a truly excellent, specific, actionable "
        "answer — or whether critical context is missing.\n\n"
        "Think deeply: what assumptions would an expert panel have to make? "
        "If those assumptions could lead to fundamentally different answers, "
        "the question needs refinement.\n\n"
        "Consider missing context such as: scale, budget, team size/expertise, "
        "timeline, technical constraints, use-case, existing infrastructure, "
        "success criteria, risk tolerance, regulatory requirements, or "
        "geographic/market context.\n\n"
        f"Question: {question}\n\n"
        "Return ONLY a JSON object. If the question is already specific "
        "enough for expert-quality advice:\n"
        '{"needs_refinement": false}\n\n'
        "If clarification would meaningfully improve the answer, return:\n"
        '{"needs_refinement": true, "questions": [\n'
        '  {"question": "...", "hint": "brief guidance on what kind of answer helps"}\n'
        "]}\n\n"
        f"Include at most {max_questions} questions. Each should be concise, "
        "focused on one critical missing dimension, and phrased in a way that "
        "feels natural and respectful — like a senior consultant clarifying "
        "scope before giving advice. Only ask questions whose answers would "
        "materially change the recommendation."
    )

    try:
        response = await provider.send(
            [PromptMessage(role="user", content=prompt)],
            model_id,
            max_tokens=500,
            temperature=0.3,
            response_format="json",
        )
        data = extract_json(response.content)
        provider_manager.record_usage(best, response.usage)

        if not data.get("needs_refinement"):
            return {"needs_refinement": False}

        questions = data.get("questions", [])
        if not isinstance(questions, list) or not questions:
            return {"needs_refinement": False}

        # Normalise and cap
        clean: list[dict[str, str | None]] = []
        for q in questions[:max_questions]:
            if isinstance(q, dict) and q.get("question"):
                clean.append(
                    {
                        "question": str(q["question"]),
                        "hint": str(q["hint"]) if q.get("hint") else None,
                    }
                )

        if not clean:
            return {"needs_refinement": False}

        return {"needs_refinement": True, "questions": clean}

    except (JSONExtractionError, Exception):
        logger.debug("Question refinement analysis failed, skipping", exc_info=True)
        return {"needs_refinement": False}


async def enrich_question(
    original: str,
    clarifications: list[dict[str, str]],
    provider_manager: ProviderManager,
) -> str:
    """Rewrite *original* incorporating clarification answers.

    Each entry in *clarifications* has ``question`` and ``answer`` keys.
    Returns the enriched question string, or the original on failure.
    """
    models = provider_manager.list_all_models()
    if not models:
        return original

    best = max(models, key=lambda m: m.input_cost_per_mtok)
    provider, model_id = provider_manager.get_provider(best.model_ref)

    qa_block = "\n".join(
        f"Q: {c['question']}\nA: {c['answer']}" for c in clarifications
    )

    prompt = (
        "Rewrite the following question into a single, specific, "
        "self-contained question that incorporates all the additional "
        "context provided below. Keep the rewritten question natural and "
        "concise — do not repeat the clarifications verbatim, just weave "
        "the context in.\n\n"
        f"Original question: {original}\n\n"
        f"Additional context:\n{qa_block}\n\n"
        "Return ONLY the rewritten question, nothing else."
    )

    try:
        response = await provider.send(
            [PromptMessage(role="user", content=prompt)],
            model_id,
            max_tokens=500,
            temperature=0.3,
        )
        provider_manager.record_usage(best, response.usage)
        enriched = response.content.strip()
        return enriched if enriched else original
    except Exception:
        logger.debug("Question enrichment failed, using original", exc_info=True)
        return original
