"""Public consensus orchestration, independent of transports and persistence.

Consumers receive typed events and decide when/how to render or persist them.
An awaited event sink provides backpressure: a failed round write aborts the
run before the consumer can advertise that round as durable.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypeAlias

from duh.consensus.machine import (
    ChallengeResult,
    ConsensusContext,
    ConsensusState,
    ConsensusStateMachine,
    RoundResult,
)
from duh.core.errors import ModelNotFoundError
from duh.providers.manager import UsageSnapshot

if TYPE_CHECKING:
    from duh.config.schema import DuhConfig
    from duh.providers.base import ModelResponse
    from duh.providers.manager import ProviderManager
    from duh.tools.registry import ToolRegistry

Phase: TypeAlias = Literal["PROPOSE", "CHALLENGE", "REVISE"]


@dataclass(frozen=True, slots=True)
class EngineOptions:
    """Explicit overrides; configuration and selections are never mutated."""

    max_rounds: int | None = None
    panel: tuple[str, ...] | None = None
    proposer: str | None = None
    challengers: tuple[str, ...] | None = None
    challenger_count: int | None = None
    web_search: bool = False
    overview: bool = True
    followups: bool = True
    thread_id: str = ""


@dataclass(frozen=True, slots=True)
class ContributionUsage:
    """Measured response usage associated with a round contribution."""

    round_number: int
    role: Literal["proposer", "challenger", "reviser"]
    model_ref: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    framing: str | None = None
    occurrence: int = 0


@dataclass(frozen=True, slots=True)
class ConsensusResult:
    question: str
    decision: str
    confidence: float
    rigor: float
    dissent: str | None
    usage: UsageSnapshot
    overview: str | None = None
    round_history: tuple[RoundResult, ...] = ()
    citations: tuple[dict[str, str | None], ...] = ()
    followups: tuple[str, ...] = ()
    tool_calls_log: tuple[dict[str, str], ...] = ()
    thread_id: str = ""


@dataclass(frozen=True, slots=True)
class PhaseStarted:
    phase: Phase
    round_number: int
    model: str | None = None
    models: tuple[str, ...] = ()
    type: Literal["phase_start"] = field(default="phase_start", init=False)

    def to_wire(self) -> dict[str, object]:
        result: dict[str, object] = {
            "type": self.type,
            "phase": self.phase,
            "round": self.round_number,
        }
        if self.model is not None:
            result["model"] = self.model
        if self.phase == "CHALLENGE":
            result["models"] = list(self.models)
        return result


@dataclass(frozen=True, slots=True)
class PhaseCompleted:
    phase: Phase
    round_number: int
    content: str | None = None
    model: str | None = None
    truncated: bool = False
    citations: tuple[dict[str, str | None], ...] = ()
    challenges: tuple[ChallengeResult, ...] = ()
    type: Literal["phase_complete"] = field(default="phase_complete", init=False)

    def to_wire(self) -> dict[str, object]:
        result: dict[str, object] = {"type": self.type, "phase": self.phase}
        if self.content is not None:
            result.update(
                content=self.content,
                truncated=self.truncated,
                citations=list(self.citations) or None,
            )
        return result


@dataclass(frozen=True, slots=True)
class ChallengeCompleted:
    round_number: int
    challenge: ChallengeResult
    truncated: bool = False
    type: Literal["challenge"] = field(default="challenge", init=False)

    def to_wire(self) -> dict[str, object]:
        return {
            "type": self.type,
            "model": self.challenge.model_ref,
            "content": self.challenge.content,
            "framing": self.challenge.framing,
            "truncated": self.truncated,
            "citations": list(self.challenge.citations) or None,
        }


@dataclass(frozen=True, slots=True)
class ChallengeFailed:
    round_number: int
    model: str
    type: Literal["challenge_error"] = field(default="challenge_error", init=False)

    def to_wire(self) -> dict[str, object]:
        return {"type": self.type, "model": self.model}


@dataclass(frozen=True, slots=True)
class RoundCommitted:
    round: RoundResult
    usage: tuple[ContributionUsage, ...] = ()
    type: Literal["commit"] = field(default="commit", init=False)

    def to_wire(self) -> dict[str, object]:
        return {
            "type": self.type,
            "round": self.round.round_number,
            "confidence": self.round.confidence,
            "rigor": self.round.rigor,
            "dissent": self.round.dissent,
        }


@dataclass(frozen=True, slots=True)
class Completed:
    result: ConsensusResult
    type: Literal["complete"] = field(default="complete", init=False)

    def to_wire(self) -> dict[str, object]:
        result = self.result
        return {
            "type": self.type,
            "decision": result.decision,
            "confidence": result.confidence,
            "rigor": result.rigor,
            "dissent": result.dissent,
            "cost": result.usage.cost_usd,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cost_usd": result.usage.cost_usd,
            },
            "overview": result.overview,
            "followups": list(result.followups) or None,
            "thread_id": result.thread_id or None,
        }


ConsensusEvent: TypeAlias = (
    PhaseStarted
    | PhaseCompleted
    | ChallengeCompleted
    | ChallengeFailed
    | RoundCommitted
    | Completed
)
EventSink: TypeAlias = Callable[[ConsensusEvent], Awaitable[None]]


def _contribution_usage(
    pm: ProviderManager,
    response: ModelResponse,
    round_number: int,
    role: Literal["proposer", "challenger", "reviser"],
    model: str,
    *,
    framing: str | None = None,
    occurrence: int = 0,
) -> ContributionUsage:
    usage = response.usage
    if usage is None:
        return ContributionUsage(
            round_number, role, model, 0, 0, 0.0, framing, occurrence
        )
    try:
        info = pm.get_model_info(model)
        cost = (
            usage.input_tokens * info.input_cost_per_mtok
            + usage.output_tokens * info.output_cost_per_mtok
        ) / 1_000_000
    except ModelNotFoundError:
        cost = 0.0
    return ContributionUsage(
        round_number,
        role,
        model,
        usage.input_tokens,
        usage.output_tokens,
        cost,
        framing,
        occurrence,
    )


async def run_consensus(
    question: str,
    config: DuhConfig,
    pm: ProviderManager,
    *,
    options: EngineOptions | None = None,
    tool_registry: ToolRegistry | None = None,
    emit: EventSink | None = None,
) -> ConsensusResult:
    """Execute the shared loop; storage and user interfaces stay with callers."""
    from duh.consensus import convergence, handlers

    opts = options or EngineOptions()
    rounds = (
        opts.max_rounds if opts.max_rounds is not None else config.general.max_rounds
    )
    if rounds < 1:
        raise ValueError("Consensus requires at least one round")
    framings = handlers.validate_challenge_framings(config.consensus.challenge_types)
    panel = list(opts.panel or config.consensus.panel) or None
    ctx = ConsensusContext(
        thread_id=opts.thread_id, question=question, max_rounds=rounds
    )
    sm = ConsensusStateMachine(ctx)

    async def send(event: ConsensusEvent) -> None:
        if emit is not None:
            await emit(event)

    with pm.usage_scope():
        for _ in range(rounds):
            usage: list[ContributionUsage] = []
            sm.transition(ConsensusState.PROPOSE)
            proposer = opts.proposer or handlers.select_proposer(pm, panel=panel)
            await send(PhaseStarted("PROPOSE", ctx.current_round, model=proposer))
            response = await handlers.handle_propose(
                ctx,
                pm,
                proposer,
                tool_registry=tool_registry,
                web_search=opts.web_search,
            )
            usage.append(
                _contribution_usage(
                    pm, response, ctx.current_round, "proposer", proposer
                )
            )
            await send(
                PhaseCompleted(
                    "PROPOSE",
                    ctx.current_round,
                    ctx.proposal or "",
                    proposer,
                    response.finish_reason != "stop",
                    tuple(ctx.proposal_citations),
                )
            )

            sm.transition(ConsensusState.CHALLENGE)
            challengers = (
                list(opts.challengers)
                if opts.challengers is not None
                else handlers.select_challengers(
                    pm,
                    proposer,
                    panel=panel,
                    **(
                        {"count": opts.challenger_count}
                        if opts.challenger_count is not None
                        else {}
                    ),
                )
            )
            await send(
                PhaseStarted("CHALLENGE", ctx.current_round, models=tuple(challengers))
            )

            async def on_challenge(
                challenge: ChallengeResult,
                response: ModelResponse,
                *,
                round_usage: list[ContributionUsage] = usage,
            ) -> None:
                round_usage.append(
                    _contribution_usage(
                        pm,
                        response,
                        ctx.current_round,
                        "challenger",
                        challenge.model_ref,
                        framing=challenge.framing,
                        occurrence=challenge.occurrence,
                    )
                )
                await send(
                    ChallengeCompleted(
                        ctx.current_round, challenge, response.finish_reason != "stop"
                    )
                )

            async def on_error(model: str) -> None:
                await send(ChallengeFailed(ctx.current_round, model))

            await handlers.handle_challenge(
                ctx,
                pm,
                challengers,
                tool_registry=tool_registry,
                web_search=opts.web_search,
                framings=framings,
                on_result=on_challenge,
                on_error=on_error,
            )
            await send(
                PhaseCompleted(
                    "CHALLENGE", ctx.current_round, challenges=tuple(ctx.challenges)
                )
            )

            sm.transition(ConsensusState.REVISE)
            reviser = ctx.proposal_model or proposer
            await send(PhaseStarted("REVISE", ctx.current_round, model=reviser))
            response = await handlers.handle_revise(
                ctx,
                pm,
                tool_registry=tool_registry,
                web_search=opts.web_search,
            )
            usage.append(
                _contribution_usage(
                    pm,
                    response,
                    ctx.current_round,
                    "reviser",
                    ctx.revision_model or reviser,
                )
            )
            await send(
                PhaseCompleted(
                    "REVISE",
                    ctx.current_round,
                    ctx.revision or "",
                    ctx.revision_model or reviser,
                    response.finish_reason != "stop",
                    tuple(ctx.revision_citations),
                )
            )

            sm.transition(ConsensusState.COMMIT)
            await handlers.handle_commit(ctx, pm)
            await send(RoundCommitted(ctx.snapshot_round(), tuple(usage)))
            if convergence.check_convergence(ctx):
                break

        sm.transition(ConsensusState.COMPLETE)
        if opts.overview:
            await handlers.generate_overview(ctx, pm)
        if opts.followups:
            await handlers.generate_followups(ctx, pm)
        citations: list[dict[str, str | None]] = []
        for rnd in ctx.round_history:
            citations.extend(rnd.proposal_citations)
            for challenge in rnd.challenges:
                citations.extend(challenge.citations)
            citations.extend(rnd.revision_citations)
        result = ConsensusResult(
            question=question,
            decision=ctx.decision or "",
            confidence=ctx.confidence,
            rigor=ctx.rigor,
            dissent=ctx.dissent,
            usage=UsageSnapshot(
                pm.total_input_tokens, pm.total_output_tokens, pm.total_cost
            ),
            overview=ctx.overview,
            round_history=tuple(ctx.round_history),
            citations=tuple(citations),
            followups=tuple(ctx.followups),
            tool_calls_log=tuple(ctx.tool_calls_log),
            thread_id=ctx.thread_id,
        )
        await send(Completed(result))
        return result


async def stream_consensus(
    question: str,
    config: DuhConfig,
    pm: ProviderManager,
    *,
    options: EngineOptions | None = None,
    tool_registry: ToolRegistry | None = None,
) -> AsyncIterator[ConsensusEvent]:
    """Iterate bounded events; closing the iterator cancels/drains its worker."""
    queue: asyncio.Queue[ConsensusEvent | BaseException | None] = asyncio.Queue(
        maxsize=1
    )

    async def emit(event: ConsensusEvent) -> None:
        await queue.put(event)

    async def worker() -> None:
        try:
            await run_consensus(
                question,
                config,
                pm,
                options=options,
                tool_registry=tool_registry,
                emit=emit,
            )
        except asyncio.CancelledError:
            raise
        except BaseException as exc:
            await queue.put(exc)
        finally:
            # Cancellation is handled by the consumer, which need not drain.
            current = asyncio.current_task()
            if current is not None and not current.cancelling():
                await queue.put(None)

    task = asyncio.create_task(worker())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            if isinstance(event, BaseException):
                raise event
            yield event
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
