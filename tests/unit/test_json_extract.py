"""Tests for JSON extraction utility."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from duh.consensus.json_extract import (
    JSONExtractionError,
    extract_json,
    extract_validated,
)

# ── extract_json: clean JSON ────────────────────────────────────────


class TestExtractCleanJSON:
    def test_simple_object(self) -> None:
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_nested_object(self) -> None:
        result = extract_json('{"a": {"b": 1}, "c": [1, 2]}')
        assert result == {"a": {"b": 1}, "c": [1, 2]}

    def test_whitespace_padded(self) -> None:
        result = extract_json('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}

    def test_numeric_values(self) -> None:
        result = extract_json('{"count": 42, "ratio": 0.75}')
        assert result == {"count": 42, "ratio": 0.75}

    def test_boolean_null_values(self) -> None:
        result = extract_json('{"flag": true, "empty": null}')
        assert result == {"flag": True, "empty": None}


# ── extract_json: markdown code fences ──────────────────────────────


class TestExtractFromMarkdown:
    def test_json_fence(self) -> None:
        text = 'Here is the result:\n```json\n{"intent": "query"}\n```'
        result = extract_json(text)
        assert result == {"intent": "query"}

    def test_plain_fence(self) -> None:
        text = 'Result:\n```\n{"intent": "query"}\n```\nDone.'
        result = extract_json(text)
        assert result == {"intent": "query"}

    def test_fence_with_surrounding_text(self) -> None:
        text = (
            "I analyzed the question and here is the classification:\n\n"
            '```json\n{"intent": "factual", "category": "science"}\n```\n\n'
            "This is based on the content."
        )
        result = extract_json(text)
        assert result == {"intent": "factual", "category": "science"}


# ── extract_json: bare JSON in text ─────────────────────────────────


class TestExtractBareJSON:
    def test_json_with_leading_text(self) -> None:
        text = 'The classification is {"intent": "judgment"}'
        result = extract_json(text)
        assert result == {"intent": "judgment"}

    def test_json_with_trailing_text(self) -> None:
        text = '{"intent": "judgment"} as determined above.'
        result = extract_json(text)
        assert result == {"intent": "judgment"}

    def test_json_with_surrounding_text(self) -> None:
        text = 'Here: {"intent": "factual", "category": "tech"} end.'
        result = extract_json(text)
        assert result == {"intent": "factual", "category": "tech"}


# ── extract_json: error cases ───────────────────────────────────────


class TestExtractErrors:
    def test_empty_string(self) -> None:
        with pytest.raises(JSONExtractionError, match=r"Empty text"):
            extract_json("")

    def test_whitespace_only(self) -> None:
        with pytest.raises(JSONExtractionError, match=r"Empty text"):
            extract_json("   \n  ")

    def test_no_json(self) -> None:
        with pytest.raises(JSONExtractionError, match=r"No valid JSON"):
            extract_json("This is plain text with no JSON at all.")

    def test_invalid_json(self) -> None:
        with pytest.raises(JSONExtractionError, match=r"No valid JSON"):
            extract_json("{invalid json content}")

    def test_array_not_object(self) -> None:
        with pytest.raises(JSONExtractionError, match=r"No valid JSON"):
            extract_json("[1, 2, 3]")


# ── extract_validated: Pydantic validation ──────────────────────────


class TaxonomyModel(BaseModel):
    intent: str
    category: str
    genus: str | None = None


class TestExtractValidated:
    def test_valid_schema(self) -> None:
        text = '{"intent": "factual", "category": "science", "genus": "physics"}'
        result = extract_validated(text, TaxonomyModel)
        assert isinstance(result, TaxonomyModel)
        assert result.intent == "factual"
        assert result.category == "science"
        assert result.genus == "physics"

    def test_optional_field_missing(self) -> None:
        text = '{"intent": "judgment", "category": "ethics"}'
        result = extract_validated(text, TaxonomyModel)
        assert result.genus is None

    def test_invalid_schema(self) -> None:
        from pydantic import ValidationError

        text = '{"wrong": "fields"}'
        with pytest.raises(ValidationError):
            extract_validated(text, TaxonomyModel)

    def test_extraction_failure_propagates(self) -> None:
        with pytest.raises(JSONExtractionError):
            extract_validated("no json here", TaxonomyModel)
