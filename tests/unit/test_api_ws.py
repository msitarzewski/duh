"""Tests for WebSocket /ws/ask endpoint."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from duh.api.routes.ws import router
from duh.config.schema import DuhConfig
from duh.consensus.machine import ChallengeResult
from duh.providers.base import ModelCapability, ModelInfo, ModelResponse, TokenUsage

# Patch at the source modules since _stream_consensus uses lazy imports
_HANDLERS = "duh.consensus.handlers"
_CONVERGENCE = "duh.consensus.convergence"


def _make_model_info(ref: str = "test:model-a") -> ModelInfo:
    provider_id, _, model_id = ref.partition(":")
    return ModelInfo(
        provider_id=provider_id,
        model_id=model_id,
        display_name=model_id,
        capabilities=ModelCapability.TEXT,
        context_window=128_000,
        max_output_tokens=4096,
        input_cost_per_mtok=1.0,
        output_cost_per_mtok=2.0,
    )


def _make_response(content: str = "test response") -> ModelResponse:
    return ModelResponse(
        content=content,
        model_info=_make_model_info(),
        usage=TokenUsage(input_tokens=100, output_tokens=50),
        finish_reason="stop",
        latency_ms=100.0,
    )


def _create_test_app() -> FastAPI:
    """Create a minimal FastAPI app with just the WS router."""
    app = FastAPI()
    app.state.config = DuhConfig()
    app.state.config.general.max_rounds = 1

    pm = MagicMock()
    pm.total_cost = 0.05
    pm.list_all_models.return_value = [
        _make_model_info("test:model-a"),
        _make_model_info("test:model-b"),
    ]
    pm.get_provider.return_value = (MagicMock(), "model-a")
    pm.get_model_info.return_value = _make_model_info()
    app.state.provider_manager = pm

    app.include_router(router)
    return app


def _apply_handler_patches(
    stack: ExitStack,
    *,
    proposal: str = "Test proposal",
    challenge_content: str = "Test challenge",
    revision: str = "Test revision",
    confidence: float = 0.85,
    dissent: str | None = "Minor dissent",
    converged: bool = True,
    propose_side_effect: Exception | None = None,
) -> None:
    """Apply all consensus handler patches onto an ExitStack."""

    async def mock_propose(ctx, pm, model_ref, **kwargs):
        ctx.proposal = proposal
        ctx.proposal_model = model_ref
        return _make_response(proposal)

    async def mock_challenge(ctx, pm, challengers, **kwargs):
        ctx.challenges = [
            ChallengeResult(
                model_ref=ref,
                content=challenge_content,
                sycophantic=False,
                framing="flaw",
            )
            for ref in challengers
        ]
        return [_make_response(challenge_content)]

    async def mock_revise(ctx, pm, **kwargs):
        ctx.revision = revision
        ctx.revision_model = ctx.proposal_model
        return _make_response(revision)

    async def mock_commit(ctx, *args, **kwargs):
        ctx.decision = ctx.revision
        ctx.rigor = 1.0
        ctx.confidence = confidence
        ctx.dissent = dissent

    def mock_convergence(ctx, **kwargs):
        ctx.converged = converged
        return converged

    if propose_side_effect is not None:
        propose_mock = AsyncMock(side_effect=propose_side_effect)
    else:
        propose_mock = AsyncMock(side_effect=mock_propose)

    stack.enter_context(patch(f"{_HANDLERS}.handle_propose", propose_mock))
    stack.enter_context(
        patch(
            f"{_HANDLERS}.handle_challenge",
            AsyncMock(side_effect=mock_challenge),
        )
    )
    stack.enter_context(
        patch(f"{_HANDLERS}.handle_revise", AsyncMock(side_effect=mock_revise))
    )
    stack.enter_context(
        patch(f"{_HANDLERS}.handle_commit", AsyncMock(side_effect=mock_commit))
    )
    stack.enter_context(
        patch(
            f"{_HANDLERS}.select_proposer",
            MagicMock(return_value="test:model-a"),
        )
    )
    stack.enter_context(
        patch(
            f"{_HANDLERS}.select_challengers",
            MagicMock(return_value=["test:model-b"]),
        )
    )
    stack.enter_context(
        patch(
            f"{_CONVERGENCE}.check_convergence",
            MagicMock(side_effect=mock_convergence),
        )
    )


def _collect_events(ws) -> list[dict]:
    """Read events from WebSocket until complete or error."""
    events: list[dict] = []
    while True:
        data = ws.receive_json()
        events.append(data)
        if data["type"] in ("complete", "error"):
            break
    return events


class TestWebSocketAsk:
    """Tests for /ws/ask WebSocket endpoint."""

    def test_full_consensus_lifecycle(self):
        """Connect, send question, receive all phase events, close."""
        app = _create_test_app()

        with ExitStack() as stack:
            _apply_handler_patches(stack)
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "What is the meaning of life?"})
                events = _collect_events(ws)

        types = [e["type"] for e in events]
        assert "phase_start" in types
        assert "phase_complete" in types
        assert "challenge" in types
        assert "commit" in types
        assert "complete" in types

    def test_missing_question_returns_error(self):
        """Empty question sends error event and closes."""
        app = _create_test_app()
        client = TestClient(app)
        with client.websocket_connect("/ws/ask") as ws:
            ws.send_json({"question": ""})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Missing question" in data["message"]

    def test_missing_question_key_returns_error(self):
        """No question key sends error event and closes."""
        app = _create_test_app()
        client = TestClient(app)
        with client.websocket_connect("/ws/ask") as ws:
            ws.send_json({"rounds": 3})
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Missing question" in data["message"]

    def test_phase_start_events_have_correct_structure(self):
        """phase_start events include phase, model/models, and round."""
        app = _create_test_app()

        with ExitStack() as stack:
            _apply_handler_patches(stack)
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test"})
                events = _collect_events(ws)

        phase_starts = [e for e in events if e["type"] == "phase_start"]
        phases = [e["phase"] for e in phase_starts]
        assert "PROPOSE" in phases
        assert "CHALLENGE" in phases
        assert "REVISE" in phases

        propose_start = next(e for e in phase_starts if e["phase"] == "PROPOSE")
        assert "model" in propose_start
        assert "round" in propose_start

        challenge_start = next(e for e in phase_starts if e["phase"] == "CHALLENGE")
        assert "models" in challenge_start
        assert isinstance(challenge_start["models"], list)

    def test_complete_event_has_decision_confidence_cost(self):
        """Complete event includes decision, confidence, and cost."""
        app = _create_test_app()

        with ExitStack() as stack:
            _apply_handler_patches(
                stack,
                revision="Final answer",
                confidence=0.85,
                dissent="Minor dissent",
            )
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test"})
                events = _collect_events(ws)

        complete = next(e for e in events if e["type"] == "complete")
        assert complete["decision"] == "Final answer"
        assert complete["confidence"] == 0.85
        assert complete["rigor"] == 1.0
        assert complete["dissent"] == "Minor dissent"
        assert "cost" in complete

    def test_commit_event_has_confidence_and_dissent(self):
        """Commit events include confidence score and dissent."""
        app = _create_test_app()

        with ExitStack() as stack:
            _apply_handler_patches(stack, confidence=0.9, dissent="Some dissent")
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test"})
                events = _collect_events(ws)

        commit = next(e for e in events if e["type"] == "commit")
        assert commit["confidence"] == 0.9
        assert commit["rigor"] == 1.0
        assert commit["dissent"] == "Some dissent"
        assert "round" in commit

    def test_challenge_events_have_model_and_content(self):
        """Individual challenge events include model ref and content."""
        app = _create_test_app()

        with ExitStack() as stack:
            _apply_handler_patches(stack, challenge_content="This is wrong because...")
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test"})
                events = _collect_events(ws)

        challenges = [e for e in events if e["type"] == "challenge"]
        assert len(challenges) >= 1
        assert challenges[0]["model"] == "test:model-b"
        assert challenges[0]["content"] == "This is wrong because..."

    def test_custom_rounds_parameter(self):
        """Client can specify number of rounds."""
        app = _create_test_app()

        with ExitStack() as stack:
            _apply_handler_patches(stack, converged=False)
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test", "rounds": 2})
                events = _collect_events(ws)

        propose_starts = [
            e for e in events if e["type"] == "phase_start" and e["phase"] == "PROPOSE"
        ]
        assert len(propose_starts) == 2

    def test_error_during_consensus_sends_error_event(self):
        """Exception during consensus sends error event."""
        app = _create_test_app()

        with ExitStack() as stack:
            _apply_handler_patches(
                stack,
                propose_side_effect=RuntimeError("Provider exploded"),
            )
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test"})
                # First event is phase_start for PROPOSE (sent before
                # handle_propose is called), second is the error.
                _first = ws.receive_json()
                data = ws.receive_json()
                assert data["type"] == "error"
                assert "Provider exploded" in data["message"]

    def test_defaults_to_three_rounds(self):
        """Without rounds param, defaults to 3."""
        app = _create_test_app()
        app.state.config.general.max_rounds = 3

        with ExitStack() as stack:
            _apply_handler_patches(stack, converged=False)
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test"})
                events = _collect_events(ws)

        propose_starts = [
            e for e in events if e["type"] == "phase_start" and e["phase"] == "PROPOSE"
        ]
        assert len(propose_starts) == 3

    def test_convergence_stops_early(self):
        """When convergence is detected, loop stops before max rounds."""
        app = _create_test_app()
        app.state.config.general.max_rounds = 5

        with ExitStack() as stack:
            _apply_handler_patches(stack, converged=True)
            client = TestClient(app)
            with client.websocket_connect("/ws/ask") as ws:
                ws.send_json({"question": "test", "rounds": 5})
                events = _collect_events(ws)

        propose_starts = [
            e for e in events if e["type"] == "phase_start" and e["phase"] == "PROPOSE"
        ]
        assert len(propose_starts) == 1
