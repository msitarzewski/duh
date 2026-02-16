"""JSON extraction utility for structured model output.

Handles extracting JSON from model responses that may contain surrounding
text, markdown code fences, or other formatting. Optional Pydantic
validation for schema enforcement.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from pydantic import BaseModel

T = TypeVar("T")

# Regex to find JSON object in text (greedy match between outermost braces)
_JSON_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_JSON_RE = re.compile(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", re.DOTALL)


class JSONExtractionError(Exception):
    """Raised when JSON cannot be extracted from text."""


def extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from text.

    Tries strategies in order:
    1. Direct ``json.loads()`` on the full text
    2. Extract from markdown code fences (```json ... ```)
    3. Find bare ``{...}`` in the text

    Args:
        text: Text that may contain a JSON object.

    Returns:
        Parsed JSON as a dict.

    Raises:
        JSONExtractionError: If no valid JSON object can be found.
    """
    stripped = text.strip()
    if not stripped:
        msg = "Empty text"
        raise JSONExtractionError(msg)

    # Strategy 1: Direct parse
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # Strategy 2: Markdown code fence
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # Strategy 3: Bare JSON object
    match = _BARE_JSON_RE.search(text)
    if match:
        try:
            result = json.loads(match.group(0))
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    msg = "No valid JSON object found in text"
    raise JSONExtractionError(msg)


def extract_validated(text: str, model_class: type[BaseModel]) -> BaseModel:
    """Extract JSON and validate against a Pydantic model.

    Args:
        text: Text containing a JSON object.
        model_class: Pydantic model class for validation.

    Returns:
        Validated Pydantic model instance.

    Raises:
        JSONExtractionError: If JSON cannot be extracted.
        pydantic.ValidationError: If JSON doesn't match the schema.
    """
    data = extract_json(text)
    return model_class.model_validate(data)
