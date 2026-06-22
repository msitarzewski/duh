"""POST /api/ask -- run consensus query via REST."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from duh.core.errors import ConsensusError, DuhError, ProviderError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["consensus"])


class RefineRequest(BaseModel):
    question: str
    max_questions: int = 4


class RefineResponse(BaseModel):
    needs_refinement: bool
    questions: list[dict[str, str | None]] = []


class EnrichRequest(BaseModel):
    original_question: str
    clarifications: list[dict[str, str]]


class EnrichResponse(BaseModel):
    enriched_question: str


class AskRequest(BaseModel):
    question: str
    protocol: str = "consensus"  # consensus, voting, auto
    rounds: int = 3
    decompose: bool = False
    tools: bool = False
    panel: list[str] | None = None
    proposer: str | None = None
    challengers: list[str] | None = None


class UsageResponse(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class AskResponse(BaseModel):
    decision: str
    confidence: float
    rigor: float = 0.0
    dissent: str | None = None
    cost: float
    usage: UsageResponse = UsageResponse()
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
    tool_registry = getattr(request.app.state, "tool_registry", None)

    try:
        if body.decompose:
            return await _handle_decompose(body, config, pm)

        if body.protocol == "voting":
            return await _handle_voting(body, config, pm)

        # Default: consensus
        return await _handle_consensus(body, config, pm, db_factory, tool_registry)

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
    body: AskRequest, config, pm, db_factory=None, tool_registry=None
) -> AskResponse:
    """Run the consensus protocol."""
    from duh.cli.app import _run_consensus

    use_native_search = config.tools.enabled and config.tools.web_search.native

    # Persist the full debate via the shared incremental path (same as CLI/WS),
    # capturing the thread ID it creates up front. Replaces the old lite path
    # that only saved the final decision.
    created: dict[str, str] = {}
    (
        decision,
        confidence,
        rigor,
        dissent,
        cost,
        _overview,
        _citations,
        _followups,
    ) = await _run_consensus(
        body.question,
        config,
        pm,
        tool_registry=tool_registry,
        panel=body.panel,
        proposer_override=body.proposer,
        challengers_override=body.challengers,
        web_search=use_native_search,
        db_factory=db_factory,
        on_thread_created=lambda tid: created.__setitem__("id", tid),
    )
    thread_id: str | None = created.get("id")

    return AskResponse(
        decision=decision,
        confidence=confidence,
        rigor=rigor,
        dissent=dissent,
        cost=cost,
        usage=UsageResponse(
            input_tokens=pm.total_input_tokens,
            output_tokens=pm.total_output_tokens,
            cost_usd=cost,
        ),
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
        rigor=result.rigor,
        cost=pm.total_cost,
        usage=UsageResponse(
            input_tokens=pm.total_input_tokens,
            output_tokens=pm.total_output_tokens,
            cost_usd=pm.total_cost,
        ),
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

        (
            decision,
            confidence,
            rigor,
            dissent,
            cost,
            _overview,
            _citations,
            _followups,
        ) = await _run_consensus(body.question, config, pm)
        return AskResponse(
            decision=decision,
            confidence=confidence,
            rigor=rigor,
            dissent=dissent,
            cost=cost,
            protocol_used="decompose",
        )

    subtask_results = await schedule_subtasks(subtask_specs, body.question, config, pm)

    synthesis_result = await synthesize(body.question, subtask_results, pm)

    return AskResponse(
        decision=synthesis_result.content,
        confidence=synthesis_result.confidence,
        rigor=synthesis_result.rigor,
        cost=pm.total_cost,
        protocol_used="decompose",
    )


@router.post("/refine", response_model=RefineResponse)
async def refine(body: RefineRequest, request: Request) -> RefineResponse:
    """Analyze a question for ambiguity and suggest clarifications."""
    from duh.consensus.refine import analyze_question

    pm = request.app.state.provider_manager
    result = await analyze_question(body.question, pm, max_questions=body.max_questions)
    return RefineResponse(
        needs_refinement=result.get("needs_refinement", False),
        questions=result.get("questions", []),
    )


@router.post("/enrich", response_model=EnrichResponse)
async def enrich(body: EnrichRequest, request: Request) -> EnrichResponse:
    """Rewrite a question incorporating clarification answers."""
    from duh.consensus.refine import enrich_question

    pm = request.app.state.provider_manager
    enriched = await enrich_question(body.original_question, body.clarifications, pm)
    return EnrichResponse(enriched_question=enriched)
