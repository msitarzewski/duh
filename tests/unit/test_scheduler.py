"""Tests for the subtask scheduler: topological ordering, parallel execution."""

from __future__ import annotations

import pytest

from duh.config.schema import DuhConfig
from duh.consensus.machine import SubtaskSpec
from duh.consensus.scheduler import (
    SubtaskResult,
    _execute_subtask,
    _run_mini_consensus,
    schedule_subtasks,
)
from duh.core.errors import ConsensusError

# ── Helpers ──────────────────────────────────────────────────────


def _make_config(*, parallel: bool = True) -> DuhConfig:
    """Create a DuhConfig with decompose settings."""
    config = DuhConfig()
    config.decompose.parallel = parallel
    return config


def _linear_subtasks() -> list[SubtaskSpec]:
    """A -> B -> C linear dependency chain."""
    return [
        SubtaskSpec("a", "Step A", []),
        SubtaskSpec("b", "Step B", ["a"]),
        SubtaskSpec("c", "Step C", ["b"]),
    ]


def _parallel_subtasks() -> list[SubtaskSpec]:
    """A and B independent, C depends on both."""
    return [
        SubtaskSpec("a", "Step A", []),
        SubtaskSpec("b", "Step B", []),
        SubtaskSpec("c", "Step C", ["a", "b"]),
    ]


def _all_independent() -> list[SubtaskSpec]:
    """Three fully independent subtasks."""
    return [
        SubtaskSpec("a", "Step A", []),
        SubtaskSpec("b", "Step B", []),
        SubtaskSpec("c", "Step C", []),
    ]


# ── SubtaskResult dataclass ─────────────────────────────────────


class TestSubtaskResult:
    def test_creation(self) -> None:
        r = SubtaskResult(label="test", decision="Answer", confidence=0.85)
        assert r.label == "test"
        assert r.decision == "Answer"
        assert r.confidence == pytest.approx(0.85)


# ── Mini consensus ──────────────────────────────────────────────


class TestRunMiniConsensus:
    async def test_returns_decision_and_confidence(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        decision, confidence = await _run_mini_consensus(
            "What database should I use?", pm
        )
        assert isinstance(decision, str)
        assert len(decision) > 0
        assert 0.0 <= confidence <= 1.0

    async def test_runs_all_four_phases(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        await _run_mini_consensus("Test question", pm)

        # At least 4 calls: propose + 2 challengers + revise
        assert len(provider.call_log) >= 4


# ── Execute subtask ─────────────────────────────────────────────


class TestExecuteSubtask:
    async def test_builds_augmented_question(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        subtask = SubtaskSpec("test", "Analyze the options", [])
        result = await _execute_subtask(subtask, "Original question", pm, {})
        assert result.label == "test"
        assert isinstance(result.decision, str)

    async def test_includes_dependency_context(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        prior = {
            "research": SubtaskResult(
                label="research",
                decision="Found three options",
                confidence=0.8,
            )
        }
        subtask = SubtaskSpec("compare", "Compare options", ["research"])
        result = await _execute_subtask(subtask, "Original question", pm, prior)
        assert result.label == "compare"

        # Verify the prompt included dependency context
        first_call = provider.call_log[0]
        user_msg = first_call["messages"][1].content
        assert "Found three options" in user_msg


# ── Schedule subtasks ───────────────────────────────────────────


class TestScheduleSubtasks:
    async def test_linear_order(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        config = _make_config(parallel=False)
        results = await schedule_subtasks(
            _linear_subtasks(), "Test question", config, pm
        )

        assert len(results) == 3
        labels = [r.label for r in results]
        # a must come before b, b before c
        assert labels.index("a") < labels.index("b")
        assert labels.index("b") < labels.index("c")

    async def test_parallel_independent(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        config = _make_config(parallel=True)
        results = await schedule_subtasks(
            _parallel_subtasks(), "Test question", config, pm
        )

        assert len(results) == 3
        labels = [r.label for r in results]
        # c must come after both a and b
        assert labels.index("c") > labels.index("a")
        assert labels.index("c") > labels.index("b")

    async def test_all_independent_parallel(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        config = _make_config(parallel=True)
        results = await schedule_subtasks(
            _all_independent(), "Test question", config, pm
        )

        assert len(results) == 3
        # All should complete
        labels = {r.label for r in results}
        assert labels == {"a", "b", "c"}

    async def test_sequential_mode(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        config = _make_config(parallel=False)
        results = await schedule_subtasks(
            _all_independent(), "Test question", config, pm
        )

        # All complete even without parallelism
        assert len(results) == 3

    async def test_empty_subtasks_raises(self) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        config = _make_config()
        with pytest.raises(ConsensusError, match="No subtasks"):
            await schedule_subtasks([], "Test", config, pm)

    async def test_results_have_correct_labels(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        config = _make_config()
        results = await schedule_subtasks(_linear_subtasks(), "Test", config, pm)

        result_labels = {r.label for r in results}
        assert result_labels == {"a", "b", "c"}

    async def test_results_have_decisions(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        config = _make_config()
        results = await schedule_subtasks(_linear_subtasks(), "Test", config, pm)

        for result in results:
            assert isinstance(result.decision, str)
            assert len(result.decision) > 0
            assert 0.0 <= result.confidence <= 1.0

    async def test_diamond_dependency(self) -> None:
        """Diamond: A -> B, A -> C, B+C -> D."""
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider
        from tests.fixtures.responses import CONSENSUS_BASIC

        provider = MockProvider(provider_id="mock", responses=CONSENSUS_BASIC)
        pm = ProviderManager()
        await pm.register(provider)

        subtasks = [
            SubtaskSpec("a", "Root", []),
            SubtaskSpec("b", "Left", ["a"]),
            SubtaskSpec("c", "Right", ["a"]),
            SubtaskSpec("d", "Merge", ["b", "c"]),
        ]
        config = _make_config(parallel=True)
        results = await schedule_subtasks(subtasks, "Test", config, pm)

        labels = [r.label for r in results]
        assert labels.index("a") < labels.index("b")
        assert labels.index("a") < labels.index("c")
        assert labels.index("b") < labels.index("d")
        assert labels.index("c") < labels.index("d")
