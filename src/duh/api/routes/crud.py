"""CRUD endpoints: recall, feedback, models, cost."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["crud"])


# -- GET /api/recall -----------------------------------------------------------


class RecallResult(BaseModel):
    thread_id: str
    question: str
    decision: str | None = None
    confidence: float | None = None


class RecallResponse(BaseModel):
    results: list[RecallResult]
    query: str


@router.get("/recall", response_model=RecallResponse)
async def recall(request: Request, query: str, limit: int = 10) -> RecallResponse:
    """Search past decisions by keyword."""
    from duh.memory.repository import MemoryRepository

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)
        threads = await repo.search(query, limit=limit)
        results = []
        for thread in threads:
            await session.refresh(thread, ["decisions"])
            entry = RecallResult(thread_id=thread.id, question=thread.question)
            if thread.decisions:
                latest = thread.decisions[-1]
                entry.decision = latest.content[:200]
                entry.confidence = latest.confidence
            results.append(entry)
    return RecallResponse(results=results, query=query)


# -- POST /api/feedback --------------------------------------------------------


class FeedbackRequest(BaseModel):
    thread_id: str
    result: str  # success, failure, partial
    notes: str | None = None


class FeedbackResponse(BaseModel):
    status: str
    thread_id: str


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(body: FeedbackRequest, request: Request) -> FeedbackResponse:
    """Record outcome for a thread's latest decision."""
    from duh.memory.repository import MemoryRepository

    if body.result not in ("success", "failure", "partial"):
        raise HTTPException(
            status_code=400, detail="result must be 'success', 'failure', or 'partial'"
        )

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)

        # Prefix matching
        resolved_id = body.thread_id
        if len(resolved_id) < 36:
            thread_list = await repo.list_threads(limit=100)
            matches = [t for t in thread_list if t.id.startswith(resolved_id)]
            if not matches:
                raise HTTPException(
                    status_code=404, detail=f"No thread matching '{body.thread_id}'"
                )
            if len(matches) > 1:
                raise HTTPException(
                    status_code=400, detail=f"Ambiguous prefix '{body.thread_id}'"
                )
            resolved_id = matches[0].id

        decisions = await repo.get_decisions(resolved_id)
        if not decisions:
            raise HTTPException(
                status_code=404,
                detail=f"No decisions for thread {resolved_id[:8]}",
            )

        latest = decisions[-1]
        await repo.save_outcome(latest.id, resolved_id, body.result, notes=body.notes)
        await session.commit()

    return FeedbackResponse(status="recorded", thread_id=resolved_id)


# -- GET /api/models -----------------------------------------------------------


class ModelInfoResponse(BaseModel):
    provider_id: str
    model_id: str
    display_name: str
    context_window: int
    max_output_tokens: int
    input_cost_per_mtok: float
    output_cost_per_mtok: float
    proposer_eligible: bool = True


class ModelsResponse(BaseModel):
    models: list[ModelInfoResponse]
    total: int


@router.get("/models", response_model=ModelsResponse)
async def models(request: Request) -> ModelsResponse:
    """List available models across all providers."""
    pm = request.app.state.provider_manager
    all_models = pm.list_all_models()
    results = [
        ModelInfoResponse(
            provider_id=m.provider_id,
            model_id=m.model_id,
            display_name=m.display_name,
            context_window=m.context_window,
            max_output_tokens=m.max_output_tokens,
            input_cost_per_mtok=m.input_cost_per_mtok,
            output_cost_per_mtok=m.output_cost_per_mtok,
            proposer_eligible=m.proposer_eligible,
        )
        for m in all_models
    ]
    return ModelsResponse(models=results, total=len(results))


# -- GET /api/cost -------------------------------------------------------------


class CostByModel(BaseModel):
    model_ref: str
    cost: float
    calls: int


class CostResponse(BaseModel):
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    by_model: list[CostByModel] = Field(default_factory=list)


@router.get("/cost", response_model=CostResponse)
async def cost(request: Request) -> CostResponse:
    """Show cost summary from stored contributions."""
    from sqlalchemy import func, select

    from duh.memory.models import Contribution

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        total_stmt = select(func.sum(Contribution.cost_usd))
        total = (await session.execute(total_stmt)).scalar() or 0.0

        in_stmt = select(func.sum(Contribution.input_tokens))
        total_in = (await session.execute(in_stmt)).scalar() or 0

        out_stmt = select(func.sum(Contribution.output_tokens))
        total_out = (await session.execute(out_stmt)).scalar() or 0

        by_model_stmt = (
            select(
                Contribution.model_ref,
                func.sum(Contribution.cost_usd),
                func.count(Contribution.id),
            )
            .group_by(Contribution.model_ref)
            .order_by(func.sum(Contribution.cost_usd).desc())
        )
        by_model = (await session.execute(by_model_stmt)).all()

    return CostResponse(
        total_cost=total,
        total_input_tokens=total_in,
        total_output_tokens=total_out,
        by_model=[
            CostByModel(model_ref=ref, cost=c, calls=n) for ref, c, n in by_model
        ],
    )


# -- GET /api/decisions/space -----------------------------------------------


class SpaceDecisionResponse(BaseModel):
    id: str
    thread_id: str
    question: str
    confidence: float
    intent: str | None = None
    category: str | None = None
    genus: str | None = None
    outcome: str | None = None
    created_at: str


class SpaceAxisMeta(BaseModel):
    categories: list[str]
    genera: list[str]


class DecisionSpaceResponse(BaseModel):
    decisions: list[SpaceDecisionResponse]
    axes: SpaceAxisMeta
    total: int


@router.get("/decisions/space", response_model=DecisionSpaceResponse)
async def decision_space(
    request: Request,
    category: str | None = None,
    genus: str | None = None,
    outcome: str | None = None,
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    since: str | None = None,
    until: str | None = None,
    search: str | None = None,
) -> DecisionSpaceResponse:
    """Get decisions for the Decision Space visualization."""
    from duh.memory.repository import MemoryRepository

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)
        decisions = await repo.get_all_decisions_for_space(
            category=category,
            genus=genus,
            outcome=outcome,
            confidence_min=confidence_min,
            confidence_max=confidence_max,
            since=since,
            until=until,
            search=search,
        )

        results = []
        all_categories: set[str] = set()
        all_genera: set[str] = set()

        for d in decisions:
            question = d.thread.question[:100] if d.thread else ""
            outcome_str = d.outcome.result if d.outcome else None

            if d.category:
                all_categories.add(d.category)
            if d.genus:
                all_genera.add(d.genus)

            results.append(
                SpaceDecisionResponse(
                    id=d.id,
                    thread_id=d.thread_id,
                    question=question,
                    confidence=d.confidence,
                    intent=d.intent,
                    category=d.category,
                    genus=d.genus,
                    outcome=outcome_str,
                    created_at=d.created_at.isoformat(),
                )
            )

    return DecisionSpaceResponse(
        decisions=results,
        axes=SpaceAxisMeta(
            categories=sorted(all_categories),
            genera=sorted(all_genera),
        ),
        total=len(results),
    )
