"""Tests for the DECOMPOSE state, handler, prompt building, and DAG validation."""

from __future__ import annotations

import json

import pytest

from duh.consensus.decompose import (
    _parse_subtasks,
    build_decompose_prompt,
    handle_decompose,
    validate_subtask_dag,
)
from duh.consensus.machine import (
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
    SubtaskSpec,
)
from duh.core.errors import ConsensusError

# ── Helpers ──────────────────────────────────────────────────────


def _make_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context with sensible defaults."""
    defaults: dict[str, object] = {
        "thread_id": "t-decompose",
        "question": (
            "How should I design a microservices architecture"
            " for an e-commerce platform?"
        ),
        "max_rounds": 3,
    }
    defaults.update(kwargs)
    return ConsensusContext(**defaults)  # type: ignore[arg-type]


def _decompose_ctx(**kwargs: object) -> ConsensusContext:
    """Create a context already in DECOMPOSE state."""
    ctx = _make_ctx(**kwargs)
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.DECOMPOSE)
    return ctx


def _valid_subtask_json(subtasks: list[dict[str, object]]) -> str:
    """Build a valid JSON string from subtask dicts."""
    return json.dumps({"subtasks": subtasks})


VALID_DAG_JSON = _valid_subtask_json(
    [
        {
            "label": "research",
            "description": "Research available options",
            "dependencies": [],
        },
        {
            "label": "compare",
            "description": "Compare the options",
            "dependencies": ["research"],
        },
        {
            "label": "recommend",
            "description": "Make a recommendation",
            "dependencies": ["compare"],
        },
    ]
)


# ── State transitions ───────────────────────────────────────────


class TestDecomposeTransitions:
    def test_idle_to_decompose_valid(self) -> None:
        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.DECOMPOSE)
        assert sm.state == ConsensusState.DECOMPOSE

    def test_decompose_to_propose_valid(self) -> None:
        ctx = _decompose_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.PROPOSE)
        assert sm.state == ConsensusState.PROPOSE
        assert ctx.current_round == 1

    def test_idle_to_decompose_empty_question_fails(self) -> None:
        ctx = _make_ctx(question="")
        sm = ConsensusStateMachine(ctx)
        with pytest.raises(ConsensusError, match="question is empty"):
            sm.transition(ConsensusState.DECOMPOSE)

    def test_idle_to_decompose_whitespace_question_fails(self) -> None:
        ctx = _make_ctx(question="   ")
        sm = ConsensusStateMachine(ctx)
        with pytest.raises(ConsensusError, match="question is empty"):
            sm.transition(ConsensusState.DECOMPOSE)

    def test_decompose_not_reachable_from_propose(self) -> None:
        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.transition(ConsensusState.PROPOSE)
        with pytest.raises(ConsensusError, match="Invalid transition"):
            sm.transition(ConsensusState.DECOMPOSE)

    def test_can_fail_from_decompose(self) -> None:
        ctx = _decompose_ctx()
        sm = ConsensusStateMachine(ctx)
        sm.fail("decompose error")
        assert sm.state == ConsensusState.FAILED
        assert ctx.error == "decompose error"

    def test_idle_valid_transitions_includes_decompose(self) -> None:
        ctx = _make_ctx()
        sm = ConsensusStateMachine(ctx)
        valid = sm.valid_transitions()
        assert ConsensusState.DECOMPOSE in valid
        assert ConsensusState.PROPOSE in valid


# ── Prompt building ─────────────────────────────────────────────


class TestBuildDecomposePrompt:
    def test_returns_system_and_user(self) -> None:
        messages = build_decompose_prompt("What is AI?")
        assert len(messages) == 2
        assert messages[0].role == "system"
        assert messages[1].role == "user"

    def test_user_includes_question(self) -> None:
        messages = build_decompose_prompt("What is the meaning of life?")
        assert "What is the meaning of life?" in messages[1].content

    def test_system_requests_json(self) -> None:
        messages = build_decompose_prompt("Test question")
        assert "JSON" in messages[0].content

    def test_system_mentions_max_subtasks(self) -> None:
        messages = build_decompose_prompt("Test question", max_subtasks=5)
        assert "5" in messages[0].content

    def test_system_mentions_dependencies(self) -> None:
        messages = build_decompose_prompt("Test question")
        assert "dependencies" in messages[0].content.lower()

    def test_system_mentions_dag(self) -> None:
        messages = build_decompose_prompt("Test question")
        assert "acyclic" in messages[0].content.lower()


# ── DAG validation ──────────────────────────────────────────────


class TestValidateSubtaskDag:
    def test_valid_linear_dag(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", []),
            SubtaskSpec("b", "Step B", ["a"]),
            SubtaskSpec("c", "Step C", ["b"]),
        ]
        validate_subtask_dag(subtasks)  # Should not raise

    def test_valid_parallel_dag(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", []),
            SubtaskSpec("b", "Step B", []),
            SubtaskSpec("c", "Step C", ["a", "b"]),
        ]
        validate_subtask_dag(subtasks)  # Should not raise

    def test_too_few_subtasks(self) -> None:
        subtasks = [SubtaskSpec("a", "Only one", [])]
        with pytest.raises(ConsensusError, match="Too few subtasks"):
            validate_subtask_dag(subtasks)

    def test_too_many_subtasks(self) -> None:
        subtasks = [SubtaskSpec(f"s{i}", f"Step {i}", []) for i in range(8)]
        with pytest.raises(ConsensusError, match="Too many subtasks"):
            validate_subtask_dag(subtasks)

    def test_too_many_custom_max(self) -> None:
        subtasks = [SubtaskSpec(f"s{i}", f"Step {i}", []) for i in range(4)]
        with pytest.raises(ConsensusError, match="Too many subtasks"):
            validate_subtask_dag(subtasks, max_subtasks=3)

    def test_self_dependency_detected(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", ["a"]),
            SubtaskSpec("b", "Step B", []),
        ]
        with pytest.raises(ConsensusError, match="self-dependency"):
            validate_subtask_dag(subtasks)

    def test_cycle_a_b_a_detected(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", ["b"]),
            SubtaskSpec("b", "Step B", ["a"]),
        ]
        with pytest.raises(ConsensusError, match=r"[Cc]ycle"):
            validate_subtask_dag(subtasks)

    def test_longer_cycle_detected(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", ["c"]),
            SubtaskSpec("b", "Step B", ["a"]),
            SubtaskSpec("c", "Step C", ["b"]),
        ]
        with pytest.raises(ConsensusError, match=r"[Cc]ycle"):
            validate_subtask_dag(subtasks)

    def test_missing_dependency_reference(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", []),
            SubtaskSpec("b", "Step B", ["nonexistent"]),
        ]
        with pytest.raises(ConsensusError, match="unknown label"):
            validate_subtask_dag(subtasks)

    def test_duplicate_labels(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", []),
            SubtaskSpec("a", "Step A duplicate", []),
        ]
        with pytest.raises(ConsensusError, match="Duplicate"):
            validate_subtask_dag(subtasks)

    def test_exactly_two_subtasks_valid(self) -> None:
        subtasks = [
            SubtaskSpec("a", "Step A", []),
            SubtaskSpec("b", "Step B", ["a"]),
        ]
        validate_subtask_dag(subtasks)  # Should not raise

    def test_exactly_max_subtasks_valid(self) -> None:
        subtasks = [SubtaskSpec(f"s{i}", f"Step {i}", []) for i in range(7)]
        validate_subtask_dag(subtasks, max_subtasks=7)  # Should not raise


# ── JSON parsing ────────────────────────────────────────────────


class TestParseSubtasks:
    def test_valid_json_parsed(self) -> None:
        data = {
            "subtasks": [
                {"label": "a", "description": "Do A", "dependencies": []},
                {"label": "b", "description": "Do B", "dependencies": ["a"]},
            ]
        }
        result = _parse_subtasks(data)
        assert len(result) == 2
        assert result[0].label == "a"
        assert result[0].description == "Do A"
        assert result[0].dependencies == []
        assert result[1].label == "b"
        assert result[1].dependencies == ["a"]

    def test_missing_subtasks_key(self) -> None:
        with pytest.raises(ConsensusError, match="subtasks"):
            _parse_subtasks({"other": "data"})

    def test_subtasks_not_a_list(self) -> None:
        with pytest.raises(ConsensusError, match="subtasks"):
            _parse_subtasks({"subtasks": "not a list"})

    def test_subtask_not_a_dict(self) -> None:
        with pytest.raises(ConsensusError, match="not a JSON object"):
            _parse_subtasks({"subtasks": ["not a dict"]})

    def test_missing_label(self) -> None:
        data = {"subtasks": [{"description": "No label", "dependencies": []}]}
        with pytest.raises(ConsensusError, match="label"):
            _parse_subtasks(data)

    def test_missing_description(self) -> None:
        data = {"subtasks": [{"label": "a", "dependencies": []}]}
        with pytest.raises(ConsensusError, match="description"):
            _parse_subtasks(data)

    def test_dependencies_defaults_to_empty(self) -> None:
        data = {"subtasks": [{"label": "a", "description": "Do A"}]}
        result = _parse_subtasks(data)
        assert result[0].dependencies == []

    def test_non_string_dependency_rejected(self) -> None:
        data = {
            "subtasks": [{"label": "a", "description": "Do A", "dependencies": [42]}]
        }
        with pytest.raises(ConsensusError, match="non-string dependency"):
            _parse_subtasks(data)


# ── Handler execution ───────────────────────────────────────────


class TestHandleDecompose:
    async def test_happy_path(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"decomposer": VALID_DAG_JSON},
        )
        pm = ProviderManager()
        await pm.register(provider)

        ctx = _decompose_ctx()
        result = await handle_decompose(ctx, pm, max_subtasks=7)

        assert len(result) == 3
        assert result[0].label == "research"
        assert result[1].label == "compare"
        assert result[2].label == "recommend"
        assert ctx.subtasks == result

    async def test_wrong_state_raises(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"decomposer": VALID_DAG_JSON},
        )
        pm = ProviderManager()
        await pm.register(provider)

        ctx = _make_ctx()  # IDLE state
        with pytest.raises(ConsensusError, match="requires DECOMPOSE state"):
            await handle_decompose(ctx, pm)

    async def test_no_models_raises(self) -> None:
        from duh.providers.manager import ProviderManager

        pm = ProviderManager()
        ctx = _decompose_ctx()
        with pytest.raises(ConsensusError, match="No models available"):
            await handle_decompose(ctx, pm)

    async def test_records_cost(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"decomposer": VALID_DAG_JSON},
            input_cost=1.0,
            output_cost=2.0,
        )
        pm = ProviderManager()
        await pm.register(provider)

        ctx = _decompose_ctx()
        await handle_decompose(ctx, pm)

        assert pm.total_cost > 0.0

    async def test_uses_json_mode(self) -> None:
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        provider = MockProvider(
            provider_id="mock",
            responses={"decomposer": VALID_DAG_JSON},
        )
        pm = ProviderManager()
        await pm.register(provider)

        ctx = _decompose_ctx()
        await handle_decompose(ctx, pm)

        call = provider.call_log[-1]
        assert call["response_format"] == "json"

    async def test_invalid_dag_from_model_raises(self) -> None:
        """Model returns valid JSON but with a cycle."""
        from duh.providers.manager import ProviderManager
        from tests.fixtures.providers import MockProvider

        cycle_json = _valid_subtask_json(
            [
                {"label": "a", "description": "A", "dependencies": ["b"]},
                {"label": "b", "description": "B", "dependencies": ["a"]},
            ]
        )
        provider = MockProvider(
            provider_id="mock",
            responses={"decomposer": cycle_json},
        )
        pm = ProviderManager()
        await pm.register(provider)

        ctx = _decompose_ctx()
        with pytest.raises(ConsensusError, match=r"[Cc]ycle"):
            await handle_decompose(ctx, pm)


# ── SubtaskSpec dataclass ──────────────────────────────────────


class TestSubtaskSpec:
    def test_creation(self) -> None:
        spec = SubtaskSpec(
            label="test", description="A test task", dependencies=["dep1"]
        )
        assert spec.label == "test"
        assert spec.description == "A test task"
        assert spec.dependencies == ["dep1"]

    def test_frozen(self) -> None:
        spec = SubtaskSpec(label="test", description="A test task")
        with pytest.raises(AttributeError):
            spec.label = "new"  # type: ignore[misc]

    def test_default_dependencies(self) -> None:
        spec = SubtaskSpec(label="test", description="A test task")
        assert spec.dependencies == []
