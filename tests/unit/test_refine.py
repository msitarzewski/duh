"""Tests for question refinement (analyze_question / enrich_question)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from duh.consensus.refine import analyze_question, enrich_question


def _mock_pm(response_content: str) -> MagicMock:
    """Create a mock ProviderManager that returns *response_content*."""
    model = MagicMock()
    model.input_cost_per_mtok = 0.5
    model.model_ref = "mock:cheap"

    provider = AsyncMock()
    provider.send = AsyncMock(
        return_value=MagicMock(
            content=response_content,
            usage=MagicMock(input_tokens=10, output_tokens=20),
        )
    )

    pm = MagicMock()
    pm.list_all_models.return_value = [model]
    pm.get_provider.return_value = (provider, "cheap")
    pm.record_usage = MagicMock()
    return pm


# ── analyze_question ──────────────────────────────────────────


class TestAnalyzeQuestion:
    async def test_no_refinement_needed(self) -> None:
        pm = _mock_pm(json.dumps({"needs_refinement": False}))
        result = await analyze_question("What is 2+2?", pm)
        assert result["needs_refinement"] is False

    async def test_refinement_needed(self) -> None:
        payload = {
            "needs_refinement": True,
            "questions": [
                {"question": "What scale?", "hint": "users/requests"},
                {"question": "Budget?", "hint": None},
            ],
        }
        pm = _mock_pm(json.dumps(payload))
        result = await analyze_question("What database should I use?", pm)
        assert result["needs_refinement"] is True
        assert len(result["questions"]) == 2
        assert result["questions"][0]["question"] == "What scale?"
        assert result["questions"][0]["hint"] == "users/requests"
        assert result["questions"][1]["hint"] is None

    async def test_max_questions_capped(self) -> None:
        payload = {
            "needs_refinement": True,
            "questions": [{"question": f"Q{i}?"} for i in range(10)],
        }
        pm = _mock_pm(json.dumps(payload))
        result = await analyze_question("Vague?", pm, max_questions=3)
        assert len(result["questions"]) == 3

    async def test_no_models_returns_no_refinement(self) -> None:
        pm = MagicMock()
        pm.list_all_models.return_value = []
        result = await analyze_question("anything", pm)
        assert result["needs_refinement"] is False

    async def test_json_parse_error_returns_no_refinement(self) -> None:
        pm = _mock_pm("This is not JSON at all")
        result = await analyze_question("anything", pm)
        assert result["needs_refinement"] is False

    async def test_provider_error_returns_no_refinement(self) -> None:
        pm = _mock_pm("")
        provider, _ = pm.get_provider("mock:cheap")
        provider.send.side_effect = RuntimeError("API down")
        result = await analyze_question("anything", pm)
        assert result["needs_refinement"] is False

    async def test_empty_questions_returns_no_refinement(self) -> None:
        payload = {"needs_refinement": True, "questions": []}
        pm = _mock_pm(json.dumps(payload))
        result = await analyze_question("anything", pm)
        assert result["needs_refinement"] is False

    async def test_json_in_code_fence(self) -> None:
        fenced = '```json\n{"needs_refinement": false}\n```'
        pm = _mock_pm(fenced)
        result = await analyze_question("specific question", pm)
        assert result["needs_refinement"] is False


# ── enrich_question ───────────────────────────────────────────


class TestEnrichQuestion:
    async def test_enrichment(self) -> None:
        pm = _mock_pm("What database for a 10k-user SaaS on AWS with $500/mo budget?")
        result = await enrich_question(
            "What database should I use?",
            [
                {"question": "Scale?", "answer": "10k users"},
                {"question": "Budget?", "answer": "$500/mo"},
            ],
            pm,
        )
        assert "10k" in result or "database" in result

    async def test_no_models_returns_original(self) -> None:
        pm = MagicMock()
        pm.list_all_models.return_value = []
        result = await enrich_question("original?", [], pm)
        assert result == "original?"

    async def test_provider_error_returns_original(self) -> None:
        pm = _mock_pm("")
        provider, _ = pm.get_provider("mock:cheap")
        provider.send.side_effect = RuntimeError("boom")
        result = await enrich_question("original?", [], pm)
        assert result == "original?"

    async def test_empty_response_returns_original(self) -> None:
        pm = _mock_pm("   ")
        result = await enrich_question("original?", [], pm)
        assert result == "original?"
