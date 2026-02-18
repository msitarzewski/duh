"""GET /api/threads — list, detail, and export endpoints."""

from __future__ import annotations

import io

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api", tags=["threads"])


class ContributionResponse(BaseModel):
    model_ref: str
    role: str
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class DecisionResponse(BaseModel):
    content: str
    confidence: float
    rigor: float = 0.0
    dissent: str | None = None


class TurnResponse(BaseModel):
    round_number: int
    state: str
    contributions: list[ContributionResponse] = Field(default_factory=list)
    decision: DecisionResponse | None = None


class ThreadSummaryResponse(BaseModel):
    thread_id: str
    question: str
    status: str
    created_at: str


class ThreadDetailResponse(BaseModel):
    thread_id: str
    question: str
    status: str
    created_at: str
    turns: list[TurnResponse] = Field(default_factory=list)


class ThreadListResponse(BaseModel):
    threads: list[ThreadSummaryResponse]
    total: int


@router.get("/threads", response_model=ThreadListResponse)
async def list_threads(
    request: Request,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> ThreadListResponse:
    """List past consensus threads."""
    from duh.memory.repository import MemoryRepository

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)
        threads = await repo.list_threads(status=status, limit=limit, offset=offset)
        results = [
            ThreadSummaryResponse(
                thread_id=t.id,
                question=t.question,
                status=t.status,
                created_at=t.created_at.isoformat(),
            )
            for t in threads
        ]
    return ThreadListResponse(threads=results, total=len(results))


@router.get("/threads/{thread_id}", response_model=ThreadDetailResponse)
async def get_thread(thread_id: str, request: Request) -> ThreadDetailResponse:
    """Get thread with full debate history."""
    from duh.memory.repository import MemoryRepository

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)

        # Support prefix matching
        if len(thread_id) < 36:
            all_threads = await repo.list_threads(limit=100)
            matches = [t for t in all_threads if t.id.startswith(thread_id)]
            if not matches:
                raise HTTPException(
                    status_code=404, detail=f"Thread not found: {thread_id}"
                )
            if len(matches) > 1:
                raise HTTPException(
                    status_code=400, detail=f"Ambiguous prefix: {thread_id}"
                )
            thread_id = matches[0].id

        thread = await repo.get_thread(thread_id)

    if thread is None:
        raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

    turns = []
    for turn in thread.turns:
        contribs = [
            ContributionResponse(
                model_ref=c.model_ref,
                role=c.role,
                content=c.content,
                input_tokens=c.input_tokens,
                output_tokens=c.output_tokens,
                cost_usd=c.cost_usd,
            )
            for c in turn.contributions
        ]
        dec = None
        if turn.decision:
            dec = DecisionResponse(
                content=turn.decision.content,
                confidence=turn.decision.confidence,
                rigor=turn.decision.rigor,
                dissent=turn.decision.dissent,
            )
        turns.append(
            TurnResponse(
                round_number=turn.round_number,
                state=turn.state,
                contributions=contribs,
                decision=dec,
            )
        )

    return ThreadDetailResponse(
        thread_id=thread.id,
        question=thread.question,
        status=thread.status,
        created_at=thread.created_at.isoformat(),
        turns=turns,
    )


@router.get("/share/{share_token}", response_model=ThreadDetailResponse)
async def get_shared_thread(share_token: str, request: Request) -> ThreadDetailResponse:
    """Get a shared thread (no auth required). Token is the thread ID."""
    from duh.memory.repository import MemoryRepository

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)
        thread = await repo.get_thread(share_token)

    if thread is None:
        raise HTTPException(
            status_code=404,
            detail=f"Shared thread not found: {share_token}",
        )

    turns = []
    for turn in thread.turns:
        contribs = [
            ContributionResponse(
                model_ref=c.model_ref,
                role=c.role,
                content=c.content,
                input_tokens=c.input_tokens,
                output_tokens=c.output_tokens,
                cost_usd=c.cost_usd,
            )
            for c in turn.contributions
        ]
        dec = None
        if turn.decision:
            dec = DecisionResponse(
                content=turn.decision.content,
                confidence=turn.decision.confidence,
                rigor=turn.decision.rigor,
                dissent=turn.decision.dissent,
            )
        turns.append(
            TurnResponse(
                round_number=turn.round_number,
                state=turn.state,
                contributions=contribs,
                decision=dec,
            )
        )

    return ThreadDetailResponse(
        thread_id=thread.id,
        question=thread.question,
        status=thread.status,
        created_at=thread.created_at.isoformat(),
        turns=turns,
    )


@router.get("/threads/{thread_id}/export")
async def export_thread(
    thread_id: str,
    request: Request,
    format: str = Query(default="pdf"),
    content: str = Query(default="full"),
    dissent: bool = Query(default=True),
) -> StreamingResponse:
    """Export a thread as PDF or markdown."""
    from duh.cli.app import _format_thread_markdown, _format_thread_pdf
    from duh.memory.repository import MemoryRepository

    db_factory = request.app.state.db_factory
    async with db_factory() as session:
        repo = MemoryRepository(session)

        # Support prefix matching
        if len(thread_id) < 36:
            all_threads = await repo.list_threads(limit=100)
            matches = [t for t in all_threads if t.id.startswith(thread_id)]
            if not matches:
                raise HTTPException(
                    status_code=404, detail=f"Thread not found: {thread_id}"
                )
            if len(matches) > 1:
                raise HTTPException(
                    status_code=400, detail=f"Ambiguous prefix: {thread_id}"
                )
            thread_id = matches[0].id

        thread = await repo.get_thread(thread_id)
        if thread is None:
            raise HTTPException(
                status_code=404, detail=f"Thread not found: {thread_id}"
            )
        votes = await repo.get_votes(thread_id)

    short_id = thread_id[:8]

    if format == "pdf":
        pdf_bytes = _format_thread_pdf(
            thread, votes, content=content, include_dissent=dissent
        )
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f"attachment; filename=consensus-{short_id}.pdf"
                )
            },
        )

    md_text = _format_thread_markdown(
        thread, votes, content=content, include_dissent=dissent
    )
    return StreamingResponse(
        io.BytesIO(md_text.encode()),
        media_type="text/markdown",
        headers={
            "Content-Disposition": (f"attachment; filename=consensus-{short_id}.md")
        },
    )
