"""WebSocket /ws/ask -- real-time consensus streaming."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

if TYPE_CHECKING:
    from duh.config.schema import DuhConfig
    from duh.consensus.machine import RoundResult
    from duh.providers.manager import ProviderManager
    from duh.tools.registry import ToolRegistry

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
    tool_registry: ToolRegistry | None = None,
) -> None:
    """Run consensus loop and stream events to WebSocket."""
    from duh.consensus.convergence import check_convergence
    from duh.consensus.handlers import (
        generate_overview,
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
    use_native_search = config.tools.enabled and config.tools.web_search.native

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
        propose_resp = await handle_propose(
            ctx,
            pm,
            proposer,
            tool_registry=tool_registry,
            web_search=use_native_search,
        )
        await ws.send_json(
            {
                "type": "phase_complete",
                "phase": "PROPOSE",
                "content": ctx.proposal or "",
                "truncated": propose_resp.finish_reason != "stop",
                "citations": ctx.proposal_citations or None,
            }
        )

        # CHALLENGE — fan out in parallel, stream each result as it arrives
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
        await _stream_challenges(
            ws,
            ctx,
            pm,
            challengers,
            tool_registry=tool_registry,
            web_search=use_native_search,
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
        revise_resp = await handle_revise(
            ctx, pm, tool_registry=tool_registry, web_search=use_native_search
        )
        await ws.send_json(
            {
                "type": "phase_complete",
                "phase": "REVISE",
                "content": ctx.revision or "",
                "truncated": revise_resp.finish_reason != "stop",
                "citations": ctx.revision_citations or None,
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

    # Generate executive overview and follow-up questions (best-effort)
    await generate_overview(ctx, pm)
    from duh.consensus.handlers import generate_followups

    await generate_followups(ctx, pm)

    # Persist to DB if available
    thread_id: str | None = None
    db_factory = getattr(ws.app.state, "db_factory", None)
    if db_factory is not None:
        try:
            thread_id = await _persist_consensus(
                db_factory,
                question,
                ctx.round_history,
                ctx.overview,
                followups=ctx.followups or None,
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
            "overview": ctx.overview,
            "followups": ctx.followups if ctx.followups else None,
        }
    )
    await ws.close()


async def _stream_challenges(
    ws: WebSocket,
    ctx: object,
    pm: object,
    challengers: list[str],
    *,
    tool_registry: object | None = None,
    web_search: bool = False,
) -> None:
    """Run challengers in parallel, streaming each result to WS as it arrives.

    Updates ``ctx.challenges`` with results.
    """
    import asyncio

    from duh.consensus.handlers import (
        _FRAMING_ORDER,
        _call_challenger,
        detect_sycophancy,
    )
    from duh.consensus.machine import ChallengeResult

    async def _run(idx: int, ref: str) -> tuple[int, tuple[str, str, Any]]:
        result = await _call_challenger(
            ctx,  # type: ignore[arg-type]
            pm,  # type: ignore[arg-type]
            ref,
            _FRAMING_ORDER[idx % len(_FRAMING_ORDER)],
            temperature=0.7,
            max_tokens=32768,
            tool_registry=tool_registry,  # type: ignore[arg-type]
            web_search=web_search,
        )
        return idx, result

    tasks = [asyncio.create_task(_run(i, ref)) for i, ref in enumerate(challengers)]

    challenges: list[ChallengeResult] = []

    for coro in asyncio.as_completed(tasks):
        try:
            _idx, (model_ref, framing, response) = await coro
            citation_dicts = tuple(
                {
                    "url": c.url,
                    "title": c.title,
                    "snippet": c.snippet,
                }
                for c in (response.citations or [])
            )
            ch = ChallengeResult(
                model_ref=model_ref,
                content=response.content,
                sycophantic=detect_sycophancy(response.content),
                framing=framing,
                citations=citation_dicts,
            )
            challenges.append(ch)

            # Stream to client immediately
            ch_citations = (
                [{"url": c["url"], "title": c.get("title")} for c in ch.citations]
                if ch.citations
                else None
            )
            await ws.send_json(
                {
                    "type": "challenge",
                    "model": ch.model_ref,
                    "content": ch.content,
                    "truncated": response.finish_reason != "stop",
                    "citations": ch_citations,
                }
            )
        except Exception:
            logger.warning("Challenger failed", exc_info=True)

    # Report failures
    succeeded = {ch.model_ref for ch in challenges}
    for ref in challengers:
        if ref not in succeeded:
            await ws.send_json({"type": "challenge_error", "model": ref})

    if not challenges:
        from duh.core.errors import ConsensusError

        msg = "All challengers failed"
        raise ConsensusError(msg)

    ctx.challenges = challenges  # type: ignore[attr-defined]


async def _persist_consensus(
    db_factory: object,
    question: str,
    round_history: list[RoundResult],
    overview: str | None = None,
    followups: list[str] | None = None,
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
            proposal_cit = None
            if rr.proposal_citations:
                proposal_cit = json.dumps(
                    [
                        {"url": c["url"], "title": c.get("title")}
                        for c in rr.proposal_citations
                    ]
                )
            await repo.add_contribution(
                turn.id,
                rr.proposal_model,
                "proposer",
                rr.proposal,
                citations_json=proposal_cit,
            )
            for ch in rr.challenges:
                ch_cit = None
                if ch.citations:
                    ch_cit = json.dumps(
                        [
                            {"url": c["url"], "title": c.get("title")}
                            for c in ch.citations
                        ]
                    )
                await repo.add_contribution(
                    turn.id,
                    ch.model_ref,
                    "challenger",
                    ch.content,
                    citations_json=ch_cit,
                )
            rev_cit = None
            if rr.revision_citations:
                rev_cit = json.dumps(
                    [
                        {"url": c["url"], "title": c.get("title")}
                        for c in rr.revision_citations
                    ]
                )
            await repo.add_contribution(
                turn.id,
                rr.proposal_model,
                "reviser",
                rr.revision,
                citations_json=rev_cit,
            )
            await repo.save_decision(
                turn.id,
                thread.id,
                rr.decision,
                rr.confidence,
                rigor=rr.rigor,
                dissent=rr.dissent,
            )

        if overview:
            await repo.save_thread_summary(thread.id, overview, "overview")

        if followups:
            thread.followups_json = json.dumps(followups)

        await session.commit()
        return str(thread.id)
