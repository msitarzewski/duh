"""WebSocket /ws/ask -- real-time consensus streaming."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from duh.config.schema import DuhConfig
    from duh.providers.manager import ProviderManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


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
        data = await websocket.receive_json()
        question = data.get("question", "")
        if not question:
            await websocket.send_json({"type": "error", "message": "Missing question"})
            await websocket.close()
            return

        rounds = data.get("rounds", 3)

        config: DuhConfig = websocket.app.state.config
        pm: ProviderManager = websocket.app.state.provider_manager
        config.general.max_rounds = rounds

        await _stream_consensus(websocket, question, config, pm)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.exception("WebSocket error during /ws/ask")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
            await websocket.close()
        except Exception:
            pass


async def _stream_consensus(
    ws: WebSocket,
    question: str,
    config: DuhConfig,
    pm: ProviderManager,
) -> None:
    """Run consensus loop and stream events to WebSocket."""
    from duh.consensus.convergence import check_convergence
    from duh.consensus.handlers import (
        handle_challenge,
        handle_commit,
        handle_propose,
        handle_revise,
        select_challengers,
        select_proposer,
    )
    from duh.consensus.machine import (
        ConsensusContext,
        ConsensusState,
        ConsensusStateMachine,
    )

    ctx = ConsensusContext(
        thread_id="",
        question=question,
        max_rounds=config.general.max_rounds,
    )
    sm = ConsensusStateMachine(ctx)

    for _round in range(config.general.max_rounds):
        # PROPOSE
        sm.transition(ConsensusState.PROPOSE)
        proposer = select_proposer(pm)
        await ws.send_json(
            {
                "type": "phase_start",
                "phase": "PROPOSE",
                "model": proposer,
                "round": ctx.current_round,
            }
        )
        await handle_propose(ctx, pm, proposer)
        await ws.send_json(
            {
                "type": "phase_complete",
                "phase": "PROPOSE",
                "content": ctx.proposal or "",
            }
        )

        # CHALLENGE
        sm.transition(ConsensusState.CHALLENGE)
        challengers = select_challengers(pm, proposer)
        await ws.send_json(
            {
                "type": "phase_start",
                "phase": "CHALLENGE",
                "models": challengers,
                "round": ctx.current_round,
            }
        )
        await handle_challenge(ctx, pm, challengers)
        for ch in ctx.challenges:
            await ws.send_json(
                {
                    "type": "challenge",
                    "model": ch.model_ref,
                    "content": ch.content,
                }
            )
        await ws.send_json({"type": "phase_complete", "phase": "CHALLENGE"})

        # REVISE
        sm.transition(ConsensusState.REVISE)
        reviser = ctx.proposal_model or proposer
        await ws.send_json(
            {
                "type": "phase_start",
                "phase": "REVISE",
                "model": reviser,
                "round": ctx.current_round,
            }
        )
        await handle_revise(ctx, pm)
        await ws.send_json(
            {
                "type": "phase_complete",
                "phase": "REVISE",
                "content": ctx.revision or "",
            }
        )

        # COMMIT
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx)
        await ws.send_json(
            {
                "type": "commit",
                "confidence": ctx.confidence,
                "dissent": ctx.dissent,
                "round": ctx.current_round,
            }
        )

        if check_convergence(ctx):
            break

    sm.transition(ConsensusState.COMPLETE)
    await ws.send_json(
        {
            "type": "complete",
            "decision": ctx.decision or "",
            "confidence": ctx.confidence,
            "dissent": ctx.dissent,
            "cost": pm.total_cost,
        }
    )
    await ws.close()
