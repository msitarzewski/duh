"""Shared orchestration contract and execution-scope regression tests."""

from __future__ import annotations

import asyncio

import pytest

from duh.config.schema import DuhConfig
from duh.consensus import (
    Completed,
    EngineOptions,
    PhaseStarted,
    RoundCommitted,
    handlers,
    run_consensus,
    stream_consensus,
)
from duh.core.errors import ConfigError, CostLimitExceededError
from duh.providers.base import TokenUsage
from duh.providers.manager import ProviderManager
from tests.fixtures.providers import MockProvider


async def _manager(*, limit=0.0):
    manager = ProviderManager(cost_hard_limit=limit)
    await manager.register(
        MockProvider(
            responses={
                "a": "A substantive answer.",
                "b": "The proposal misses a constraint.",
            },
            input_cost=1.0,
        )
    )
    return manager


async def _commit(ctx, pm):
    ctx.decision = ctx.revision
    ctx.confidence = 0.9
    ctx.rigor = 1.0


async def test_simultaneous_engines_report_only_their_own_usage(monkeypatch):
    manager = await _manager(limit=0.00045)
    manager.record_usage(manager.get_model_info("mock:a"), TokenUsage(1, 0))
    barrier = asyncio.Barrier(2)
    original = handlers.handle_propose

    async def propose(*args, **kwargs):
        await barrier.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(handlers, "handle_propose", propose)
    monkeypatch.setattr(handlers, "handle_commit", _commit)
    options = EngineOptions(max_rounds=1, overview=False, followups=False)
    first, second = await asyncio.gather(
        run_consensus("First question", DuhConfig(), manager, options=options),
        run_consensus("Second question", DuhConfig(), manager, options=options),
    )
    assert first.question == "First question"
    assert second.question == "Second question"
    assert first.usage.input_tokens == second.usage.input_tokens == 400
    assert first.usage.cost_usd == second.usage.cost_usd == pytest.approx(0.0004)
    assert manager.aggregate_usage.input_tokens == 801
    assert len(first.round_history) == len(second.round_history) == 1


async def test_round_sink_failure_aborts_before_completion(monkeypatch):
    manager = await _manager()
    monkeypatch.setattr(handlers, "handle_commit", _commit)
    observed = []

    async def consume(event):
        observed.append(event)
        if isinstance(event, RoundCommitted):
            assert sum(u.input_tokens for u in event.usage) == 400
            raise OSError("Round store unavailable")

    with pytest.raises(OSError, match="Round store unavailable"):
        await run_consensus(
            "Question",
            DuhConfig(),
            manager,
            options=EngineOptions(max_rounds=2),
            emit=consume,
        )
    assert not any(isinstance(e, Completed) for e in observed)
    assert (
        len(
            [
                e
                for e in observed
                if isinstance(e, PhaseStarted) and e.phase == "PROPOSE"
            ]
        )
        == 1
    )


async def test_stream_events_and_budget_failure_propagate(monkeypatch):
    manager = await _manager(limit=0.00015)
    monkeypatch.setattr(handlers, "handle_commit", _commit)
    events = []
    with pytest.raises(CostLimitExceededError):
        async for event in stream_consensus(
            "Question", DuhConfig(), manager, options=EngineOptions(max_rounds=1)
        ):
            events.append(event)
    assert events[0].type == "phase_start"
    assert not any(isinstance(e, Completed) for e in events)
    with manager.usage_scope() as next_run:
        assert next_run.cost_usd == 0.0


async def test_stream_completion_matches_callback_result(monkeypatch):
    manager = await _manager()
    monkeypatch.setattr(handlers, "handle_commit", _commit)
    events = [
        event
        async for event in stream_consensus(
            "Question",
            DuhConfig(),
            manager,
            options=EngineOptions(max_rounds=1, overview=False, followups=False),
        )
    ]
    assert isinstance(events[-1], Completed)
    complete = events[-1].to_wire()
    assert complete["decision"]
    assert complete["usage"]["input_tokens"] == 400
    assert len([e for e in events if isinstance(e, RoundCommitted)]) == 1


async def test_closing_event_iterator_cancels_its_inflight_provider(monkeypatch):
    manager = await _manager()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def propose(*args, **kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(handlers, "handle_propose", propose)
    events = stream_consensus("Question", DuhConfig(), manager)
    assert (await anext(events)).type == "phase_start"
    await started.wait()
    await events.aclose()
    assert cancelled.is_set()
    with manager.usage_scope() as next_run:
        assert next_run.cost_usd == 0.0


async def test_postprocessing_usage_is_included_in_immutable_result(monkeypatch):
    from dataclasses import FrozenInstanceError

    manager = await _manager()
    monkeypatch.setattr(handlers, "handle_commit", _commit)
    result = await run_consensus(
        "Question", DuhConfig(), manager, options=EngineOptions(max_rounds=1)
    )
    assert result.usage.input_tokens == 600
    assert manager.aggregate_usage.input_tokens == 600
    with pytest.raises(FrozenInstanceError):
        result.decision = "changed"


async def test_invalid_framing_config_is_rejected_before_any_provider_work():
    manager = await _manager()
    config = DuhConfig()
    config.consensus.challenge_types = ["unsupported-framing"]
    with pytest.raises(ConfigError, match="framing"):
        await run_consensus("Question", config, manager)
    assert manager.aggregate_usage.input_tokens == 0


def test_invalid_framing_is_rejected_when_loading_configuration():
    with pytest.raises(ValueError, match="challenge_types"):
        DuhConfig.model_validate({"consensus": {"challenge_types": ["unsupported"]}})


@pytest.mark.parametrize("asynchronous", [False, True])
async def test_thread_created_sink_failure_aborts_before_provider_work(
    monkeypatch, asynchronous
):
    from unittest.mock import AsyncMock, MagicMock

    from duh.memory import persist

    manager = await _manager()
    storage = MagicMock()
    storage.start = AsyncMock(return_value="thread-id")
    monkeypatch.setattr(persist, "IncrementalPersister", lambda *args: storage)

    def sync_callback(thread_id):
        raise RuntimeError("Caller aborted")

    async def async_callback(thread_id):
        raise RuntimeError("Caller aborted")

    callback = async_callback if asynchronous else sync_callback
    with pytest.raises(RuntimeError, match="Caller aborted"):
        await persist.run_persisted_consensus(
            "Question",
            DuhConfig(),
            manager,
            db_factory=object(),
            on_thread_created=callback,
        )
    assert manager.aggregate_usage.input_tokens == 0


@pytest.mark.parametrize("limit,should_fail", [(0.00045, True), (0.01, False)])
async def test_cli_refinement_shares_execution_manager_budget_and_total(
    monkeypatch, limit, should_fail
):
    from unittest.mock import AsyncMock, MagicMock

    from duh.cli import app

    manager = await _manager(limit=limit)
    setup = AsyncMock(return_value=manager)
    monkeypatch.setattr(app, "_setup_providers", setup)
    monkeypatch.setattr(app, "_setup_tools", lambda config: None)
    monkeypatch.setattr(handlers, "handle_commit", _commit)

    async def refine(question, config, *, provider_manager):
        assert provider_manager is manager
        provider_manager.record_usage(
            provider_manager.get_model_info("mock:a"), TokenUsage(100, 0)
        )
        return "Refined question"

    monkeypatch.setattr(app, "_refine_question", refine)
    render = MagicMock()
    monkeypatch.setattr(app, "_display_consensus_result", render)
    config = DuhConfig()
    config.general.max_rounds = 1
    config.database.url = "sqlite+aiosqlite:///:memory:"
    if should_fail:
        with pytest.raises(CostLimitExceededError):
            await app._ask_refined_async(
                "Question", config, protocol="consensus", decompose=False
            )
        render.assert_not_called()
    else:
        await app._ask_refined_async(
            "Question", config, protocol="consensus", decompose=False
        )
        assert render.call_args.args[0][4] == pytest.approx(0.0007)
    setup.assert_awaited_once()


@pytest.mark.parametrize(
    "protocol,decompose,target",
    [
        ("voting", False, "_ask_voting_async"),
        ("auto", False, "_ask_auto_async"),
        ("consensus", True, "_ask_decompose_async"),
    ],
)
async def test_refinement_reuses_scope_for_every_protocol(
    monkeypatch, protocol, decompose, target
):
    from unittest.mock import AsyncMock

    from duh.cli import app

    manager = await _manager()
    monkeypatch.setattr(app, "_setup_providers", AsyncMock(return_value=manager))

    async def refine(question, config, *, provider_manager):
        provider_manager.record_usage(
            provider_manager.get_model_info("mock:a"), TokenUsage(100, 0)
        )
        return "Refined"

    async def execute(question, config, *, provider_manager):
        assert provider_manager is manager
        assert provider_manager.total_input_tokens == 100

    monkeypatch.setattr(app, "_refine_question", refine)
    run = AsyncMock(side_effect=execute)
    monkeypatch.setattr(app, target, run)
    await app._ask_refined_async(
        "Question", DuhConfig(), protocol=protocol, decompose=decompose
    )
    run.assert_awaited_once()
