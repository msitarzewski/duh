"""WebSocket /ws/ask -- real-time consensus streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from duh.api.auth import authenticate_connection

if TYPE_CHECKING:
    from duh.config.schema import DuhConfig
    from duh.consensus.machine import ChallengeResult, ConsensusContext
    from duh.providers.base import ModelResponse
    from duh.providers.manager import ProviderManager
    from duh.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


class WebSocketAskRequest(BaseModel):
    """Bound the authenticated first message before starting paid provider work."""

    question: str = Field(min_length=1, max_length=20_000)
    rounds: int = Field(default=3, ge=1, le=10, strict=True)
    panel: list[str] | None = Field(default=None, max_length=20)
    proposer: str | None = Field(default=None, max_length=200)
    challengers: list[str] | None = Field(default=None, max_length=20)
    token: str | None = Field(default=None, max_length=16_384)
    api_key: str | None = Field(default=None, max_length=512)


@router.websocket("/ws/ask")
async def ws_ask(websocket: WebSocket) -> None:
    """Stream consensus phases over WebSocket.

    Client sends::

        {"question": "...", "rounds": 3, "protocol": "consensus"}

    Server streams events::

        {"type": "phase_start", "phase": "PROPOSE",
         "model": "anthropic:claude-opus-4-6"}
        {"type": "phase_complete", "phase": "PROPOSE",
         "content": "...full..."}
        {"type": "phase_start", "phase": "CHALLENGE",
         "models": ["openai:gpt-5.2", ...]}
        {"type": "challenge", "model": "...", "content": "..."}
        {"type": "phase_complete", "phase": "CHALLENGE"}
        {"type": "phase_start", "phase": "REVISE",
         "model": "anthropic:claude-opus-4-6"}
        {"type": "phase_complete", "phase": "REVISE",
         "content": "..."}
        {"type": "commit", "confidence": 0.85, "dissent": "..."}
        {"type": "complete", "decision": "...",
         "confidence": 0.85, "cost": 0.04}
        {"type": "error", "message": "..."}
    """
    await websocket.accept()

    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        if len(raw.encode("utf-8")) > 65_536:
            raise ValueError("Request too large")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Expected a request object")
        if not isinstance(data.get("question"), str) or not data["question"].strip():
            raise ValueError("Missing question")
        body = WebSocketAskRequest.model_validate(data)
        await authenticate_connection(websocket, token=body.token, api_key=body.api_key)
        question = body.question.strip()
        panel = body.panel or None
        proposer_override = body.proposer
        challengers_raw = body.challengers or None

        config: DuhConfig = websocket.app.state.config.model_copy(deep=True)
        pm: ProviderManager = websocket.app.state.provider_manager
        config.general.max_rounds = body.rounds

        tool_registry = getattr(websocket.app.state, "tool_registry", None)

        await _stream_consensus(
            websocket,
            question,
            config,
            pm,
            panel=panel,
            proposer_override=proposer_override,
            challengers_override=challengers_raw,
            tool_registry=tool_registry,
        )

    except WebSocketDisconnect:
        pass
    except (HTTPException, ValidationError, ValueError, TimeoutError) as exc:
        message = exc.detail if isinstance(exc, HTTPException) else "Invalid request"
        if isinstance(exc, ValueError) and str(exc) == "Missing question":
            message = "Missing question"
        await websocket.send_json({"type": "error", "message": message})
        await websocket.close(code=1008)
    except Exception:
        logger.exception("WebSocket error during /ws/ask")
        try:
            await websocket.send_json(
                {"type": "error", "message": "Consensus failed. Please try again."}
            )
            await websocket.close()
        except Exception:
            pass


async def _stream_consensus(
    ws: WebSocket,
    question: str,
    config: DuhConfig,
    pm: ProviderManager,
    *,
    panel: list[str] | None = None,
    proposer_override: str | None = None,
    challengers_override: list[str] | None = None,
    tool_registry: ToolRegistry | None = None,
) -> None:
    """Adapt shared engine events and incremental persistence to WebSocket IO."""
    from duh.consensus.engine import ConsensusEvent, EngineOptions
    from duh.memory.persist import run_persisted_consensus

    async def consume(event: ConsensusEvent) -> None:
        await ws.send_json(event.to_wire())

    async def thread_created(thread_id: str) -> None:
        await ws.send_json({"type": "thread_started", "thread_id": thread_id})

    await run_persisted_consensus(
        question,
        config,
        pm,
        options=EngineOptions(
            panel=tuple(panel) if panel else None,
            proposer=proposer_override,
            challengers=tuple(challengers_override) if challengers_override else None,
            web_search=config.tools.enabled and config.tools.web_search.native,
        ),
        tool_registry=tool_registry,
        emit=consume,
        db_factory=getattr(ws.app.state, "db_factory", None),
        on_thread_created=thread_created,
    )
    await ws.close()


async def _stream_challenges(
    ws: WebSocket,
    ctx: ConsensusContext,
    pm: ProviderManager,
    challengers: list[str],
    *,
    tool_registry: ToolRegistry | None = None,
    web_search: bool = False,
) -> None:
    """Compatibility adapter for the shared challenge handler."""
    from duh.consensus.handlers import handle_challenge

    async def on_result(challenge: ChallengeResult, response: ModelResponse) -> None:
        await ws.send_json(
            {
                "type": "challenge",
                "model": challenge.model_ref,
                "content": challenge.content,
                "truncated": response.finish_reason != "stop",
                "citations": list(challenge.citations) or None,
            }
        )

    async def on_error(model: str) -> None:
        await ws.send_json({"type": "challenge_error", "model": model})

    await handle_challenge(
        ctx,
        pm,
        challengers,
        tool_registry=tool_registry,
        web_search=web_search,
        on_result=on_result,
        on_error=on_error,
    )
