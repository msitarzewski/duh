"""Main CLI application.

Click commands for the duh consensus engine: ask, recall, threads,
show, models, cost.
"""

from __future__ import annotations

import asyncio
import sys
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
    from duh.providers.base import ModelInfo
    from duh.providers.manager import ProviderManager


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
        if prov_config.api_key is None and name in ("anthropic", "openai", "google"):
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

    return pm


async def _run_consensus(
    question: str,
    config: DuhConfig,
    pm: ProviderManager,
    display: ConsensusDisplay | None = None,
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
                await handle_propose(ctx, pm, proposer)
            display.show_propose(proposer, ctx.proposal or "")
        else:
            await handle_propose(ctx, pm, proposer)

        # CHALLENGE
        sm.transition(ConsensusState.CHALLENGE)
        challengers = select_challengers(pm, proposer)
        if display:
            detail = f"{len(challengers)} models"
            with display.phase_status("CHALLENGE", detail):
                await handle_challenge(ctx, pm, challengers)
            display.show_challenges(ctx.challenges)
        else:
            await handle_challenge(ctx, pm, challengers)

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
@click.pass_context
def ask(ctx: click.Context, question: str, rounds: int | None) -> None:
    """Run a consensus query.

    Sends QUESTION to multiple LLMs, challenges their answers,
    and produces a revised consensus decision.
    """
    config = _load_config(ctx.obj["config_path"])
    if rounds is not None:
        config.general.max_rounds = rounds

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

    display = ConsensusDisplay()
    display.start()
    return await _run_consensus(question, config, pm, display=display)


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

    await engine.dispose()

    if thread is None:
        click.echo(f"Thread not found: {thread_id}")
        return

    click.echo(f"Question: {thread.question}")
    click.echo(f"Status: {thread.status}")
    click.echo(f"Created: {thread.created_at.strftime('%Y-%m-%d %H:%M')}")
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
            click.echo()


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
