"""Task-type classifier: determine whether a question is reasoning or judgment.

Uses the cheapest available model with JSON mode to classify the question,
falling back to ``UNKNOWN`` on any failure.
"""

from __future__ import annotations

import enum
import logging
from typing import TYPE_CHECKING

from duh.consensus.json_extract import extract_json
from duh.providers.base import PromptMessage

if TYPE_CHECKING:
    from duh.providers.base import ModelInfo
    from duh.providers.manager import ProviderManager

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a task classifier. Classify the user's question into one of "
    "these categories:\n"
    '- "reasoning": questions requiring logical analysis, math, code, '
    "or step-by-step problem solving\n"
    '- "judgment": questions requiring opinions, evaluations, comparisons, '
    "or subjective assessment\n\n"
    "Respond with a JSON object: "
    '{"task_type": "reasoning"} or {"task_type": "judgment"}'
)


class TaskType(enum.Enum):
    """Classification of a user question."""

    REASONING = "reasoning"
    JUDGMENT = "judgment"
    UNKNOWN = "unknown"


def _cheapest_model(models: list[ModelInfo]) -> ModelInfo:
    """Return the model with the lowest input cost."""
    return min(models, key=lambda m: m.input_cost_per_mtok)


async def classify_task_type(
    question: str,
    provider_manager: ProviderManager,
) -> TaskType:
    """Classify *question* as reasoning, judgment, or unknown.

    Uses the cheapest model by input cost. Returns ``TaskType.UNKNOWN``
    on any failure (parse error, model error, empty model list, etc.).
    """
    models = provider_manager.list_all_models()
    if not models:
        return TaskType.UNKNOWN

    cheapest = _cheapest_model(models)
    provider, model_id = provider_manager.get_provider(cheapest.model_ref)

    messages = [
        PromptMessage(role="system", content=_SYSTEM_PROMPT),
        PromptMessage(role="user", content=question),
    ]

    try:
        response = await provider.send(
            messages,
            model_id,
            temperature=0.0,
            response_format="json",
        )
        provider_manager.record_usage(cheapest, response.usage)
        data = extract_json(response.content)
        raw_type = data.get("task_type", "").lower().strip()
        return TaskType(raw_type)
    except Exception as exc:
        logger.debug("Classification failed: %s", exc)
        return TaskType.UNKNOWN
