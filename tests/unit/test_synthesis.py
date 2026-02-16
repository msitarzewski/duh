"""Tests for the synthesis handler: merge and prioritize strategies."""

from __future__ import annotations

import pytest

from duh.consensus.scheduler import SubtaskResult
from duh.consensus.synthesis import (
    SynthesisResult,
    _build_merge_prompt,
    _build_prioritize_prompt,
    synthesize,
)
from duh.core.errors import ConsensusError

# ── Helpers ──────────────────────────────────────────────────────


def _sample_results() -> list[SubtaskResult]:
    """Create sample subtask results for testing."""
    return [
        SubtaskResult(
            label="research",
            decision="Found three options: A, B, C",
            confidence=0.9,
        ),
        SubtaskResult(
            label="compare",
            decision="Option B is best for cost",
            confidence=0.75,
        ),
        SubtaskResult(
            label="recommend",
            decision="Use option B with fallback to A",
            confidence=0.85,
        ),
    ]


# ── SynthesisResult dataclass ──────────────────────────────────


class TestSynthesisResult:
    def test_creation(self) -> None:
        r = SynthesisResult(content="Final answer", confidence=0.8, strategy="merge")
        assert r.content == "Final answer"
        assert r.confidence == pytest.approx(0.8)
        assert r.strategy == "merge"


# ── Merge prompt building ──────────────────────────────────────


class TestBuildMergePrompt:
    def test_returns_system_and_user(self) -> None:
        messages = _build_merge_prompt("Question?", _sample_results())
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_user_includes_question(self) -> None:
        messages = _build_merge_prompt("How to scale?", _sample_results())
        assert "How to scale?" in messages[1].content

    def test_user_includes_subtask_results(self) -> None:
        results = _sample_results()
        messages = _build_merge_prompt("Question?", results)
        user = messages[1].content
        for r in results:
            assert r.label in user
            assert r.decision in user

    def test_system_mentions_synthesis(self) -> None:
        messages = _build_merge_prompt("Question?", _sample_results())
        sys_lower = messages[0].content.lower()
        assert "synthesize" in sys_lower or "combine" in sys_lower


# ── Prioritize prompt building ─────────────────────────────────


class TestBuildPrioritizePrompt:
    def test_returns_system_and_user(self) -> None:
        messages = _build_prioritize_prompt("Question?", _sample_results())
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_system_mentions_confidence(self) -> None:
        messages = _build_prioritize_prompt("Question?", _sample_results())
        assert "confidence" in messages[0].content.lower()

    def test_user_includes_all_results(self) -> None:
        results = _sample_results()
        messages = _build_prioritize_prompt("Question?", results)
        user = messages[1].content
        for r in results:
            assert r.label in user

    def test_results_ordered_by_confidence_desc(self) -> None:
        results = _sample_results()
        messages = _build_prioritize_prompt("Question?", results)
        user = messages[1].content
        # "research" (0.9) should appear before "compare" (0.75)
        assert user.index("research") < user.index("compare")


# ── Synthesize function ────────────────────────────────────────


class TestSynthesize:
    async def test_merge_strategy(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"synthesizer": "Comprehensive final answer."},
        )
        pm = ProviderManager()
        await pm.register(provider)

        result = await synthesize(
            "What database?",
            _sample_results(),
            pm,
            strategy="merge",
        )

        assert isinstance(result, SynthesisResult)
        assert "Comprehensive" in result.content
        assert result.strategy == "merge"
        assert result.confidence == pytest.approx((0.9 + 0.75 + 0.85) / 3)

    async def test_prioritize_strategy(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"synthesizer": "Prioritized answer."},
        )
        pm = ProviderManager()
        await pm.register(provider)

        result = await synthesize(
            "What database?",
            _sample_results(),
            pm,
            strategy="prioritize",
        )

        assert result.strategy == "prioritize"
        assert "Prioritized" in result.content

    async def test_confidence_is_average(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"synthesizer": "Answer."},
        )
        pm = ProviderManager()
        await pm.register(provider)

        results = _sample_results()
        expected_avg = sum(r.confidence for r in results) / len(results)

        synthesis = await synthesize("Q?", results, pm)
        assert synthesis.confidence == pytest.approx(expected_avg)

    async def test_no_results_raises(self) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        with pytest.raises(ConsensusError, match="No subtask results"):
            await synthesize("Q?", [], pm)

    async def test_no_models_raises(self) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        with pytest.raises(ConsensusError, match="No models available"):
            await synthesize("Q?", _sample_results(), pm)

    async def test_uses_strongest_model(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        # Create two providers with different costs
        cheap = MockProvider(
            provider_id="cheap",
            responses={"small": "Cheap answer"},
            output_cost=1.0,
        )
        expensive = MockProvider(
            provider_id="expensive",
            responses={"big": "Expensive answer"},
            output_cost=60.0,
        )
        pm = ProviderManager()
        await pm.register(cheap)
        await pm.register(expensive)

        result = await synthesize("Q?", _sample_results(), pm)

        # Should use the expensive model
        assert "Expensive" in result.content

    async def test_records_cost(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"synthesizer": "Answer."},
            input_cost=1.0,
            output_cost=2.0,
        )
        pm = ProviderManager()
        await pm.register(provider)

        await synthesize("Q?", _sample_results(), pm)
        assert pm.total_cost > 0.0

    async def test_default_strategy_is_merge(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"synthesizer": "Answer."},
        )
        pm = ProviderManager()
        await pm.register(provider)

        result = await synthesize("Q?", _sample_results(), pm)
        assert result.strategy == "merge"
