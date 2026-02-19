"""Main CLI application.

Click commands for the duh consensus engine: ask, recall, threads,
show, models, cost, batch.
"""

from __future__ import annotations

import asyncio
import json as json_mod
import sys
import time
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING

import click

from duh import __version__
from duh.config.loader import load_config
from duh.core.errors import ConfigError, DuhError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

    from duh.cli.display import ConsensusDisplay
    from duh.config.schema import DuhConfig
    from duh.memory.models import Thread, Vote
    from duh.providers.base import ModelInfo
    from duh.providers.manager import ProviderManager
    from duh.tools.registry import ToolRegistry


# ── Helpers ──────────────────────────────────────────────────────


def _error(msg: str) -> None:
    """Print an error message to stderr and exit."""
    click.echo(f"Error: {msg}", err=True)
    sys.exit(1)


def _load_config(config_path: str | None) -> DuhConfig:
    """Load config with user-friendly error handling."""
    try:
        return load_config(path=config_path)
    except ConfigError as e:
        _error(str(e))
        raise  # unreachable, keeps mypy happy


async def _create_db(
    config: DuhConfig,
) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    """Create async engine and sessionmaker from config."""
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from duh.memory.models import Base

    url = config.database.url
    if "~" in url:
        url = url.replace("~", str(Path.home()))

    # Ensure parent directory exists for sqlite
    if url.startswith("sqlite"):
        db_path = url.split("///")[-1] if "///" in url else ""
        if db_path and db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    engine_kwargs: dict[str, object] = {}
    if url.startswith("sqlite"):
        if ":memory:" in url:
            # In-memory SQLite needs StaticPool so all queries share
            # the same connection (and thus the same in-memory DB).
            from sqlalchemy.pool import StaticPool

            engine_kwargs["poolclass"] = StaticPool
            engine_kwargs["connect_args"] = {"check_same_thread": False}
        else:
            from sqlalchemy.pool import NullPool

            engine_kwargs["poolclass"] = NullPool
    else:
        engine_kwargs["pool_size"] = config.database.pool_size
        engine_kwargs["max_overflow"] = config.database.max_overflow
        engine_kwargs["pool_timeout"] = config.database.pool_timeout
        engine_kwargs["pool_recycle"] = config.database.pool_recycle
        engine_kwargs["pool_pre_ping"] = True

    engine = create_async_engine(url, **engine_kwargs)

    # Enable foreign keys for SQLite
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    # Only use create_all for in-memory SQLite (tests/dev).
    # File-based SQLite and PostgreSQL are managed by alembic migrations.
    is_memory = url.startswith("sqlite") and ":memory:" in url
    if is_memory:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    elif url.startswith("sqlite"):
        from duh.memory.migrations import ensure_schema

        await ensure_schema(engine)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    return factory, engine


async def _setup_providers(config: DuhConfig) -> ProviderManager:
    """Instantiate and register providers from config."""
    from duh.providers.manager import ProviderManager

    pm = ProviderManager(cost_hard_limit=config.cost.hard_limit)

    for name, prov_config in config.providers.items():
        if not prov_config.enabled:
            continue
        if prov_config.api_key is None and name in (
            "anthropic",
            "openai",
            "google",
            "mistral",
            "perplexity",
        ):
            continue  # Skip providers without API keys

        # Set provider rate limit if configured
        if prov_config.rate_limit > 0:
            pm.set_provider_rate_limit(name, prov_config.rate_limit)

        if name == "anthropic":
            from duh.providers.anthropic import AnthropicProvider

            anthropic_prov = AnthropicProvider(api_key=prov_config.api_key)
            await pm.register(anthropic_prov)  # type: ignore[arg-type]
        elif name == "openai":
            from duh.providers.openai import OpenAIProvider

            openai_prov = OpenAIProvider(
                api_key=prov_config.api_key,
                base_url=prov_config.base_url,
            )
            await pm.register(openai_prov)  # type: ignore[arg-type]
        elif name == "google":
            from duh.providers.google import GoogleProvider

            google_prov = GoogleProvider(api_key=prov_config.api_key)
            await pm.register(google_prov)  # type: ignore[arg-type]
        elif name == "mistral":
            from duh.providers.mistral import MistralProvider

            mistral_prov = MistralProvider(api_key=prov_config.api_key)
            await pm.register(mistral_prov)  # type: ignore[arg-type]
        elif name == "perplexity":
            from duh.providers.perplexity import PerplexityProvider

            perplexity_prov = PerplexityProvider(api_key=prov_config.api_key)
            await pm.register(perplexity_prov)  # type: ignore[arg-type]

    return pm


def _setup_tools(config: DuhConfig) -> ToolRegistry | None:
    """Set up tool registry from config.

    Returns None if tools are disabled.
    """
    if not config.tools.enabled:
        return None

    from duh.tools.registry import ToolRegistry

    registry = ToolRegistry()

    # Web search tool (always available when tools enabled)
    from duh.tools.web_search import WebSearchTool

    registry.register(WebSearchTool(config.tools.web_search))

    # File read tool (always available when tools enabled)
    from duh.tools.file_read import FileReadTool

    registry.register(FileReadTool())

    # Code execution tool (only if explicitly enabled)
    if config.tools.code_execution.enabled:
        from duh.tools.code_exec import CodeExecutionTool

        registry.register(CodeExecutionTool(config.tools.code_execution))

    return registry


async def _run_consensus(
    question: str,
    config: DuhConfig,
    pm: ProviderManager,
    display: ConsensusDisplay | None = None,
    tool_registry: ToolRegistry | None = None,
    *,
    panel: list[str] | None = None,
    proposer_override: str | None = None,
    challengers_override: list[str] | None = None,
) -> tuple[str, float, float, str | None, float]:
    """Run the full consensus loop.

    Returns (decision, confidence, rigor, dissent, total_cost).
    """
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
        thread_id="",  # Placeholder, set after DB save
        question=question,
        max_rounds=config.general.max_rounds,
    )
    sm = ConsensusStateMachine(ctx)

    # Resolve effective panel from config or explicit arg
    effective_panel = panel or config.consensus.panel or None

    for _round in range(config.general.max_rounds):
        # PROPOSE
        sm.transition(ConsensusState.PROPOSE)
        if display:
            display.round_header(ctx.current_round, config.general.max_rounds)

        proposer = proposer_override or select_proposer(pm, panel=effective_panel)
        if display:
            with display.phase_status("PROPOSE", proposer):
                await handle_propose(ctx, pm, proposer, tool_registry=tool_registry)
            display.show_propose(proposer, ctx.proposal or "")
        else:
            await handle_propose(ctx, pm, proposer, tool_registry=tool_registry)

        # CHALLENGE
        sm.transition(ConsensusState.CHALLENGE)
        challengers = challengers_override or select_challengers(
            pm, proposer, panel=effective_panel
        )
        if display:
            detail = f"{len(challengers)} models"
            with display.phase_status("CHALLENGE", detail):
                await handle_challenge(
                    ctx, pm, challengers, tool_registry=tool_registry
                )
            display.show_challenges(ctx.challenges)
        else:
            await handle_challenge(ctx, pm, challengers, tool_registry=tool_registry)

        # REVISE
        sm.transition(ConsensusState.REVISE)
        if display:
            reviser = ctx.proposal_model or proposer
            with display.phase_status("REVISE", reviser):
                await handle_revise(ctx, pm)
            display.show_revise(ctx.revision_model or reviser, ctx.revision or "")
        else:
            await handle_revise(ctx, pm)

        # COMMIT
        sm.transition(ConsensusState.COMMIT)
        await handle_commit(ctx, pm)
        if display:
            display.show_commit(ctx.confidence, ctx.rigor, ctx.dissent)
            display.round_footer(
                ctx.current_round,
                config.general.max_rounds,
                len(pm.list_all_models()),
                pm.total_cost,
            )

        # Check convergence
        if check_convergence(ctx):
            break

        # If not converged and more rounds available, continue
        if ctx.current_round < config.general.max_rounds:
            continue
        break

    sm.transition(ConsensusState.COMPLETE)

    # Show tool usage if any
    if display and ctx.tool_calls_log:
        display.show_tool_use(ctx.tool_calls_log)

    return (
        ctx.decision or "",
        ctx.confidence,
        ctx.rigor,
        ctx.dissent,
        pm.total_cost,
    )


# ── CLI group ────────────────────────────────────────────────────


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="duh")
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True),
    default=None,
    help="Path to config file.",
)
@click.pass_context
def cli(ctx: click.Context, config_path: str | None) -> None:
    """duh - Multi-model consensus engine.

    Ask multiple LLMs, get one answer they agree on.
    """
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config_path
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── ask ──────────────────────────────────────────────────────────


@cli.command()
@click.argument("question")
@click.option(
    "--rounds",
    type=int,
    default=None,
    help="Max consensus rounds (overrides config).",
)
@click.option(
    "--decompose",
    is_flag=True,
    default=False,
    help="Decompose the question into subtasks before consensus.",
)
@click.option(
    "--protocol",
    type=click.Choice(["consensus", "voting", "auto"]),
    default=None,
    help="Protocol: consensus (default), voting, or auto (classify first).",
)
@click.option(
    "--tools/--no-tools",
    default=None,
    help="Enable/disable tool use (overrides config).",
)
@click.option(
    "--proposer",
    default=None,
    help="Override proposer model (e.g. anthropic:claude-opus-4-6).",
)
@click.option(
    "--challengers",
    default=None,
    help="Override challengers (comma-separated model refs).",
)
@click.option(
    "--panel",
    default=None,
    help="Restrict to these models only (comma-separated model refs).",
)
@click.pass_context
def ask(
    ctx: click.Context,
    question: str,
    rounds: int | None,
    decompose: bool,
    protocol: str | None,
    tools: bool | None,
    proposer: str | None,
    challengers: str | None,
    panel: str | None,
) -> None:
    """Run a consensus query.

    Sends QUESTION to multiple LLMs, challenges their answers,
    and produces a revised consensus decision.
    """
    config = _load_config(ctx.obj["config_path"])
    if rounds is not None:
        config.general.max_rounds = rounds

    # Override tool settings from CLI flag
    if tools is not None:
        config.tools.enabled = tools

    # Parse model selection overrides
    panel_list = panel.split(",") if panel else None
    challengers_list = challengers.split(",") if challengers else None

    # Determine effective protocol
    effective_protocol = protocol or config.general.protocol

    if decompose or config.general.decompose:
        try:
            asyncio.run(_ask_decompose_async(question, config))
        except DuhError as e:
            _error(str(e))
        return

    if effective_protocol == "voting":
        try:
            asyncio.run(_ask_voting_async(question, config))
        except DuhError as e:
            _error(str(e))
        return

    if effective_protocol == "auto":
        try:
            asyncio.run(_ask_auto_async(question, config))
        except DuhError as e:
            _error(str(e))
        return

    try:
        result = asyncio.run(
            _ask_async(
                question,
                config,
                panel=panel_list,
                proposer_override=proposer,
                challengers_override=challengers_list,
            )
        )
    except DuhError as e:
        _error(str(e))
        return  # unreachable

    decision, confidence, rigor, dissent, cost = result

    from duh.cli.display import ConsensusDisplay

    display = ConsensusDisplay()
    display.show_final_decision(decision, confidence, rigor, cost, dissent)


async def _ask_async(
    question: str,
    config: DuhConfig,
    *,
    panel: list[str] | None = None,
    proposer_override: str | None = None,
    challengers_override: list[str] | None = None,
) -> tuple[str, float, float, str | None, float]:
    """Async implementation for the ask command."""
    from duh.cli.display import ConsensusDisplay

    pm = await _setup_providers(config)

    if not pm.list_all_models():
        _error(
            "No models available. Configure providers in "
            "~/.config/duh/config.toml or set API key environment variables."
        )

    tool_registry = _setup_tools(config)
    display = ConsensusDisplay()
    display.start()
    return await _run_consensus(
        question,
        config,
        pm,
        display=display,
        tool_registry=tool_registry,
        panel=panel,
        proposer_override=proposer_override,
        challengers_override=challengers_override,
    )


async def _ask_voting_async(
    question: str,
    config: DuhConfig,
) -> None:
    """Async implementation for the ask --protocol=voting command."""
    from duh.cli.display import ConsensusDisplay
    from duh.consensus.voting import run_voting
    from duh.memory.repository import MemoryRepository

    pm = await _setup_providers(config)

    if not pm.list_all_models():
        _error(
            "No models available. Configure providers in "
            "~/.config/duh/config.toml or set API key environment variables."
        )

    display = ConsensusDisplay()
    display.start()

    aggregation = config.voting.aggregation
    result = await run_voting(question, pm, aggregation=aggregation)

    if result.votes:
        display.show_votes(list(result.votes))

    display.show_voting_result(result, pm.total_cost)

    # Persist votes
    factory, engine = await _create_db(config)
    async with factory() as session:
        repo = MemoryRepository(session)
        thread = await repo.create_thread(question)
        thread.status = "complete"
        for vote in result.votes:
            await repo.save_vote(thread.id, vote.model_ref, vote.content)
        # Save aggregated decision
        if result.decision:
            turn = await repo.create_turn(thread.id, 1, "COMMIT")
            await repo.save_decision(
                turn.id,
                thread.id,
                result.decision,
                result.confidence,
                rigor=result.rigor,
            )
        await session.commit()
    await engine.dispose()


async def _ask_auto_async(
    question: str,
    config: DuhConfig,
) -> None:
    """Async implementation for the ask --protocol=auto command.

    Classifies the question first, then routes to voting (for judgment)
    or consensus (for reasoning/unknown).
    """
    from duh.consensus.classifier import TaskType, classify_task_type

    pm = await _setup_providers(config)

    if not pm.list_all_models():
        _error(
            "No models available. Configure providers in "
            "~/.config/duh/config.toml or set API key environment variables."
        )

    task_type = await classify_task_type(question, pm)
    click.echo(f"Classified as: {task_type.value}")

    if task_type == TaskType.JUDGMENT:
        await _ask_voting_async(question, config)
    else:
        # Reasoning or unknown -> use consensus
        from duh.cli.display import ConsensusDisplay

        display = ConsensusDisplay()
        display.start()
        decision, confidence, rigor, dissent, cost = await _run_consensus(
            question, config, pm, display=display
        )
        display.show_final_decision(decision, confidence, rigor, cost, dissent)


async def _ask_decompose_async(
    question: str,
    config: DuhConfig,
) -> None:
    """Async implementation for the ask --decompose command.

    Runs DECOMPOSE -> schedule_subtasks -> synthesize, displaying
    each phase.  Single-subtask optimization: if only one subtask
    is produced, runs normal consensus instead of synthesis.
    """
    import json as json_mod

    from duh.cli.display import ConsensusDisplay
    from duh.consensus.decompose import handle_decompose
    from duh.consensus.machine import (
        ConsensusContext,
        ConsensusState,
        ConsensusStateMachine,
    )
    from duh.consensus.scheduler import schedule_subtasks
    from duh.consensus.synthesis import synthesize

    pm = await _setup_providers(config)

    if not pm.list_all_models():
        _error(
            "No models available. Configure providers in "
            "~/.config/duh/config.toml or set API key environment variables."
        )

    display = ConsensusDisplay()
    display.start()

    # DECOMPOSE
    ctx = ConsensusContext(
        thread_id="",
        question=question,
        max_rounds=config.general.max_rounds,
    )
    sm = ConsensusStateMachine(ctx)
    sm.transition(ConsensusState.DECOMPOSE)

    with display.phase_status("DECOMPOSE", "analyzing"):
        subtask_specs = await handle_decompose(
            ctx, pm, max_subtasks=config.decompose.max_subtasks
        )

    display.show_decompose(subtask_specs)

    # Persist subtasks to DB
    factory, engine = await _create_db(config)
    async with factory() as session:
        from duh.memory.repository import MemoryRepository

        repo = MemoryRepository(session)
        thread = await repo.create_thread(question)

        for i, spec in enumerate(subtask_specs):
            await repo.save_subtask(
                parent_thread_id=thread.id,
                label=spec.label,
                description=spec.description,
                dependencies=json_mod.dumps(spec.dependencies),
                sequence_order=i,
            )
        await session.commit()

    # Single-subtask optimization: skip synthesis
    if len(subtask_specs) == 1:
        result = await _run_consensus(question, config, pm, display=display)
        decision, confidence, rigor, dissent, cost = result
        display.show_final_decision(decision, confidence, rigor, cost, dissent)
        await engine.dispose()
        return

    # Schedule subtasks
    subtask_results = await schedule_subtasks(
        subtask_specs, question, config, pm, display=display
    )

    for sr in subtask_results:
        display.show_subtask_progress(sr)

    # Synthesize
    with display.phase_status("SYNTHESIS", "merging"):
        synthesis_result = await synthesize(question, subtask_results, pm)

    display.show_synthesis(synthesis_result)
    display.show_final_decision(
        synthesis_result.content,
        synthesis_result.confidence,
        synthesis_result.rigor,
        pm.total_cost,
        None,
    )

    await engine.dispose()


# ── recall ───────────────────────────────────────────────────────


@cli.command()
@click.argument("query")
@click.option("--limit", type=int, default=10, help="Max results.")
@click.pass_context
def recall(ctx: click.Context, query: str, limit: int) -> None:
    """Search past decisions by keyword.

    Searches thread questions and decision content for QUERY.
    """
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_recall_async(config, query, limit))
    except DuhError as e:
        _error(str(e))


async def _recall_async(config: DuhConfig, query: str, limit: int) -> None:
    """Async implementation for the recall command."""

    from duh.memory.repository import MemoryRepository

    factory, engine = await _create_db(config)
    async with factory() as session:
        repo = MemoryRepository(session)
        threads = await repo.search(query, limit=limit)
        # Eagerly load decisions before leaving session
        for thread in threads:
            await session.refresh(thread, ["decisions"])

    await engine.dispose()

    if not threads:
        click.echo(f"No results for '{query}'.")
        return

    for thread in threads:
        click.echo(f"  Thread {thread.id[:8]}  {thread.question}")
        if thread.decisions:
            latest = thread.decisions[-1]
            snippet = latest.content[:120].replace("\n", " ")
            click.echo(f"    Decision: {snippet}...")
            click.echo(
                f"    Confidence: {latest.confidence:.0%}  Rigor: {latest.rigor:.0%}"
            )
        click.echo()


# ── threads ──────────────────────────────────────────────────────


@cli.command()
@click.option(
    "--status",
    type=click.Choice(["active", "complete", "failed"]),
    default=None,
    help="Filter by status.",
)
@click.option("--limit", type=int, default=20, help="Max results.")
@click.pass_context
def threads(ctx: click.Context, status: str | None, limit: int) -> None:
    """List past consensus threads."""
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_threads_async(config, status, limit))
    except DuhError as e:
        _error(str(e))


async def _threads_async(config: DuhConfig, status: str | None, limit: int) -> None:
    """Async implementation for the threads command."""
    from duh.memory.repository import MemoryRepository

    factory, engine = await _create_db(config)
    async with factory() as session:
        repo = MemoryRepository(session)
        thread_list = await repo.list_threads(status=status, limit=limit)

    await engine.dispose()

    if not thread_list:
        click.echo("No threads found.")
        return

    for thread in thread_list:
        created = thread.created_at.strftime("%Y-%m-%d %H:%M")
        snippet = thread.question[:60].replace("\n", " ")
        click.echo(f"  {thread.id[:8]}  [{thread.status}]  {created}  {snippet}")


# ── show ─────────────────────────────────────────────────────────


@cli.command()
@click.argument("thread_id")
@click.pass_context
def show(ctx: click.Context, thread_id: str) -> None:
    """Show a thread with its full debate history.

    THREAD_ID can be the full UUID or a prefix (minimum 8 chars).
    """
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_show_async(config, thread_id))
    except DuhError as e:
        _error(str(e))


async def _show_async(config: DuhConfig, thread_id: str) -> None:
    """Async implementation for the show command."""
    from duh.memory.repository import MemoryRepository

    factory, engine = await _create_db(config)
    async with factory() as session:
        repo = MemoryRepository(session)

        # Support prefix matching
        if len(thread_id) < 36:
            thread_list = await repo.list_threads(limit=100)
            matches = [t for t in thread_list if t.id.startswith(thread_id)]
            if not matches:
                click.echo(f"No thread matching '{thread_id}'.")
                await engine.dispose()
                return
            if len(matches) > 1:
                click.echo(f"Ambiguous prefix '{thread_id}'. Matches:")
                for m in matches:
                    click.echo(f"  {m.id}  {m.question[:50]}")
                await engine.dispose()
                return
            thread_id = matches[0].id

        thread = await repo.get_thread(thread_id)
        decisions_with_outcomes = await repo.get_decisions_with_outcomes(thread_id)
        votes = await repo.get_votes(thread_id)

    await engine.dispose()

    if thread is None:
        click.echo(f"Thread not found: {thread_id}")
        return

    click.echo(f"Question: {thread.question}")
    click.echo(f"Status: {thread.status}")
    click.echo(f"Created: {thread.created_at.strftime('%Y-%m-%d %H:%M')}")
    click.echo()

    # Show votes if any
    if votes:
        click.echo("--- Votes ---")
        for vote in votes:
            click.echo(f"  [{vote.model_ref}]")
            click.echo(f"  {vote.content}")
            click.echo()

    for turn in thread.turns:
        click.echo(f"--- Round {turn.round_number} ---")
        for contrib in turn.contributions:
            label = contrib.role.upper()
            click.echo(f"  [{label}] {contrib.model_ref}")
            click.echo(f"  {contrib.content}")
            click.echo()
        if turn.decision:
            click.echo(
                f"  Decision (confidence {turn.decision.confidence:.0%},"
                f" rigor {turn.decision.rigor:.0%}):"
            )
            click.echo(f"  {turn.decision.content}")
            if turn.decision.dissent:
                click.echo(f"  Dissent: {turn.decision.dissent}")

            # Taxonomy display
            d = turn.decision
            if d.intent or d.category or d.genus:
                click.echo(
                    f"  Taxonomy: intent={d.intent or ''}"
                    f" category={d.category or ''}"
                    f" genus={d.genus or ''}"
                )
            click.echo()

    # Show outcomes for the thread
    for dec in decisions_with_outcomes:
        if dec.outcome is not None:
            click.echo(
                f"  Outcome: {dec.outcome.result}"
                + (f" - {dec.outcome.notes}" if dec.outcome.notes else "")
            )


# ── feedback ────────────────────────────────────────────────


@cli.command()
@click.argument("thread_id")
@click.option(
    "--result",
    type=click.Choice(["success", "failure", "partial"]),
    required=True,
    help="Outcome result for the decision.",
)
@click.option("--notes", type=str, default=None, help="Optional notes.")
@click.pass_context
def feedback(
    ctx: click.Context, thread_id: str, result: str, notes: str | None
) -> None:
    """Record an outcome for a thread's latest decision.

    THREAD_ID can be the full UUID or a prefix (minimum 8 chars).
    """
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_feedback_async(config, thread_id, result, notes))
    except DuhError as e:
        _error(str(e))


async def _feedback_async(
    config: DuhConfig,
    thread_id: str,
    result_str: str,
    notes: str | None,
) -> None:
    """Async implementation for the feedback command."""
    from duh.memory.repository import MemoryRepository

    factory, engine = await _create_db(config)
    message: str = ""

    async with factory() as session:
        repo = MemoryRepository(session)

        # Support prefix matching (same pattern as show command)
        resolved_id = thread_id
        if len(resolved_id) < 36:
            thread_list = await repo.list_threads(limit=100)
            matches = [t for t in thread_list if t.id.startswith(resolved_id)]
            if not matches:
                message = f"No thread matching '{thread_id}'."
            elif len(matches) > 1:
                lines = [f"Ambiguous prefix '{thread_id}'. Matches:"]
                for m in matches:
                    lines.append(f"  {m.id}  {m.question[:50]}")
                message = "\n".join(lines)
            else:
                resolved_id = matches[0].id

        if not message:
            decisions = await repo.get_decisions(resolved_id)
            if not decisions:
                message = f"No decisions found for thread {resolved_id[:8]}."
            else:
                latest = decisions[-1]
                await repo.save_outcome(latest.id, resolved_id, result_str, notes=notes)
                await session.commit()
                message = f"Outcome recorded: {result_str} for thread {resolved_id[:8]}"

    await engine.dispose()
    click.echo(message)


# ── export ──────────────────────────────────────────────────────


@cli.command()
@click.argument("thread_id")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "markdown", "pdf"]),
    default="json",
    help="Export format.",
)
@click.option(
    "--content",
    type=click.Choice(["full", "decision"]),
    default="full",
    help="Content level: full report or decision only.",
)
@click.option(
    "--no-dissent",
    is_flag=True,
    default=False,
    help="Suppress dissent section.",
)
@click.option(
    "-o",
    "--output",
    "output_path",
    type=click.Path(),
    default=None,
    help="Output file path (required for PDF).",
)
@click.pass_context
def export(
    ctx: click.Context,
    thread_id: str,
    fmt: str,
    content: str,
    no_dissent: bool,
    output_path: str | None,
) -> None:
    """Export a thread with full debate history.

    THREAD_ID can be the full UUID or a prefix (minimum 8 chars).
    """
    if fmt == "pdf" and not output_path:
        _error("--output / -o is required for PDF export.")
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(
            _export_async(
                config,
                thread_id,
                fmt,
                content=content,
                include_dissent=not no_dissent,
                output_path=output_path,
            )
        )
    except DuhError as e:
        _error(str(e))


async def _export_async(
    config: DuhConfig,
    thread_id: str,
    fmt: str,
    *,
    content: str = "full",
    include_dissent: bool = True,
    output_path: str | None = None,
) -> None:
    """Async implementation for the export command."""
    from duh.memory.repository import MemoryRepository

    factory, engine = await _create_db(config)
    thread = None
    votes: list[Vote] = []
    message: str = ""

    async with factory() as session:
        repo = MemoryRepository(session)

        # Support prefix matching (same pattern as feedback command)
        resolved_id = thread_id
        if len(resolved_id) < 36:
            thread_list = await repo.list_threads(limit=100)
            matches = [t for t in thread_list if t.id.startswith(resolved_id)]
            if not matches:
                message = f"No thread matching '{thread_id}'."
            elif len(matches) > 1:
                lines = [f"Ambiguous prefix '{thread_id}'. Matches:"]
                for m in matches:
                    lines.append(f"  {m.id}  {m.question[:50]}")
                message = "\n".join(lines)
            else:
                resolved_id = matches[0].id

        if not message:
            thread = await repo.get_thread(resolved_id)
            if thread is None:
                message = f"Thread not found: {resolved_id}"
            else:
                votes = await repo.get_votes(resolved_id)

    await engine.dispose()

    if message:
        click.echo(message)
        return

    assert thread is not None
    if fmt == "json":
        output = _format_thread_json(thread, votes)
    elif fmt == "pdf":
        pdf_bytes = _format_thread_pdf(
            thread, votes, content=content, include_dissent=include_dissent
        )
        assert output_path is not None
        Path(output_path).write_bytes(pdf_bytes)
        click.echo(f"PDF exported to {output_path}")
        return
    else:
        output = _format_thread_markdown(
            thread, votes, content=content, include_dissent=include_dissent
        )

    if output_path:
        Path(output_path).write_text(output)
        click.echo(f"Exported to {output_path}")
    else:
        click.echo(output)


def _format_thread_json(
    thread: Thread,
    votes: list[Vote],
) -> str:
    """Format a thread as JSON for export."""
    from datetime import UTC, datetime

    turns_data = []
    for turn in thread.turns:
        contributions_data = []
        for contrib in turn.contributions:
            contributions_data.append(
                {
                    "model_ref": contrib.model_ref,
                    "role": contrib.role,
                    "content": contrib.content,
                    "input_tokens": contrib.input_tokens,
                    "output_tokens": contrib.output_tokens,
                    "cost_usd": contrib.cost_usd,
                }
            )

        decision_data = None
        if turn.decision:
            decision_data = {
                "content": turn.decision.content,
                "confidence": turn.decision.confidence,
                "rigor": turn.decision.rigor,
                "dissent": turn.decision.dissent,
            }

        turns_data.append(
            {
                "round_number": turn.round_number,
                "state": turn.state,
                "contributions": contributions_data,
                "decision": decision_data,
            }
        )

    votes_data = [
        {
            "model_ref": v.model_ref,
            "content": v.content,
        }
        for v in votes
    ]

    export_data = {
        "thread_id": thread.id,
        "question": thread.question,
        "status": thread.status,
        "created_at": thread.created_at.isoformat(),
        "turns": turns_data,
        "votes": votes_data,
        "exported_at": datetime.now(UTC).isoformat(),
    }

    return json_mod.dumps(export_data, indent=2)


def _format_thread_markdown(
    thread: Thread,
    votes: list[Vote],
    *,
    content: str = "full",
    include_dissent: bool = True,
) -> str:
    """Format a thread as Markdown for export.

    Args:
        content: "full" for complete report, "decision" for decision only.
        include_dissent: Whether to include the dissent section.
    """
    lines: list[str] = []
    created = thread.created_at.strftime("%Y-%m-%d")

    total_cost = sum(c.cost_usd for turn in thread.turns for c in turn.contributions)

    # Find the final decision
    final_decision = None
    for turn in reversed(thread.turns):
        if turn.decision:
            final_decision = turn.decision
            break

    lines.append(f"# Consensus: {thread.question}")
    lines.append("")

    # Decision section
    if final_decision:
        lines.append("## Decision")
        lines.append(final_decision.content)
        lines.append("")
        conf_pct = f"{final_decision.confidence:.0%}"
        rigor_pct = f"{final_decision.rigor:.0%}"
        lines.append(f"Confidence: {conf_pct}  Rigor: {rigor_pct}")
        lines.append("")

        if include_dissent and final_decision.dissent:
            lines.append("## Dissent")
            lines.append(final_decision.dissent)
            lines.append("")

    if content == "full":
        lines.append("---")
        lines.append("")
        lines.append("## Consensus Process")
        lines.append("")

        for turn in thread.turns:
            lines.append(f"### Round {turn.round_number}")
            lines.append("")

            proposers = [c for c in turn.contributions if c.role == "proposer"]
            challengers = [c for c in turn.contributions if c.role == "challenger"]
            revisers = [c for c in turn.contributions if c.role == "reviser"]
            others = [
                c
                for c in turn.contributions
                if c.role not in ("proposer", "challenger", "reviser")
            ]

            for p in proposers:
                lines.append(f"#### Proposal ({p.model_ref})")
                lines.append(p.content)
                lines.append("")

            if challengers:
                lines.append("#### Challenges")
                for ch in challengers:
                    lines.append(f"**{ch.model_ref}**: {ch.content}")
                    lines.append("")

            for r in revisers:
                lines.append(f"#### Revision ({r.model_ref})")
                lines.append(r.content)
                lines.append("")

            for o in others:
                role_label = o.role.capitalize()
                lines.append(f"#### {role_label} ({o.model_ref})")
                lines.append(o.content)
                lines.append("")

        if votes:
            lines.append("### Votes")
            for v in votes:
                lines.append(f"**{v.model_ref}**: {v.content}")
                lines.append("")

    lines.append("---")
    lines.append(f"*duh v{__version__} | {created} | Cost: ${total_cost:.4f}*")
    return "\n".join(lines)


def _format_thread_pdf(
    thread: Thread,
    votes: list[Vote],
    *,
    content: str = "full",
    include_dissent: bool = True,
) -> bytes:
    """Format a thread as a research-paper quality PDF.

    Features: repeating header/footer, TOC with bookmarks, provider-colored
    callout boxes, confidence meter, and full Unicode via TTF fonts (with
    graceful fallback to core Helvetica).
    """
    import html as html_mod
    import re
    from datetime import datetime

    from fpdf import FPDF  # type: ignore[import-untyped]

    total_cost = sum(c.cost_usd for turn in thread.turns for c in turn.contributions)
    total_input = sum(
        c.input_tokens for turn in thread.turns for c in turn.contributions
    )
    total_output = sum(
        c.output_tokens for turn in thread.turns for c in turn.contributions
    )
    created = thread.created_at.strftime("%Y-%m-%d")
    exported = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    model_refs = sorted(
        {c.model_ref for turn in thread.turns for c in turn.contributions}
    )

    final_decision = None
    for turn in reversed(thread.turns):
        if turn.decision:
            final_decision = turn.decision
            break

    # ── Provider color map ──────────────────────────────────────
    provider_colors: dict[str, tuple[int, int, int]] = {
        "anthropic": (204, 107, 43),
        "openai": (16, 163, 127),
        "google": (66, 133, 244),
        "mistral": (131, 56, 236),
        "perplexity": (0, 160, 160),
    }
    default_color = (120, 120, 120)

    def _provider_color(model_ref: str) -> tuple[int, int, int]:
        provider = model_ref.split(":")[0].lower() if ":" in model_ref else ""
        return provider_colors.get(provider, default_color)

    # ── PDF subclass with header/footer ─────────────────────────

    class ConsensusReport(FPDF):  # type: ignore[misc]
        """FPDF subclass with repeating header and footer."""

        def __init__(self) -> None:
            super().__init__()
            self._use_ttf = False
            self._font_family = "Helvetica"
            self._mono_family = "Courier"

        def _setup_fonts(self) -> None:
            """Try to load a TTF font for Unicode support."""
            import os

            search_paths = [
                "/System/Library/Fonts/Helvetica.ttc",
                "/System/Library/Fonts/HelveticaNeue.ttc",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/TTF/DejaVuSans.ttf",
            ]
            for path in search_paths:
                if os.path.isfile(path):
                    try:
                        self.add_font("DuhSans", "", path)
                        self.add_font("DuhSans", "B", path)
                        self.add_font("DuhSans", "I", path)
                        self.add_font("DuhSans", "BI", path)
                        self._use_ttf = True
                        self._font_family = "DuhSans"
                        break
                    except Exception:
                        continue

        def header(self) -> None:
            self.set_font(self._font_family, "", 8)
            self.set_text_color(160, 160, 160)
            self.cell(0, 5, "duh consensus report", align="L")
            self.cell(0, 5, exported, align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_draw_color(220, 220, 220)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

        def footer(self) -> None:
            self.set_y(-15)
            self.set_font(self._font_family, "", 8)
            self.set_text_color(160, 160, 160)
            self.set_draw_color(220, 220, 220)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(2)
            self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")
            self.cell(0, 5, f"duh v{__version__}", align="R")

        def _safe(self, text: str) -> str:
            """Make text safe for the current font encoding."""
            if self._use_ttf:
                return text
            for char, repl in (
                ("\u2014", "--"),
                ("\u2013", "-"),
                ("\u2018", "'"),
                ("\u2019", "'"),
                ("\u201c", '"'),
                ("\u201d", '"'),
                ("\u2026", "..."),
                ("\u2022", "*"),
                ("\u00a0", " "),
                ("\u2192", "->"),
                ("\u2190", "<-"),
            ):
                text = text.replace(char, repl)
            return text.encode("latin-1", errors="replace").decode("latin-1")

    # ── Markdown rendering helpers ──────────────────────────────

    def _inline_fmt(text: str) -> str:
        """Convert inline markdown (bold, italic, code) to HTML."""
        parts = re.split(r"(`[^`]+`)", text)
        result: list[str] = []
        for part in parts:
            if part.startswith("`") and part.endswith("`"):
                result.append(
                    f"<font face='{pdf._mono_family}'>"
                    f"{html_mod.escape(part[1:-1])}</font>"
                )
            else:
                escaped = html_mod.escape(part)
                escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
                escaped = re.sub(r"__(.+?)__", r"<b>\1</b>", escaped)
                escaped = re.sub(r"\*(.+?)\*", r"<i>\1</i>", escaped)
                escaped = re.sub(r"_(.+?)_", r"<i>\1</i>", escaped)
                result.append(escaped)
        return "".join(result)

    def _md_to_html(md: str) -> str:
        """Convert markdown to HTML for fpdf2's write_html."""
        lines = md.split("\n")
        parts: list[str] = []
        in_code = False
        in_list = False
        list_tag = "ul"

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("```"):
                if in_code:
                    parts.append("</pre>")
                    in_code = False
                else:
                    if in_list:
                        parts.append(f"</{list_tag}>")
                        in_list = False
                    parts.append("<pre>")
                    in_code = True
                continue

            if in_code:
                parts.append(html_mod.escape(line) + "\n")
                continue

            if not stripped:
                if in_list:
                    parts.append(f"</{list_tag}>")
                    in_list = False
                continue

            m = re.match(r"^#{1,6}\s+(.+)$", stripped)
            if m:
                if in_list:
                    parts.append(f"</{list_tag}>")
                    in_list = False
                parts.append(f"<p><b>{_inline_fmt(m.group(1))}</b></p>")
                continue

            m = re.match(r"^[-*]\s+(.+)$", stripped)
            if m:
                if not in_list or list_tag != "ul":
                    if in_list:
                        parts.append(f"</{list_tag}>")
                    parts.append("<ul>")
                    in_list = True
                    list_tag = "ul"
                parts.append(f"<li>{_inline_fmt(m.group(1))}</li>")
                continue

            m = re.match(r"^\d+[.)]\s+(.+)$", stripped)
            if m:
                if not in_list or list_tag != "ol":
                    if in_list:
                        parts.append(f"</{list_tag}>")
                    parts.append("<ol>")
                    in_list = True
                    list_tag = "ol"
                parts.append(f"<li>{_inline_fmt(m.group(1))}</li>")
                continue

            if in_list:
                parts.append(f"</{list_tag}>")
                in_list = False
            parts.append(f"<p>{_inline_fmt(stripped)}</p>")

        if in_list:
            parts.append(f"</{list_tag}>")
        if in_code:
            parts.append("</pre>")

        return "".join(parts)

    def _write_md(md_text: str) -> None:
        """Render markdown content as formatted PDF."""
        pdf.write_html(pdf._safe(_md_to_html(md_text)))

    # ── Callout box helper ──────────────────────────────────────

    def _draw_accent_bar(
        start_y: float, end_y: float, color: tuple[int, int, int]
    ) -> None:
        """Draw a thick colored accent bar on the left margin."""
        saved_draw = (pdf.draw_color.r, pdf.draw_color.g, pdf.draw_color.b)
        saved_width = pdf.line_width
        pdf.set_draw_color(*color)
        pdf.set_line_width(2.5)
        x = pdf.l_margin - 1
        # Clamp to page content area
        top = max(start_y, pdf.t_margin)
        bot = min(end_y, pdf.h - pdf.b_margin)
        if bot > top:
            pdf.line(x, top, x, bot)
        pdf.set_draw_color(*saved_draw)
        pdf.set_line_width(saved_width)

    def _callout_box(
        model_ref: str,
        role: str,
        body: str,
        *,
        accent: tuple[int, int, int] | None = None,
    ) -> None:
        """Draw a colored callout box with provider accent line."""
        color = accent or _provider_color(model_ref)
        start_y = pdf.get_y()

        # Indent content to leave room for accent bar
        saved_margin = pdf.l_margin
        pdf.set_left_margin(saved_margin + 6)
        pdf.set_x(pdf.l_margin)

        # Header: model + role
        pdf.set_font(pdf._font_family, "B", 9)
        pdf.set_text_color(*color)
        pdf.cell(0, 5, pdf._safe(f"{model_ref}  |  {role.upper()}"))
        pdf.ln(5)

        # Body
        pdf.set_text_color(40, 40, 40)
        pdf.set_font(pdf._font_family, "", 10)
        _write_md(body)
        pdf.ln(2)

        end_y = pdf.get_y()

        # Draw accent bar on left edge (doesn't overlap text)
        _draw_accent_bar(start_y, end_y, color)

        # Restore margin
        pdf.set_left_margin(saved_margin)
        pdf.ln(4)

    # ── Build the PDF ───────────────────────────────────────────

    pdf = ConsensusReport()
    pdf._setup_fonts()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_text_color(40, 40, 40)

    # -- Title page / header area --
    pdf.add_page()

    pdf.set_font(pdf._font_family, "B", 20)
    pdf.multi_cell(0, 10, pdf._safe(thread.question))
    pdf.ln(3)

    # Metadata line
    pdf.set_font(pdf._font_family, "", 9)
    pdf.set_text_color(130, 130, 130)
    meta_parts = [
        f"Thread {thread.id[:8]}",
        f"Created {created}",
        f"{len(model_refs)} model{'s' if len(model_refs) != 1 else ''}",
    ]
    if total_cost > 0:
        meta_parts.append(f"Cost ${total_cost:.4f}")
    pdf.cell(0, 5, pdf._safe("  |  ".join(meta_parts)))
    pdf.ln(6)

    # Horizontal rule
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.5)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(6)
    pdf.set_text_color(40, 40, 40)
    pdf.set_line_width(0.2)

    # -- TOC placeholder --
    if content == "full":
        pdf.insert_toc_placeholder(
            render_toc,
            pages=1,
        )

    # -- Decision section --
    if final_decision:
        pdf.start_section("Decision")
        pdf.set_font(pdf._font_family, "B", 15)
        pdf.cell(0, 8, "Decision")
        pdf.ln(8)

        decision_start_y = pdf.get_y()

        # Indent for accent bar
        pdf.set_left_margin(16)
        pdf.set_x(16)

        # Decision content
        pdf.set_font(pdf._font_family, "", 11)
        pdf.set_text_color(40, 40, 40)
        _write_md(final_decision.content)
        pdf.ln(4)

        # Confidence meter
        conf_pct = final_decision.confidence
        pdf.set_font(pdf._font_family, "B", 10)
        pdf.cell(30, 6, pdf._safe(f"Confidence: {conf_pct:.0%}"))
        bar_x = pdf.get_x() + 2
        bar_y = pdf.get_y() + 1
        bar_w = 60
        bar_h = 4
        pdf.set_fill_color(230, 230, 230)
        pdf.rect(bar_x, bar_y, bar_w, bar_h, style="F")
        g = int(100 + 155 * conf_pct)
        pdf.set_fill_color(40, min(g, 200), 80)
        pdf.rect(bar_x, bar_y, bar_w * conf_pct, bar_h, style="F")
        pdf.ln(10)

        # Rigor meter
        rigor_pct = final_decision.rigor
        pdf.set_font(pdf._font_family, "B", 10)
        pdf.cell(30, 6, pdf._safe(f"Rigor: {rigor_pct:.0%}"))
        bar_x = pdf.get_x() + 2
        bar_y = pdf.get_y() + 1
        pdf.set_fill_color(230, 230, 230)
        pdf.rect(bar_x, bar_y, bar_w, bar_h, style="F")
        g = int(100 + 155 * rigor_pct)
        pdf.set_fill_color(40, min(g, 200), 80)
        pdf.rect(bar_x, bar_y, bar_w * rigor_pct, bar_h, style="F")
        pdf.ln(10)

        # Draw green accent bar
        _draw_accent_bar(decision_start_y, pdf.get_y(), (40, 160, 80))
        pdf.set_left_margin(10)

        # Dissent
        if include_dissent and final_decision.dissent:
            pdf.start_section("Dissent", level=1)
            pdf.set_font(pdf._font_family, "B", 13)
            pdf.set_text_color(40, 40, 40)
            pdf.cell(0, 8, "Dissent")
            pdf.ln(6)

            dissent_start_y = pdf.get_y()
            pdf.set_left_margin(16)
            pdf.set_x(16)

            pdf.set_font(pdf._font_family, "I", 10)
            pdf.set_text_color(100, 100, 100)
            _write_md(final_decision.dissent)
            pdf.ln(4)

            # Amber accent bar
            _draw_accent_bar(dissent_start_y, pdf.get_y(), (200, 140, 80))
            pdf.set_left_margin(10)
            pdf.set_text_color(40, 40, 40)

    # -- Consensus process --
    if content == "full":
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)

        pdf.start_section("Consensus Process")
        pdf.set_font(pdf._font_family, "B", 15)
        pdf.cell(0, 8, "Consensus Process")
        pdf.ln(8)

        for turn in thread.turns:
            section_title = f"Round {turn.round_number}"
            pdf.start_section(section_title, level=1)
            pdf.set_font(pdf._font_family, "B", 13)
            pdf.set_text_color(80, 80, 80)
            pdf.cell(0, 7, section_title)
            pdf.ln(7)
            pdf.set_text_color(40, 40, 40)

            for c in turn.contributions:
                _callout_box(c.model_ref, c.role, c.content)

        # Votes
        if votes:
            pdf.start_section("Votes", level=1)
            pdf.set_font(pdf._font_family, "B", 13)
            pdf.cell(0, 8, "Votes")
            pdf.ln(6)

            for v in votes:
                color = _provider_color(v.model_ref)
                pdf.set_font(pdf._font_family, "B", 10)
                pdf.set_text_color(*color)
                pdf.cell(55, 6, pdf._safe(v.model_ref))
                pdf.set_font(pdf._font_family, "", 10)
                pdf.set_text_color(60, 60, 60)
                pdf.cell(0, 6, pdf._safe(v.content))
                pdf.ln(6)

            pdf.ln(4)
            pdf.set_text_color(40, 40, 40)

    # -- Appendix: metadata footer ───────────────────────────────
    pdf.ln(4)
    pdf.set_draw_color(200, 200, 200)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    pdf.set_font(pdf._font_family, "", 8)
    pdf.set_text_color(140, 140, 140)
    footer_parts = [
        f"Cost: ${total_cost:.4f}",
        f"Tokens: {total_input:,} in / {total_output:,} out",
        f"Models: {', '.join(model_refs)}",
    ]
    pdf.cell(0, 4, pdf._safe("  |  ".join(footer_parts)))
    pdf.set_text_color(40, 40, 40)

    return bytes(pdf.output())


def render_toc(pdf: object, outline: list[object]) -> None:
    """Render a table of contents page for the PDF.

    Called by fpdf2's ``insert_toc_placeholder`` mechanism.
    """
    from fpdf import FPDF

    assert isinstance(pdf, FPDF)
    font = getattr(pdf, "_font_family", "Helvetica")
    pdf.set_font(font, "B", 15)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 10, "Table of Contents")
    pdf.ln(10)

    for entry in outline:
        level = getattr(entry, "level", 0)
        name = getattr(entry, "name", "")
        page_number = getattr(entry, "page_number", 0)
        link = getattr(entry, "link", None)

        indent = 4 * level
        pdf.set_x(pdf.l_margin + indent)

        if level == 0:
            pdf.set_font(font, "B", 11)
        else:
            pdf.set_font(font, "", 10)

        pdf.set_text_color(60, 60, 60)
        w = pdf.w - pdf.l_margin - pdf.r_margin - indent - 15
        # Use safe method if available
        safe = getattr(pdf, "_safe", lambda t: t)
        pdf.cell(w, 6, safe(name), link=link)
        pdf.cell(15, 6, str(page_number), align="R")
        pdf.ln(6)


# ── models ───────────────────────────────────────────────────────


@cli.command()
@click.pass_context
def models(ctx: click.Context) -> None:
    """List configured providers and available models."""
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_models_async(config))
    except DuhError as e:
        _error(str(e))


async def _models_async(config: DuhConfig) -> None:
    """Async implementation for the models command."""
    pm = await _setup_providers(config)
    all_models = pm.list_all_models()

    if not all_models:
        click.echo("No models available.")
        click.echo(
            "Configure providers in ~/.config/duh/config.toml "
            "or set API key environment variables."
        )
        return

    # Group by provider
    by_provider: dict[str, list[ModelInfo]] = {}
    for model in all_models:
        by_provider.setdefault(model.provider_id, []).append(model)

    for provider_id, model_list in sorted(by_provider.items()):
        click.echo(f"{provider_id}:")
        for m in model_list:
            role = "challenger-only" if not m.proposer_eligible else ""
            suffix = f"  [{role}]" if role else ""
            click.echo(
                f"  {m.display_name} ({m.model_id})  "
                f"ctx:{m.context_window:,}  "
                f"in:${m.input_cost_per_mtok}/Mtok  "
                f"out:${m.output_cost_per_mtok}/Mtok{suffix}"
            )
        click.echo()


# ── cost ─────────────────────────────────────────────────────────


@cli.command()
@click.pass_context
def cost(ctx: click.Context) -> None:
    """Show cumulative cost from stored contributions."""
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_cost_async(config))
    except DuhError as e:
        _error(str(e))


async def _cost_async(config: DuhConfig) -> None:
    """Async implementation for the cost command."""
    from sqlalchemy import func, select

    from duh.memory.models import Contribution

    factory, engine = await _create_db(config)
    async with factory() as session:
        # Total cost
        stmt = select(func.sum(Contribution.cost_usd))
        result = await session.execute(stmt)
        total = result.scalar() or 0.0

        # Total tokens
        stmt_in = select(func.sum(Contribution.input_tokens))
        stmt_out = select(func.sum(Contribution.output_tokens))
        result_in = await session.execute(stmt_in)
        result_out = await session.execute(stmt_out)
        total_input = result_in.scalar() or 0
        total_output = result_out.scalar() or 0

        # Cost by model
        stmt_by_model = (
            select(
                Contribution.model_ref,
                func.sum(Contribution.cost_usd),
                func.count(Contribution.id),
            )
            .group_by(Contribution.model_ref)
            .order_by(func.sum(Contribution.cost_usd).desc())
        )
        result_by_model = await session.execute(stmt_by_model)
        by_model = result_by_model.all()

    await engine.dispose()

    click.echo(f"Total cost: ${total:.4f}")
    click.echo(f"Total tokens: {total_input:,} input + {total_output:,} output")

    if by_model:
        click.echo()
        click.echo("By model:")
        for model_ref, model_cost, call_count in by_model:
            click.echo(f"  {model_ref}: ${model_cost:.4f} ({call_count} calls)")


# ── calibration ──────────────────────────────────────────────────


@cli.command()
@click.option("--category", default=None, help="Filter by decision category.")
@click.option("--since", default=None, help="Only decisions after this date (ISO).")
@click.option("--until", default=None, help="Only decisions before this date (ISO).")
@click.pass_context
def calibration(
    ctx: click.Context,
    category: str | None,
    since: str | None,
    until: str | None,
) -> None:
    """Show confidence calibration analysis.

    Compares predicted confidence against actual outcomes to
    measure how well-calibrated the consensus engine is.
    """
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_calibration_async(config, category, since, until))
    except DuhError as e:
        _error(str(e))


async def _calibration_async(
    config: DuhConfig,
    category: str | None,
    since: str | None,
    until: str | None,
) -> None:
    """Async implementation for the calibration command."""
    from duh.calibration import compute_calibration
    from duh.memory.repository import MemoryRepository

    factory, engine = await _create_db(config)
    async with factory() as session:
        repo = MemoryRepository(session)
        decisions = await repo.get_all_decisions_for_space(
            category=category,
            since=since,
            until=until,
        )

    await engine.dispose()

    result = compute_calibration(decisions)

    if result.total_decisions == 0:
        click.echo("No decisions found.")
        return

    click.echo(f"Total decisions: {result.total_decisions}")
    click.echo(f"With outcomes: {result.total_with_outcomes}")
    click.echo(f"Overall accuracy: {result.overall_accuracy:.1%}")
    click.echo(f"ECE: {result.ece:.4f}")

    if result.ece < 0.05:
        rating = "excellent"
    elif result.ece < 0.10:
        rating = "good"
    elif result.ece < 0.20:
        rating = "fair"
    else:
        rating = "poor"
    click.echo(f"Calibration: {rating}")

    if result.total_with_outcomes > 0:
        click.echo()
        click.echo(
            f"{'Range':<12} {'Count':>6} {'Outcomes':>9} "
            f"{'Accuracy':>9} {'Conf':>6} {'Gap':>6}"
        )
        for b in result.buckets:
            if b.count == 0:
                continue
            lo_pct = f"{b.range_lo:.0%}"
            hi_pct = f"{b.range_hi:.0%}"
            label = f"{lo_pct}-{hi_pct}"
            acc_str = f"{b.accuracy:.1%}" if b.with_outcomes > 0 else "-"
            conf_str = f"{b.mean_confidence:.1%}"
            gap_str = (
                f"{abs(b.accuracy - b.mean_confidence):.1%}"
                if b.with_outcomes > 0
                else "-"
            )
            click.echo(
                f"{label:<12} {b.count:>6} {b.with_outcomes:>9} "
                f"{acc_str:>9} {conf_str:>6} {gap_str:>6}"
            )


# ── backup ───────────────────────────────────────────────────────


@cli.command()
@click.argument("path", type=click.Path())
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["auto", "sqlite", "json"]),
    default="auto",
    help="Backup format (auto detects from db type).",
)
@click.option("--config", "config_path", default=None, help="Config file path.")
def backup(path: str, fmt: str, config_path: str | None) -> None:
    """Backup the duh database to PATH."""
    config = _load_config(config_path)
    try:
        asyncio.run(_backup_async(config, path, fmt))
    except (DuhError, ValueError, FileNotFoundError, OSError) as e:
        _error(str(e))


async def _backup_async(config: DuhConfig, path: str, fmt: str) -> None:
    """Async implementation for the backup command."""
    from duh.memory.backup import backup_json, backup_sqlite, detect_db_type

    db_url = config.database.url
    if "~" in db_url:
        db_url = db_url.replace("~", str(Path.home()))

    db_type = detect_db_type(db_url)
    dest = Path(path)

    if fmt == "auto":
        fmt = "sqlite" if db_type == "sqlite" else "json"

    if fmt == "sqlite" and db_type != "sqlite":
        _error("Cannot use sqlite backup format for a PostgreSQL database.")

    if fmt == "sqlite":
        result_path = await backup_sqlite(db_url, dest)
    else:
        factory, engine = await _create_db(config)
        async with factory() as session:
            result_path = await backup_json(session, dest)
        await engine.dispose()

    size = result_path.stat().st_size
    if size < 1024:
        size_str = f"{size} B"
    elif size < 1024 * 1024:
        size_str = f"{size / 1024:.1f} KB"
    else:
        size_str = f"{size / (1024 * 1024):.1f} MB"

    click.echo(f"Backup saved to {result_path} ({size_str})")


# ── restore ─────────────────────────────────────────────────────


@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option(
    "--merge",
    is_flag=True,
    default=False,
    help="Merge with existing data instead of replacing.",
)
@click.option("--config", "config_path", default=None, help="Config file path.")
def restore(path: str, merge: bool, config_path: str | None) -> None:
    """Restore the duh database from PATH."""
    config = _load_config(config_path)
    try:
        asyncio.run(_restore_async(config, path, merge))
    except (DuhError, ValueError, FileNotFoundError, OSError) as e:
        _error(str(e))


async def _restore_async(config: DuhConfig, path: str, merge: bool) -> None:
    """Async implementation for the restore command."""
    from duh.memory.backup import (
        detect_backup_format,
        detect_db_type,
        restore_json,
        restore_sqlite,
    )

    db_url = config.database.url
    if "~" in db_url:
        db_url = db_url.replace("~", str(Path.home()))

    source = Path(path)
    fmt = detect_backup_format(source)
    db_type = detect_db_type(db_url)

    if fmt == "sqlite" and db_type != "sqlite":
        _error("Cannot restore a SQLite backup into a PostgreSQL database.")

    if fmt == "sqlite":
        await restore_sqlite(source, db_url)
        click.echo(f"Restored SQLite database from {source}")
    else:
        factory, engine = await _create_db(config)
        async with factory() as session:
            counts = await restore_json(session, source, merge=merge)
        await engine.dispose()

        total = sum(counts.values())
        mode = "Merged" if merge else "Restored"
        click.echo(f"{mode} {total} records from {source}")
        for table_name, count in counts.items():
            if count > 0:
                click.echo(f"  {table_name}: {count}")


# ── serve ────────────────────────────────────────────────────────


@cli.command()
@click.option("--host", default=None, help="Host to bind to (overrides config).")
@click.option(
    "--port", type=int, default=None, help="Port to bind to (overrides config)."
)
@click.option(
    "--reload", is_flag=True, default=False, help="Enable auto-reload for development."
)
@click.pass_context
def serve(ctx: click.Context, host: str | None, port: int | None, reload: bool) -> None:
    """Start the REST API server with web UI."""
    import uvicorn

    from duh.api.app import create_app

    config = _load_config(ctx.obj["config_path"])

    effective_host = host or config.api.host
    effective_port = port or config.api.port

    # Check for frontend build
    from pathlib import Path

    dist_dir = Path(__file__).resolve().parents[2].parent / "web" / "dist"
    if dist_dir.is_dir():
        url = f"http://{effective_host}:{effective_port}"
        click.echo(f"Web UI: {url}")
    else:
        click.echo("Web UI not built. Run: cd web && npm run build")

    app = create_app(config)
    uvicorn.run(
        app,
        host=effective_host,
        port=effective_port,
        reload=reload,
    )


# ── mcp ─────────────────────────────────────────────────────────


@cli.command()
@click.pass_context
def mcp(ctx: click.Context) -> None:
    """Start the MCP server for AI agent integration."""
    from duh.mcp.server import run_server

    asyncio.run(run_server())


# ── batch ───────────────────────────────────────────────────────


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--protocol",
    type=click.Choice(["consensus", "voting", "auto"]),
    default="consensus",
    help="Protocol for each question.",
)
@click.option(
    "--rounds",
    type=int,
    default=None,
    help="Max consensus rounds.",
)
@click.option(
    "--format",
    "output_fmt",
    type=click.Choice(["text", "json"]),
    default="text",
    help="Output format.",
)
@click.pass_context
def batch(
    ctx: click.Context,
    file: str,
    protocol: str,
    rounds: int | None,
    output_fmt: str,
) -> None:
    """Run consensus on multiple questions from a file.

    FILE can be a text file (one question per line) or JSONL
    (each line is {"question": "..."}).
    """
    config = _load_config(ctx.obj["config_path"])
    if rounds is not None:
        config.general.max_rounds = rounds

    try:
        questions = _parse_batch_file(file, protocol)
    except (OSError, ValueError) as e:
        _error(str(e))
        return  # unreachable

    if not questions:
        _error("No questions found in file.")
        return  # unreachable

    try:
        asyncio.run(_batch_async(questions, config, output_fmt))
    except DuhError as e:
        _error(str(e))


def _parse_batch_file(
    file_path: str,
    default_protocol: str,
) -> list[dict[str, str]]:
    """Parse a batch file into a list of question dicts.

    Returns list of {"question": "...", "protocol": "..."}.
    Auto-detects JSONL vs plain text by trying to parse the first
    non-empty line as JSON.
    """
    path = Path(file_path)
    lines = path.read_text(encoding="utf-8").splitlines()

    # Find first non-empty line to detect format
    first_content_line: str | None = None
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            first_content_line = stripped
            break

    if first_content_line is None:
        return []

    # Detect JSONL format
    is_jsonl = False
    try:
        parsed = json_mod.loads(first_content_line)
        if isinstance(parsed, dict) and "question" in parsed:
            is_jsonl = True
    except (json_mod.JSONDecodeError, ValueError):
        pass

    questions: list[dict[str, str]] = []

    if is_jsonl:
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                entry = json_mod.loads(stripped)
            except json_mod.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {i}: {e}") from e
            if not isinstance(entry, dict) or "question" not in entry:
                raise ValueError(
                    f"Line {i}: each JSON line must have a 'question' field"
                )
            questions.append(
                {
                    "question": entry["question"],
                    "protocol": entry.get("protocol", default_protocol),
                }
            )
    else:
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            questions.append(
                {
                    "question": stripped,
                    "protocol": default_protocol,
                }
            )

    return questions


async def _batch_async(
    questions: list[dict[str, str]],
    config: DuhConfig,
    output_fmt: str,
) -> None:
    """Async implementation for the batch command."""
    pm = await _setup_providers(config)

    if not pm.list_all_models():
        _error(
            "No models available. Configure providers in "
            "~/.config/duh/config.toml or set API key environment variables."
        )

    total = len(questions)
    results: list[dict[str, object]] = []
    total_cost = 0.0
    start_time = time.monotonic()

    for i, q in enumerate(questions, 1):
        question = q["question"]
        q_protocol = q["protocol"]
        truncated = question[:60] + ("..." if len(question) > 60 else "")

        if output_fmt == "text":
            header = f"── Question {i}/{total} "
            click.echo(f"\n{header:─<60}")
            click.echo(f"Q: {truncated}")

        cost_before = pm.total_cost

        try:
            if q_protocol == "voting":
                from duh.consensus.voting import run_voting

                aggregation = config.voting.aggregation
                vr = await run_voting(question, pm, aggregation=aggregation)
                decision = vr.decision or ""
                confidence = vr.confidence
                rigor = vr.rigor
            else:
                decision, confidence, rigor, _dissent, _cost = await _run_consensus(
                    question, config, pm
                )

            q_cost = pm.total_cost - cost_before
            total_cost += q_cost

            results.append(
                {
                    "question": question,
                    "decision": decision,
                    "confidence": confidence,
                    "rigor": rigor,
                    "cost": round(q_cost, 4),
                }
            )

            if output_fmt == "text":
                click.echo(f"Decision: {decision[:200]}")
                click.echo(f"Confidence: {confidence:.0%}  Rigor: {rigor:.0%}")
                click.echo(f"Cost: ${q_cost:.4f}")

        except Exception as e:
            q_cost = pm.total_cost - cost_before
            total_cost += q_cost
            results.append(
                {
                    "question": question,
                    "error": str(e),
                    "confidence": 0.0,
                    "rigor": 0.0,
                    "cost": round(q_cost, 4),
                }
            )
            if output_fmt == "text":
                click.echo(f"Error: {e}")

    elapsed = time.monotonic() - start_time

    if output_fmt == "json":
        output = {
            "results": results,
            "summary": {
                "total_questions": total,
                "total_cost": round(total_cost, 4),
                "elapsed_seconds": round(elapsed, 1),
            },
        }
        click.echo(json_mod.dumps(output, indent=2))
    else:
        click.echo("\n── Summary ──────────────────────────────────────────────")
        click.echo(
            f"{total} questions | Total cost: ${total_cost:.4f} "
            f"| Elapsed: {elapsed:.1f}s"
        )


# ── user-create ─────────────────────────────────────────────


@cli.command("user-create")
@click.option("--email", required=True)
@click.option("--password", required=True)
@click.option("--name", "display_name", required=True)
@click.option(
    "--role",
    type=click.Choice(["admin", "contributor", "viewer"]),
    default="contributor",
)
@click.option("--config", "config_path", default=None)
def user_create(
    email: str,
    password: str,
    display_name: str,
    role: str,
    config_path: str | None,
) -> None:
    """Create a new user."""
    config = _load_config(config_path)
    try:
        asyncio.run(_user_create_async(config, email, password, display_name, role))
    except DuhError as e:
        _error(str(e))


async def _user_create_async(
    config: DuhConfig,
    email: str,
    password: str,
    display_name: str,
    role: str,
) -> None:
    """Async implementation for the user-create command."""
    from sqlalchemy import select

    from duh.api.auth import hash_password
    from duh.memory.models import User

    factory, engine = await _create_db(config)
    async with factory() as session:
        # Check email uniqueness
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            await engine.dispose()
            _error(f"Email already registered: {email}")

        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    await engine.dispose()
    click.echo(f"User created: {user.id} ({user.email}) role={user.role}")


# ── user-list ───────────────────────────────────────────────


@cli.command("user-list")
@click.option("--config", "config_path", default=None)
def user_list(config_path: str | None) -> None:
    """List all users."""
    config = _load_config(config_path)
    try:
        asyncio.run(_user_list_async(config))
    except DuhError as e:
        _error(str(e))


async def _user_list_async(config: DuhConfig) -> None:
    """Async implementation for the user-list command."""
    from sqlalchemy import select

    from duh.memory.models import User

    factory, engine = await _create_db(config)
    async with factory() as session:
        stmt = select(User).order_by(User.created_at)
        result = await session.execute(stmt)
        users = result.scalars().all()

    await engine.dispose()

    if not users:
        click.echo("No users found.")
        return

    for user in users:
        active = "active" if user.is_active else "disabled"
        click.echo(
            f"  {user.id[:8]}  {user.email}  {user.display_name}  "
            f"role={user.role}  {active}"
        )
