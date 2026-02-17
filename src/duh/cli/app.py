"""Main CLI application.

Click commands for the duh consensus engine: ask, recall, threads,
show, models, cost, batch.
"""

from __future__ import annotations

import asyncio
import json as json_mod
import sys
import time
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

    engine = create_async_engine(url)

    # Enable foreign keys for SQLite
    if url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _enable_fks(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

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
        ):
            continue  # Skip providers without API keys

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
) -> tuple[str, float, str | None, float]:
    """Run the full consensus loop.

    Returns (decision, confidence, dissent, total_cost).
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

    for _round in range(config.general.max_rounds):
        # PROPOSE
        sm.transition(ConsensusState.PROPOSE)
        if display:
            display.round_header(ctx.current_round, config.general.max_rounds)

        proposer = select_proposer(pm)
        if display:
            with display.phase_status("PROPOSE", proposer):
                await handle_propose(ctx, pm, proposer, tool_registry=tool_registry)
            display.show_propose(proposer, ctx.proposal or "")
        else:
            await handle_propose(ctx, pm, proposer, tool_registry=tool_registry)

        # CHALLENGE
        sm.transition(ConsensusState.CHALLENGE)
        challengers = select_challengers(pm, proposer)
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
        await handle_commit(ctx)
        if display:
            display.show_commit(ctx.confidence, ctx.dissent)
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
@click.pass_context
def ask(
    ctx: click.Context,
    question: str,
    rounds: int | None,
    decompose: bool,
    protocol: str | None,
    tools: bool | None,
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
        result = asyncio.run(_ask_async(question, config))
    except DuhError as e:
        _error(str(e))
        return  # unreachable

    decision, confidence, dissent, cost = result

    from duh.cli.display import ConsensusDisplay

    display = ConsensusDisplay()
    display.show_final_decision(decision, confidence, cost, dissent)


async def _ask_async(
    question: str,
    config: DuhConfig,
) -> tuple[str, float, str | None, float]:
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
        question, config, pm, display=display, tool_registry=tool_registry
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
        decision, confidence, dissent, cost = await _run_consensus(
            question, config, pm, display=display
        )
        display.show_final_decision(decision, confidence, cost, dissent)


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
        decision, confidence, dissent, cost = result
        display.show_final_decision(decision, confidence, cost, dissent)
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
            click.echo(f"    Confidence: {latest.confidence:.0%}")
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
            click.echo(f"  Decision (confidence {turn.decision.confidence:.0%}):")
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
    type=click.Choice(["json", "markdown"]),
    default="json",
    help="Export format.",
)
@click.pass_context
def export(ctx: click.Context, thread_id: str, fmt: str) -> None:
    """Export a thread with full debate history.

    THREAD_ID can be the full UUID or a prefix (minimum 8 chars).
    """
    config = _load_config(ctx.obj["config_path"])
    try:
        asyncio.run(_export_async(config, thread_id, fmt))
    except DuhError as e:
        _error(str(e))


async def _export_async(config: DuhConfig, thread_id: str, fmt: str) -> None:
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
        click.echo(_format_thread_json(thread, votes))
    else:
        click.echo(_format_thread_markdown(thread, votes))


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
) -> str:
    """Format a thread as Markdown for export."""
    lines: list[str] = []
    created = thread.created_at.strftime("%Y-%m-%d")
    lines.append(f"# Thread: {thread.question}")
    lines.append(f"**Status**: {thread.status} | **Created**: {created}")
    lines.append("")

    if votes:
        lines.append("## Votes")
        for v in votes:
            lines.append(f"**{v.model_ref}**: {v.content}")
            lines.append("")

    for turn in thread.turns:
        lines.append(f"## Round {turn.round_number}")

        for contrib in turn.contributions:
            role_label = contrib.role.capitalize()
            lines.append(f"### {role_label} ({contrib.model_ref})")
            lines.append(contrib.content)
            lines.append("")

        if turn.decision:
            lines.append("### Decision")
            conf_pct = f"{turn.decision.confidence:.0%}"
            dissent_part = (
                f" | **Dissent**: {turn.decision.dissent}"
                if turn.decision.dissent
                else ""
            )
            lines.append(f"**Confidence**: {conf_pct}{dissent_part}")
            lines.append(turn.decision.content)
            lines.append("")

    lines.append("---")
    lines.append(f"*Exported from duh v{__version__}*")
    return "\n".join(lines)


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
            click.echo(
                f"  {m.display_name} ({m.model_id})  "
                f"ctx:{m.context_window:,}  "
                f"in:${m.input_cost_per_mtok}/Mtok  "
                f"out:${m.output_cost_per_mtok}/Mtok"
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
            else:
                decision, confidence, _dissent, _cost = await _run_consensus(
                    question, config, pm
                )

            q_cost = pm.total_cost - cost_before
            total_cost += q_cost

            results.append(
                {
                    "question": question,
                    "decision": decision,
                    "confidence": confidence,
                    "cost": round(q_cost, 4),
                }
            )

            if output_fmt == "text":
                click.echo(f"Decision: {decision[:200]}")
                click.echo(f"Confidence: {confidence:.0%}")
                click.echo(f"Cost: ${q_cost:.4f}")

        except Exception as e:
            q_cost = pm.total_cost - cost_before
            total_cost += q_cost
            results.append(
                {
                    "question": question,
                    "error": str(e),
                    "confidence": 0.0,
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
