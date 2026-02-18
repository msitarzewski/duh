"""POST /api/ask -- run consensus query via REST."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from duh.core.errors import ConsensusError, DuhError, ProviderError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["consensus"])


class AskRequest(BaseModel):
    question: str
    protocol: str = "consensus"  # consensus, voting, auto
    rounds: int = 3
    decompose: bool = False
    tools: bool = False
    panel: list[str] | None = None
    proposer: str | None = None
    challengers: list[str] | None = None


class AskResponse(BaseModel):
    decision: str
    confidence: float
    dissent: str | None = None
    cost: float
    thread_id: str | None = None
    protocol_used: str = "consensus"


@router.post("/ask", response_model=AskResponse)
async def ask(body: AskRequest, request: Request) -> AskResponse | JSONResponse:
    """Run a consensus query."""
    config = request.app.state.config
    pm = request.app.state.provider_manager

    # Override config from request
    config.general.max_rounds = body.rounds

    db_factory = getattr(request.app.state, "db_factory", None)

    try:
        if body.decompose:
            return await _handle_decompose(body, config, pm)

        if body.protocol == "voting":
            return await _handle_voting(body, config, pm)

        # Default: consensus
        return await _handle_consensus(body, config, pm, db_factory)

    except ProviderError as exc:
        logger.exception("Provider error during /api/ask")
        return JSONResponse(
            status_code=503,
            content={"detail": f"Provider error: {exc}"},
        )
    except ConsensusError as exc:
        logger.exception("Consensus error during /api/ask")
        return JSONResponse(
            status_code=502,
            content={"detail": f"Consensus error: {exc}"},
        )
    except DuhError as exc:
        logger.exception("Error during /api/ask")
        return JSONResponse(
            status_code=400,
            content={"detail": str(exc)},
        )


async def _handle_consensus(  # type: ignore[no-untyped-def]
    body: AskRequest, config, pm, db_factory=None
) -> AskResponse:
    """Run the consensus protocol."""
    from duh.cli.app import _run_consensus

    decision, confidence, dissent, cost = await _run_consensus(
        body.question,
        config,
        pm,
        panel=body.panel,
        proposer_override=body.proposer,
        challengers_override=body.challengers,
    )

    thread_id: str | None = None
    if db_factory is not None:
        try:
            thread_id = await _persist_result(
                db_factory, body.question, decision, confidence, dissent
            )
        except Exception:
            logger.exception("Failed to persist consensus thread")

    return AskResponse(
        decision=decision,
        confidence=confidence,
        dissent=dissent,
        cost=cost,
        thread_id=thread_id,
        protocol_used="consensus",
    )


async def _handle_voting(body: AskRequest, config, pm) -> AskResponse:  # type: ignore[no-untyped-def]
    """Run the voting protocol."""
    from duh.consensus.voting import run_voting

    result = await run_voting(body.question, pm, aggregation=config.voting.aggregation)
    return AskResponse(
        decision=result.decision,
        confidence=result.confidence,
        cost=pm.total_cost,
        protocol_used="voting",
    )


async def _handle_decompose(body: AskRequest, config, pm) -> AskResponse:  # type: ignore[no-untyped-def]
    """Run the decompose protocol."""
    from duh.consensus.decompose import handle_decompose
    from duh.consensus.machine import (
        ConsensusContext,
        ConsensusState,
        ConsensusStateMachine,
    )
    from duh.consensus.scheduler import schedule_subtasks
    from duh.consensus.synthesis import synthesize

    ctx = ConsensusContext(
        thread_id="",
        question=body.question,
        max_rounds=config.general.max_rounds,
    )
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.DECOMPOSE)

    subtask_specs = await handle_decompose(
        ctx, pm, max_subtasks=config.decompose.max_subtasks
    )

    # Single-subtask optimization: run normal consensus
    if len(subtask_specs) == 1:
        from duh.cli.app import _run_consensus

        decision, confidence, dissent, cost = await _run_consensus(
            body.question, config, pm
        )
        return AskResponse(
            decision=decision,
            confidence=confidence,
            dissent=dissent,
            cost=cost,
            protocol_used="decompose",
        )

    subtask_results = await schedule_subtasks(subtask_specs, body.question, config, pm)

    synthesis_result = await synthesize(body.question, subtask_results, pm)

    return AskResponse(
        decision=synthesis_result.content,
        confidence=synthesis_result.confidence,
        cost=pm.total_cost,
        protocol_used="decompose",
    )


async def _persist_result(
    db_factory: object,
    question: str,
    decision: str,
    confidence: float,
    dissent: str | None,
) -> str:
    """Persist a consensus result to the database.

    Returns the new thread ID.
    """
    from duh.memory.repository import MemoryRepository

    async with db_factory() as session:  # type: ignore[operator]
        repo = MemoryRepository(session)
        thread = await repo.create_thread(question)
        thread.status = "complete"
        turn = await repo.create_turn(thread.id, 1, "COMMIT")
        await repo.save_decision(
            turn.id, thread.id, decision, confidence, dissent=dissent
        )
        await session.commit()
        return str(thread.id)
