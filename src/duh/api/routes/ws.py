"""WebSocket /ws/ask -- real-time consensus streaming."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from duh.config.schema import DuhConfig
    from duh.consensus.machine import RoundResult
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
        panel: list[str] | None = data.get("panel") or None
        proposer_override: str | None = data.get("proposer") or None
        challengers_raw: list[str] | None = data.get("challengers") or None

        config: DuhConfig = websocket.app.state.config
        pm: ProviderManager = websocket.app.state.provider_manager
        config.general.max_rounds = rounds

        await _stream_consensus(
            websocket,
            question,
            config,
            pm,
            panel=panel,
            proposer_override=proposer_override,
            challengers_override=challengers_raw,
        )

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
    *,
    panel: list[str] | None = None,
    proposer_override: str | None = None,
    challengers_override: list[str] | None = None,
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

    effective_panel = panel or config.consensus.panel or None

    for _round in range(config.general.max_rounds):
        # PROPOSE
        sm.transition(ConsensusState.PROPOSE)
        proposer = proposer_override or select_proposer(pm, panel=effective_panel)
        await ws.send_json(
            {
                "type": "phase_start",
                "phase": "PROPOSE",
                "model": proposer,
                "round": ctx.current_round,
            }
        )
        propose_resp = await handle_propose(ctx, pm, proposer)
        await ws.send_json(
            {
                "type": "phase_complete",
                "phase": "PROPOSE",
                "content": ctx.proposal or "",
                "truncated": propose_resp.finish_reason != "stop",
            }
        )

        # CHALLENGE
        sm.transition(ConsensusState.CHALLENGE)
        challengers = challengers_override or select_challengers(
            pm, proposer, panel=effective_panel
        )
        await ws.send_json(
            {
                "type": "phase_start",
                "phase": "CHALLENGE",
                "models": challengers,
                "round": ctx.current_round,
            }
        )
        challenge_resps = await handle_challenge(ctx, pm, challengers)
        for i, ch in enumerate(ctx.challenges):
            resp_truncated = (
                i < len(challenge_resps) and challenge_resps[i].finish_reason != "stop"
            )
            await ws.send_json(
                {
                    "type": "challenge",
                    "model": ch.model_ref,
                    "content": ch.content,
                    "truncated": resp_truncated,
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
        revise_resp = await handle_revise(ctx, pm)
        await ws.send_json(
            {
                "type": "phase_complete",
                "phase": "REVISE",
                "content": ctx.revision or "",
                "truncated": revise_resp.finish_reason != "stop",
            }
        )

        # COMMIT
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx, pm)
        await ws.send_json(
            {
                "type": "commit",
                "confidence": ctx.confidence,
                "rigor": ctx.rigor,
                "dissent": ctx.dissent,
                "round": ctx.current_round,
            }
        )

        if check_convergence(ctx):
            break

    sm.transition(ConsensusState.COMPLETE)

    # Persist to DB if available
    thread_id: str | None = None
    db_factory = getattr(ws.app.state, "db_factory", None)
    if db_factory is not None:
        try:
            thread_id = await _persist_consensus(
                db_factory, question, ctx.round_history
            )
        except Exception:
            logger.exception("Failed to persist consensus thread")

    await ws.send_json(
        {
            "type": "complete",
            "decision": ctx.decision or "",
            "confidence": ctx.confidence,
            "rigor": ctx.rigor,
            "dissent": ctx.dissent,
            "cost": pm.total_cost,
            "thread_id": thread_id,
        }
    )
    await ws.close()


async def _persist_consensus(
    db_factory: object,
    question: str,
    round_history: list[RoundResult],
) -> str:
    """Persist consensus round history to the database.

    Returns the new thread ID.
    """
    from duh.memory.repository import MemoryRepository

    async with db_factory() as session:  # type: ignore[operator]
        repo = MemoryRepository(session)
        thread = await repo.create_thread(question)
        thread.status = "complete"

        for rr in round_history:
            turn = await repo.create_turn(thread.id, rr.round_number, "COMMIT")
            await repo.add_contribution(
                turn.id, rr.proposal_model, "proposer", rr.proposal
            )
            for ch in rr.challenges:
                await repo.add_contribution(
                    turn.id, ch.model_ref, "challenger", ch.content
                )
            await repo.add_contribution(
                turn.id, rr.proposal_model, "reviser", rr.revision
            )
            await repo.save_decision(
                turn.id,
                thread.id,
                rr.decision,
                rr.confidence,
                rigor=rr.rigor,
                dissent=rr.dissent,
            )

        await session.commit()
        return str(thread.id)
