"""WebSocket /ws/ask -- real-time consensus streaming."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, ValidationError

from duh.api.auth import authenticate_connection
from duh.core.errors import ProviderError

if TYPE_CHECKING:
    from duh.config.schema import DuhConfig
    from duh.memory.persist import IncrementalPersister
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

    # Persist incrementally so a mid-run disconnect/crash leaves a real
    # partial thread. Create it up front and tell the client its ID early.
    persister: IncrementalPersister | None = None
    db_factory = getattr(ws.app.state, "db_factory", None)
    if db_factory is not None:
        from duh.memory.persist import IncrementalPersister

        persister = IncrementalPersister(db_factory, question)
        try:
            thread_id_early = await persister.start()
            ctx.thread_id = thread_id_early
            await ws.send_json({"type": "thread_started", "thread_id": thread_id_early})
        except Exception:
            logger.exception("Failed to create consensus thread")
            persister = None

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
        if persister is not None:
            try:
                await persister.persist_round(ctx.snapshot_round())
            except Exception:
                logger.exception("Failed to persist consensus round")
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

    # Finalize the incrementally-persisted thread (mark complete, attach
    # overview / follow-ups / usage). The thread + all rounds are already saved.
    thread_id: str | None = ctx.thread_id or None
    if persister is not None:
        try:
            await persister.finalize(
                overview=ctx.overview,
                followups=ctx.followups or None,
                usage={
                    "input_tokens": pm.total_input_tokens,
                    "output_tokens": pm.total_output_tokens,
                    "cost_usd": pm.total_cost,
                },
            )
        except Exception:
            logger.exception("Failed to finalize consensus thread")

    await ws.send_json(
        {
            "type": "complete",
            "decision": ctx.decision or "",
            "confidence": ctx.confidence,
            "rigor": ctx.rigor,
            "dissent": ctx.dissent,
            "cost": pm.total_cost,
            "usage": {
                "input_tokens": pm.total_input_tokens,
                "output_tokens": pm.total_output_tokens,
                "cost_usd": pm.total_cost,
            },
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

    try:
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
            except ProviderError:
                logger.warning("Challenger failed", exc_info=True)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

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
