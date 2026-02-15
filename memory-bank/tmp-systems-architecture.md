# duh — Technical Architecture Blueprint

**Author**: Systems Architect Agent
**Date**: 2026-02-15
**Status**: Draft for team review
**References**: `projectbrief.md`, `techContext.md`, `decisions.md`, `competitive-landscape.md`

---

## Table of Contents

1. [Python Project Structure](#1-python-project-structure)
2. [Provider Adapter Interface](#2-provider-adapter-interface)
3. [Consensus Protocol State Machine](#3-consensus-protocol-state-machine)
4. [SQLAlchemy Memory Schema](#4-sqlalchemy-memory-schema)
5. [CLI Architecture](#5-cli-architecture)
6. [Testing Strategy](#6-testing-strategy)
7. [Configuration Format](#7-configuration-format)
8. [Error Handling Patterns](#8-error-handling-patterns)
9. [Async Patterns](#9-async-patterns)
10. [Docker Setup](#10-docker-setup)

---

## 1. Python Project Structure

### Rationale

Monorepo with a single installable package (`duh`). No premature splitting into separate packages — the system is one product with clear internal module boundaries. If federation (Phase 4) requires a standalone navigator package, split then.

Package management via `uv` (fast, handles lockfiles, replaces pip/pip-tools/poetry). pyproject.toml as the single source of truth.

### Directory Tree

```
duh/
├── pyproject.toml                  # Package metadata, dependencies, scripts
├── uv.lock                         # Locked dependency versions
├── Dockerfile                      # Production container
├── docker-compose.yml              # Local dev with persistence
├── alembic.ini                     # Database migration config
├── alembic/
│   ├── env.py
│   ├── versions/                   # Migration scripts
│   └── script.py.mako
├── config/
│   └── default.toml                # Default configuration
├── src/
│   └── duh/
│       ├── __init__.py             # Package version, top-level exports
│       ├── __main__.py             # Entry point: `python -m duh`
│       ├── cli/
│       │   ├── __init__.py
│       │   ├── app.py              # CLI entry, argument parsing
│       │   ├── console.py          # Rich console setup, shared console instance
│       │   ├── panels.py           # Live display panels (proposal, challenge, status)
│       │   └── formatters.py       # Output formatting for consensus results
│       ├── consensus/
│       │   ├── __init__.py
│       │   ├── engine.py           # ConsensusEngine — top-level orchestrator
│       │   ├── states.py           # State machine: states, transitions, handlers
│       │   ├── decomposer.py       # Task decomposition logic
│       │   ├── challenger.py       # Challenge prompt generation, devil's advocate
│       │   ├── synthesizer.py      # Revision/synthesis of feedback
│       │   └── types.py            # Data classes for consensus phases
│       ├── providers/
│       │   ├── __init__.py
│       │   ├── base.py             # Abstract base: ModelProvider protocol
│       │   ├── registry.py         # Provider discovery, instantiation from config
│       │   ├── manager.py          # ProviderManager — routing, health, cost tracking
│       │   ├── anthropic.py        # Claude adapter
│       │   ├── openai.py           # GPT / o-series adapter (also covers local OpenAI-compat)
│       │   ├── google.py           # Gemini adapter
│       │   └── ollama.py           # Ollama-specific adapter (model listing, pull, etc.)
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── models.py           # SQLAlchemy ORM models (all three layers)
│       │   ├── session.py          # Async session factory, engine setup
│       │   ├── repository.py       # Data access layer (queries, inserts)
│       │   ├── summarizer.py       # Turn/thread summary generation
│       │   └── context.py          # Context builder: what to pass to models
│       ├── config/
│       │   ├── __init__.py
│       │   ├── schema.py           # Pydantic models for config validation
│       │   └── loader.py           # TOML loading, env var overrides, merging
│       └── core/
│           ├── __init__.py
│           ├── errors.py           # Exception hierarchy
│           ├── events.py           # Internal event bus for UI updates
│           ├── cost.py             # Token counting, cost calculation
│           └── logging.py          # Structured logging setup
├── tests/
│   ├── conftest.py                 # Shared fixtures: mock providers, test DB
│   ├── unit/
│   │   ├── test_consensus_states.py
│   │   ├── test_providers.py
│   │   ├── test_memory_models.py
│   │   ├── test_cost.py
│   │   ├── test_config.py
│   │   └── test_context_builder.py
│   ├── integration/
│   │   ├── test_consensus_loop.py
│   │   ├── test_memory_persistence.py
│   │   └── test_provider_registry.py
│   └── fixtures/
│       ├── providers.py            # Mock provider implementations
│       ├── responses.py            # Canned model responses for deterministic tests
│       └── database.py             # In-memory SQLite fixtures
└── docs/
    ├── architecture.md             # This document (promoted from memory-bank)
    ├── consensus-protocol.md       # Detailed protocol specification
    └── provider-guide.md           # How to add a new provider adapter
```

### Key Structural Decisions

- **`src/` layout**: Prevents accidental imports from the project root. Standard modern Python packaging practice.
- **`providers/` separate from `consensus/`**: Providers are stateless adapters. Consensus is the state machine. Clean dependency direction: consensus depends on providers, not the reverse.
- **`memory/` owns all persistence**: Single module for all database operations. No scattered SQL across the codebase.
- **`core/` for cross-cutting concerns**: Errors, events, cost tracking, logging. Used by all other modules.
- **Alembic at the root**: Database migrations are a first-class concern, not buried inside the package.

---

## 2. Provider Adapter Interface

### Design: Protocol (Structural Typing) over ABC

Using `typing.Protocol` rather than `abc.ABC`. This means any class that implements the right methods is a valid provider — no inheritance required. This is important because some providers (OpenAI-compatible locals) may share an implementation class with different configurations, not different base classes.

### Interface Definition

```python
# src/duh/providers/base.py

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol, runtime_checkable


class ModelCapability(enum.Flag):
    """Capabilities a model may or may not support."""
    TEXT = enum.auto()
    STREAMING = enum.auto()
    TOOL_USE = enum.auto()
    VISION = enum.auto()
    JSON_MODE = enum.auto()
    SYSTEM_PROMPT = enum.auto()


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Static metadata about a model available through a provider."""
    provider_id: str          # e.g. "anthropic", "openai", "ollama"
    model_id: str             # e.g. "claude-opus-4-6", "gpt-5.2", "llama3:70b"
    display_name: str         # Human-readable: "Claude Opus 4.6"
    capabilities: ModelCapability
    context_window: int       # Max tokens (input + output)
    max_output_tokens: int    # Max output tokens
    input_cost_per_mtok: float   # USD per million input tokens (0.0 for local)
    output_cost_per_mtok: float  # USD per million output tokens (0.0 for local)
    is_local: bool = False


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Token counts from a single model call."""
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass(slots=True)
class ModelResponse:
    """Complete response from a model call."""
    content: str
    model_info: ModelInfo
    usage: TokenUsage
    finish_reason: str        # "stop", "max_tokens", "tool_use"
    latency_ms: float         # Wall-clock time for the call
    raw_response: object = field(default=None, repr=False)  # Provider SDK response


@dataclass(frozen=True, slots=True)
class StreamChunk:
    """A single chunk from a streaming response."""
    text: str
    is_final: bool = False
    usage: TokenUsage | None = None  # Only populated on final chunk


@dataclass(frozen=True, slots=True)
class PromptMessage:
    """A single message in a prompt sequence."""
    role: str     # "system", "user", "assistant"
    content: str


@runtime_checkable
class ModelProvider(Protocol):
    """
    Protocol that all provider adapters must satisfy.

    Implementations are stateless — they hold connection config but no
    conversation state. The consensus engine manages all state.
    """

    @property
    def provider_id(self) -> str:
        """Unique identifier for this provider (e.g. 'anthropic', 'openai')."""
        ...

    async def list_models(self) -> list[ModelInfo]:
        """
        Return metadata for all models available through this provider.
        Should be cached after first call (models don't change mid-session).
        """
        ...

    async def send(
        self,
        messages: list[PromptMessage],
        model_id: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> ModelResponse:
        """
        Send a prompt and wait for complete response.
        Raises ProviderError on failure.
        """
        ...

    async def stream(
        self,
        messages: list[PromptMessage],
        model_id: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Send a prompt and yield response chunks as they arrive.
        Final chunk has is_final=True and includes usage.
        Raises ProviderError on failure.
        """
        ...

    async def health_check(self) -> bool:
        """
        Verify the provider is reachable and credentials are valid.
        Returns True if healthy, False otherwise. Must not raise.
        """
        ...
```

### Provider Manager

The `ProviderManager` sits above individual adapters and provides:

```python
# src/duh/providers/manager.py

from __future__ import annotations

from dataclasses import dataclass, field

from duh.providers.base import ModelInfo, ModelProvider, ModelResponse, PromptMessage


@dataclass
class CostAccumulator:
    """Tracks cumulative cost across all model calls in a session."""
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cost_usd: float = 0.0
    calls: int = 0

    def record(self, response: ModelResponse) -> float:
        """Record usage from a response. Returns cost of this call in USD."""
        info = response.model_info
        input_cost = (response.usage.input_tokens / 1_000_000) * info.input_cost_per_mtok
        output_cost = (response.usage.output_tokens / 1_000_000) * info.output_cost_per_mtok
        call_cost = input_cost + output_cost

        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens
        self.total_cost_usd += call_cost
        self.calls += 1
        return call_cost


class ProviderManager:
    """
    Manages provider lifecycle, model discovery, routing, and cost tracking.

    Responsibilities:
    - Instantiate providers from config
    - Aggregate model listings across all providers
    - Route send/stream calls to the correct provider
    - Track cumulative cost
    - Handle provider health checks
    """

    def __init__(self) -> None:
        self._providers: dict[str, ModelProvider] = {}
        self._models: dict[str, ModelInfo] = {}  # Keyed by "provider_id:model_id"
        self.cost = CostAccumulator()

    def register(self, provider: ModelProvider) -> None:
        """Register a provider adapter."""
        self._providers[provider.provider_id] = provider

    async def discover_models(self) -> list[ModelInfo]:
        """Query all registered providers for available models."""
        all_models: list[ModelInfo] = []
        for provider in self._providers.values():
            models = await provider.list_models()
            for model in models:
                key = f"{model.provider_id}:{model.model_id}"
                self._models[key] = model
                all_models.append(model)
        return all_models

    def resolve_model(self, model_ref: str) -> tuple[ModelProvider, ModelInfo]:
        """
        Resolve a model reference like 'anthropic:claude-opus-4-6' or
        'ollama:llama3:70b' to the provider and model info.
        Raises KeyError if not found.
        """
        info = self._models[model_ref]
        provider = self._providers[info.provider_id]
        return provider, info

    async def send(
        self,
        model_ref: str,
        messages: list[PromptMessage],
        **kwargs,
    ) -> ModelResponse:
        """Send to a specific model, track cost."""
        provider, info = self.resolve_model(model_ref)
        response = await provider.send(messages, info.model_id, **kwargs)
        self.cost.record(response)
        return response
```

### Why This Design

- **`ModelInfo` is immutable**: Provider metadata does not change during a session. `frozen=True` + `slots=True` for memory efficiency and hashability.
- **`send` vs `stream`**: Two separate methods rather than a `stream=True` flag. Cleaner type signatures — `send` returns `ModelResponse`, `stream` returns `AsyncIterator[StreamChunk]`.
- **Cost tracking at the manager level**: Individual providers do not track cost. The manager accumulates cost from every response, giving a single source of truth for "how much has this session/thread cost?"
- **`model_ref` as `provider_id:model_id`**: Unambiguous. Multiple providers might offer models with overlapping names (e.g., a fine-tuned model served via OpenAI API and via vLLM).
- **No tool-use in the initial interface**: Tool use is a Phase 2+ concern. The consensus loop does not need tool calling — it needs prompt-in, text-out. Tool use can be added to the protocol later as an optional method without breaking existing adapters.

---

## 3. Consensus Protocol State Machine

### State Diagram

```
                          ┌─────────────────────────────────┐
                          │                                 │
                          v                                 │
    INPUT ──> DECOMPOSE ──> PROPOSE ──> CHALLENGE ──> REVISE ──> COMMIT ──> NEXT
                              ^                                               │
                              │                                               │
                              └───────────────── (more tasks) ────────────────┘
                                                                              │
                                                                        (no more tasks)
                                                                              │
                                                                              v
                                                                           COMPLETE
```

### Detailed Transitions

```
State        | Trigger             | Next State  | Condition
-------------|---------------------|-------------|----------------------------------
IDLE         | user submits query  | DECOMPOSE   | Always
DECOMPOSE    | tasks generated     | PROPOSE     | At least one task produced
DECOMPOSE    | trivial query       | PROPOSE     | Single-task shortcut (no decomp needed)
PROPOSE      | proposal received   | CHALLENGE   | Always
CHALLENGE    | challenges received | REVISE      | At least one substantive challenge
CHALLENGE    | unanimous agreement | COMMIT      | All challengers agree (rare, skip REVISE)
REVISE       | revision received   | COMMIT      | round >= max_rounds
REVISE       | revision received   | CHALLENGE   | round < max_rounds (another round)
COMMIT       | committed to memory | NEXT        | Always
NEXT         | more tasks remain   | PROPOSE     | task_queue not empty
NEXT         | all tasks done      | COMPLETE    | task_queue empty
COMPLETE     | -                   | IDLE        | Results returned to user
```

### State Data Structures

```python
# src/duh/consensus/types.py

from __future__ import annotations

import enum
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


class ConsensusState(enum.Enum):
    IDLE = "idle"
    DECOMPOSE = "decompose"
    PROPOSE = "propose"
    CHALLENGE = "challenge"
    REVISE = "revise"
    COMMIT = "commit"
    NEXT = "next"
    COMPLETE = "complete"


@dataclass(slots=True)
class Task:
    """A single task produced by decomposition."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    description: str = ""
    rationale: str = ""          # Why this task matters
    suggested_model: str = ""    # Optional: model hint from decomposer
    order: int = 0               # Execution order
    depends_on: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Proposal:
    """A model's proposed approach for a task."""
    model_ref: str               # "anthropic:claude-opus-4-6"
    content: str
    confidence: float = 0.0      # Self-assessed 0.0-1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    token_usage_input: int = 0
    token_usage_output: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass(slots=True)
class Challenge:
    """A model's critique of a proposal."""
    model_ref: str
    content: str
    severity: str = "medium"     # "low", "medium", "high", "critical"
    challenge_type: str = ""     # "risk", "alternative", "flaw", "devils_advocate"
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    token_usage_input: int = 0
    token_usage_output: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass(slots=True)
class Revision:
    """Revised proposal after incorporating challenges."""
    model_ref: str               # May be original proposer or a synthesizer
    content: str
    addressed_challenges: list[str] = field(default_factory=list)  # Which challenges were addressed
    unresolved_dissent: list[str] = field(default_factory=list)    # What remains contested
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    token_usage_input: int = 0
    token_usage_output: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


@dataclass(slots=True)
class Commitment:
    """Final committed result for a task."""
    task: Task
    final_content: str
    proposal: Proposal
    challenges: list[Challenge]
    revisions: list[Revision]
    dissent: list[str]           # Unresolved disagreements — preserved, not discarded
    round_count: int
    total_cost_usd: float
    total_latency_ms: float


@dataclass(slots=True)
class ConsensusContext:
    """
    Full state of a consensus session. Passed to the engine,
    mutated through state transitions.
    """
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    user_query: str = ""
    state: ConsensusState = ConsensusState.IDLE

    # DECOMPOSE outputs
    tasks: list[Task] = field(default_factory=list)
    current_task_index: int = 0

    # Per-task state (reset on NEXT)
    current_proposal: Proposal | None = None
    current_challenges: list[Challenge] = field(default_factory=list)
    current_revisions: list[Revision] = field(default_factory=list)
    current_round: int = 0
    max_rounds: int = 3          # Configurable

    # Accumulated results
    commitments: list[Commitment] = field(default_factory=list)

    # Cost tracking
    total_cost_usd: float = 0.0
    total_tokens_in: int = 0
    total_tokens_out: int = 0

    @property
    def current_task(self) -> Task | None:
        if self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    @property
    def has_more_tasks(self) -> bool:
        return self.current_task_index < len(self.tasks) - 1
```

### State Machine Engine

```python
# src/duh/consensus/engine.py  (simplified — key structure)

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from duh.consensus.types import (
    Challenge,
    Commitment,
    ConsensusContext,
    ConsensusState,
    Proposal,
    Revision,
)
from duh.core.events import EventBus

if TYPE_CHECKING:
    from duh.providers.manager import ProviderManager
    from duh.memory.repository import MemoryRepository


class ConsensusEngine:
    """
    Drives the consensus state machine.

    Each state has a handler that:
    1. Reads the current ConsensusContext
    2. Makes model calls (via ProviderManager)
    3. Mutates the context
    4. Returns the next state

    The engine loops until COMPLETE.
    """

    def __init__(
        self,
        provider_manager: ProviderManager,
        memory: MemoryRepository,
        event_bus: EventBus,
    ) -> None:
        self._providers = provider_manager
        self._memory = memory
        self._events = event_bus

        # State handler dispatch table
        self._handlers: dict[ConsensusState, ...] = {
            ConsensusState.DECOMPOSE: self._handle_decompose,
            ConsensusState.PROPOSE: self._handle_propose,
            ConsensusState.CHALLENGE: self._handle_challenge,
            ConsensusState.REVISE: self._handle_revise,
            ConsensusState.COMMIT: self._handle_commit,
            ConsensusState.NEXT: self._handle_next,
        }

    async def run(self, query: str, **config) -> ConsensusContext:
        """
        Execute the full consensus loop for a user query.
        Returns the completed ConsensusContext with all commitments.
        """
        ctx = ConsensusContext(user_query=query, state=ConsensusState.DECOMPOSE)
        ctx.max_rounds = config.get("max_rounds", 3)

        while ctx.state != ConsensusState.COMPLETE:
            handler = self._handlers[ctx.state]
            next_state = await handler(ctx)
            prev_state = ctx.state
            ctx.state = next_state
            await self._events.emit("state_transition", {
                "from": prev_state.value,
                "to": next_state.value,
                "task_index": ctx.current_task_index,
                "round": ctx.current_round,
            })

        return ctx

    async def _handle_decompose(self, ctx: ConsensusContext) -> ConsensusState:
        """
        Break the user query into tasks.
        Uses a strong reasoner model. For simple queries, may produce a single task.
        """
        # Select decomposer model (configurable, default: strongest available)
        # Build decomposition prompt
        # Parse structured task list from response
        # Populate ctx.tasks
        # Emit event for UI
        ...
        return ConsensusState.PROPOSE

    async def _handle_propose(self, ctx: ConsensusContext) -> ConsensusState:
        """
        One model proposes an approach for the current task.
        Proposer selection: round-robin, random, or configured per task.
        """
        task = ctx.current_task
        # Select proposer model
        # Build proposal prompt: task + thread summary + prior commitments
        # Send to model (streaming for UI)
        # Store Proposal in ctx.current_proposal
        ...
        return ConsensusState.CHALLENGE

    async def _handle_challenge(self, ctx: ConsensusContext) -> ConsensusState:
        """
        Multiple models critique the proposal IN PARALLEL.
        Each challenger gets a different framing:
        - "What is wrong with this proposal?"
        - "What would you do differently?"
        - "What is the biggest risk?"
        - Devil's advocate (assigned to one challenger)
        """
        task = ctx.current_task
        proposal = ctx.current_proposal

        # Build challenge prompts — one per challenger, each with different framing
        challenge_prompts = self._build_challenge_prompts(proposal, task)

        # Fan out to all challengers in parallel
        results = await asyncio.gather(
            *[
                self._providers.send(model_ref, messages)
                for model_ref, messages in challenge_prompts
            ],
            return_exceptions=True,
        )

        # Parse challenges, handle any provider failures gracefully
        # Store in ctx.current_challenges
        ...

        # If all challengers substantively agree (rare), skip REVISE
        if self._is_unanimous_agreement(ctx.current_challenges):
            return ConsensusState.COMMIT

        return ConsensusState.REVISE

    async def _handle_revise(self, ctx: ConsensusContext) -> ConsensusState:
        """
        Synthesize the proposal with challenge feedback.
        May use the original proposer or a dedicated synthesizer model.
        """
        # Build revision prompt: original proposal + all challenges
        # Send to synthesizer model
        # Store Revision in ctx.current_revisions
        ctx.current_round += 1
        ...

        if ctx.current_round >= ctx.max_rounds:
            return ConsensusState.COMMIT
        return ConsensusState.CHALLENGE  # Another round

    async def _handle_commit(self, ctx: ConsensusContext) -> ConsensusState:
        """
        Commit the final result for this task to memory.
        Preserve dissent — unresolved disagreements are recorded, not discarded.
        """
        commitment = Commitment(
            task=ctx.current_task,
            final_content=ctx.current_revisions[-1].content if ctx.current_revisions else ctx.current_proposal.content,
            proposal=ctx.current_proposal,
            challenges=ctx.current_challenges,
            revisions=ctx.current_revisions,
            dissent=[c.content for c in ctx.current_challenges if c.severity in ("high", "critical")],
            round_count=ctx.current_round,
            total_cost_usd=0.0,  # Calculated from components
        )
        ctx.commitments.append(commitment)

        # Persist to memory layer
        await self._memory.save_commitment(ctx.id, commitment)

        # Generate turn summary via fast/cheap model
        await self._generate_turn_summary(ctx, commitment)

        return ConsensusState.NEXT

    async def _handle_next(self, ctx: ConsensusContext) -> ConsensusState:
        """
        Move to next task or complete.
        Reset per-task state.
        """
        if ctx.has_more_tasks:
            ctx.current_task_index += 1
            ctx.current_proposal = None
            ctx.current_challenges = []
            ctx.current_revisions = []
            ctx.current_round = 0
            return ConsensusState.PROPOSE
        return ConsensusState.COMPLETE
```

### Challenge Prompt Framing

The challenge phase is the critical differentiator. Naive "do you agree?" produces sycophantic agreement. Each challenger gets a specific adversarial framing:

```python
CHALLENGE_FRAMINGS = [
    {
        "type": "flaw",
        "system": "You are a critical reviewer. Your job is to find flaws, errors, and weaknesses.",
        "prompt": "Here is a proposal:\n\n{proposal}\n\nWhat is wrong with this proposal? Be specific. Identify concrete flaws, incorrect assumptions, or missing considerations. Do not be polite — be thorough.",
    },
    {
        "type": "alternative",
        "system": "You are an independent thinker. You always consider different approaches.",
        "prompt": "Here is a proposal:\n\n{proposal}\n\nWhat would you do differently? Propose a concrete alternative approach. Explain why your approach would be better.",
    },
    {
        "type": "risk",
        "system": "You are a risk analyst. You identify what could go wrong.",
        "prompt": "Here is a proposal:\n\n{proposal}\n\nWhat is the biggest risk with this proposal? What failure modes exist? What has been overlooked?",
    },
    {
        "type": "devils_advocate",
        "system": "You are a devil's advocate. You must argue AGAINST this proposal regardless of your actual opinion. Find the strongest possible counterarguments.",
        "prompt": "Here is a proposal:\n\n{proposal}\n\nArgue against this proposal. Take the strongest possible opposing position. What would someone who completely disagrees say?",
    },
]
```

---

## 4. SQLAlchemy Memory Schema

### Design Principles

- Async-native: Using `sqlalchemy.ext.asyncio` throughout.
- SQLite default, PostgreSQL ready. No Postgres-specific types in the core schema.
- UUIDs stored as strings (SQLite-compatible). PostgreSQL migration can add native UUID type later via Alembic.
- Timestamps always UTC, stored as timezone-aware.
- Soft deletes via `deleted_at` column where appropriate.
- JSON columns for flexible structured data (supported by both SQLite and PostgreSQL).

### Model Definitions

```python
# src/duh/memory/models.py

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


# =============================================================================
# Layer 1: Operational (Thread Tracking)
# =============================================================================


class Thread(Base):
    """
    Top-level conversation/project. A user starts a thread with a query.
    The consensus loop runs within a thread.
    """
    __tablename__ = "threads"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    title: Mapped[str] = mapped_column(String(500), default="")
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active"
    )  # active, completed, archived
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Cost tracking
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    total_tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens_out: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    turns: Mapped[list[Turn]] = relationship(back_populates="thread", cascade="all, delete-orphan")
    thread_summary: Mapped[Optional[ThreadSummary]] = relationship(
        back_populates="thread", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_threads_status", "status"),
        Index("ix_threads_created", "created_at"),
    )


class Turn(Base):
    """
    One round of the consensus loop within a thread.
    A turn corresponds to one task from the decomposition.
    Contains a proposal, challenges, revisions, and a commitment.
    """
    __tablename__ = "turns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    thread_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("threads.id", ondelete="CASCADE"), nullable=False
    )
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    task_order: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(20), default="propose")  # Consensus state
    round_count: Mapped[int] = mapped_column(Integer, default=0)
    final_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dissent: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # Preserved disagreements
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    thread: Mapped[Thread] = relationship(back_populates="turns")
    contributions: Mapped[list[Contribution]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )
    turn_summary: Mapped[Optional[TurnSummary]] = relationship(
        back_populates="turn", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_turns_thread", "thread_id"),
        Index("ix_turns_thread_order", "thread_id", "task_order"),
    )


class Contribution(Base):
    """
    An individual model response within a turn.
    Could be a proposal, a challenge, or a revision.
    """
    __tablename__ = "contributions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    turn_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("turns.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "proposer", "challenger", "reviser", "decomposer"
    model_ref: Mapped[str] = mapped_column(
        String(200), nullable=False
    )  # "anthropic:claude-opus-4-6"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    challenge_type: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )  # "flaw", "alternative", "risk", "devils_advocate"
    round_number: Mapped[int] = mapped_column(Integer, default=0)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    turn: Mapped[Turn] = relationship(back_populates="contributions")

    __table_args__ = (
        Index("ix_contributions_turn", "turn_id"),
        Index("ix_contributions_role", "turn_id", "role"),
        Index("ix_contributions_model", "model_ref"),
    )


class TurnSummary(Base):
    """
    AI-generated summary of a single turn. Created by a fast/cheap model
    after each turn completes. Used for context window management.
    """
    __tablename__ = "turn_summaries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    turn_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("turns.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    model_ref: Mapped[str] = mapped_column(String(200), nullable=False)  # Which model generated it
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    turn: Mapped[Turn] = relationship(back_populates="turn_summary")


class ThreadSummary(Base):
    """
    Rolling summary of the entire thread. Regenerated (not appended) after
    each turn to stay coherent. This is what gets passed to models as
    context instead of full history.
    """
    __tablename__ = "thread_summaries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    thread_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("threads.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    model_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)  # Incremented on each regeneration
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    # Relationships
    thread: Mapped[Thread] = relationship(back_populates="thread_summary")


# =============================================================================
# Layer 2: Institutional (Accumulated Knowledge)
# =============================================================================


class Decision(Base):
    """
    A structured record of a consensus decision. Promoted from a thread
    commitment when the user or system determines it has lasting value.
    This is the core knowledge unit.
    """
    __tablename__ = "decisions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    thread_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("threads.id"), nullable=False
    )
    turn_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("turns.id"), nullable=False
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)  # The original question/task
    resolution: Mapped[str] = mapped_column(Text, nullable=False)  # The committed answer
    proposals: Mapped[dict] = mapped_column(JSON, default=dict)   # Snapshot of proposals
    challenges: Mapped[dict] = mapped_column(JSON, default=dict)  # Snapshot of challenges
    dissent: Mapped[dict] = mapped_column(JSON, default=dict)     # Preserved disagreements
    models_involved: Mapped[list] = mapped_column(JSON, default=list)  # Which models participated
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # Consensus confidence 0.0-1.0
    domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Auto-classified
    tags: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    outcomes: Mapped[list[Outcome]] = relationship(back_populates="decision", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_decisions_thread", "thread_id"),
        Index("ix_decisions_domain", "domain"),
        Index("ix_decisions_created", "created_at"),
    )


class Pattern(Base):
    """
    Inferred user or domain preferences over time.
    Example: "User prefers PostgreSQL over MySQL for new projects."
    Example: "In agriculture domain, consensus quality improves with 4+ models."
    """
    __tablename__ = "patterns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    pattern_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # "user_preference", "domain_pattern", "model_performance"
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)  # References to decisions/threads
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    observation_count: Mapped[int] = mapped_column(Integer, default=1)
    domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_patterns_type", "pattern_type"),
        Index("ix_patterns_domain", "domain"),
    )


class Outcome(Base):
    """
    Feedback on whether a decision was correct/useful. Closes the learning loop.
    User or system can record outcomes: "That recommendation worked" or
    "That approach failed because X."
    """
    __tablename__ = "outcomes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    decision_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("decisions.id", ondelete="CASCADE"), nullable=False
    )
    result: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "success", "partial", "failure", "unknown"
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    recorded_by: Mapped[str] = mapped_column(
        String(50), default="user"
    )  # "user", "system", "network"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # Relationships
    decision: Mapped[Decision] = relationship(back_populates="outcomes")

    __table_args__ = (
        Index("ix_outcomes_decision", "decision_id"),
        Index("ix_outcomes_result", "result"),
    )


# =============================================================================
# Layer 3: Retrieval (Future — schema designed now, populated later)
# =============================================================================


class Embedding(Base):
    """
    Vector embedding for semantic search over memory.
    Phase 2+ feature, but schema designed now for forward compatibility.

    The embedding vector is stored as JSON (list of floats) for SQLite
    compatibility. PostgreSQL deployments should migrate to pgvector.
    """
    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_new_id)
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # "thread", "turn", "decision", "pattern"
    source_id: Mapped[str] = mapped_column(String(32), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of source text
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "text-embedding-3-small"
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)  # 256, 1536, 3072, etc.
    vector: Mapped[list] = mapped_column(JSON, nullable=False)  # List[float] — JSON for SQLite compat
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (
        Index("ix_embeddings_source", "source_type", "source_id"),
        Index("ix_embeddings_hash", "content_hash"),
    )
```

### Session Factory

```python
# src/duh/memory/session.py

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from duh.memory.models import Base


async def init_database(database_url: str) -> async_sessionmaker[AsyncSession]:
    """
    Initialize the database engine and create tables.
    Returns an async session factory.

    database_url examples:
      - "sqlite+aiosqlite:///duh.db"         (local file)
      - "sqlite+aiosqlite://"                 (in-memory, for tests)
      - "postgresql+asyncpg://user:pass@host/db"  (PostgreSQL)
    """
    engine = create_async_engine(
        database_url,
        echo=False,
        # SQLite-specific: enable WAL mode for concurrent reads
        # PostgreSQL ignores this
        connect_args={"check_same_thread": False} if "sqlite" in database_url else {},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return async_sessionmaker(engine, expire_on_commit=False)
```

### Migration Strategy

Alembic from day one. Even for SQLite. Schema changes happen through migration scripts, not `create_all` in production.

```
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

The `init_database` function above uses `create_all` as a convenience for development and testing. Production deployments run Alembic migrations.

---

## 5. CLI Architecture

### Framework: Rich for Phase 1

Using `rich` (not `textual`) for Phase 1. Rich provides live display, progress bars, panels, and streaming output — everything needed for the consensus loop visualization. Textual is a full TUI framework (mouse support, widgets, focus management) which is overkill until we need interactive navigation. Rich is lighter and composes better with simple CLI argument parsing.

### Key UI Components

```python
# src/duh/cli/panels.py  (conceptual — key components)

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.text import Text


class ConsensusDisplay:
    """
    Manages the Rich Live display during a consensus loop.

    Layout:
    ┌──────────────────────────────────────────┐
    │ TASK 1/3: Design auth system             │
    ├──────────────────────────────────────────┤
    │ PROPOSE (Claude Opus 4.6)                │
    │ ████████████░░░░ streaming...             │
    │                                          │
    │ [proposal text streams here]             │
    ├──────────────────────────────────────────┤
    │ CHALLENGE (parallel)                     │
    │ GPT-5.2        ████████████████ done     │
    │ Gemini 3 Pro   ████████░░░░░░░ 52%      │
    │ Llama 3 70B    ████████████████ done     │
    ├──────────────────────────────────────────┤
    │ Round 1/3 · 4 models · $0.04 · 12.3s    │
    └──────────────────────────────────────────┘
    """

    def __init__(self, console: Console) -> None:
        self.console = console
        self._live: Live | None = None

    def start(self) -> None:
        self._live = Live(console=self.console, refresh_per_second=10)
        self._live.start()

    def stop(self) -> None:
        if self._live:
            self._live.stop()

    def update_state(
        self,
        state: str,
        task_num: int,
        task_total: int,
        task_desc: str,
        models: list[dict],  # [{"name": "...", "progress": 0.5, "status": "streaming"}]
        round_num: int,
        max_rounds: int,
        cost_usd: float,
        elapsed_s: float,
        streaming_text: str = "",
    ) -> None:
        """Rebuild and update the live display."""
        # Task header
        header = Text(f"TASK {task_num}/{task_total}: {task_desc}", style="bold cyan")

        # State panel with model progress
        state_rows = []
        for m in models:
            bar = self._progress_bar(m["progress"])
            status = m.get("status", "")
            state_rows.append(f"  {m['name']:<20} {bar} {status}")
        state_content = f"  {state.upper()}\n" + "\n".join(state_rows)

        # Streaming text (if in PROPOSE or REVISE)
        content_panel = ""
        if streaming_text:
            content_panel = streaming_text[-500:]  # Show last 500 chars

        # Footer with stats
        footer = (
            f"  Round {round_num}/{max_rounds} · "
            f"{len(models)} models · "
            f"${cost_usd:.4f} · "
            f"{elapsed_s:.1f}s"
        )

        panel = Panel(
            Group(
                Text(state_content),
                Text(content_panel, style="dim") if content_panel else Text(""),
                Text(footer, style="bold"),
            ),
            title=str(header),
            border_style="blue",
        )

        if self._live:
            self._live.update(panel)
```

### CLI Entry Point

```python
# src/duh/cli/app.py

import asyncio
import sys

import click
from rich.console import Console

from duh.config.loader import load_config
from duh.consensus.engine import ConsensusEngine
from duh.memory.session import init_database
from duh.providers.registry import create_providers


@click.group()
@click.version_option()
def cli():
    """duh — multi-model consensus and knowledge infrastructure."""
    pass


@cli.command()
@click.argument("query", nargs=-1, required=True)
@click.option("--models", "-m", multiple=True, help="Model refs to use (e.g. anthropic:claude-opus-4-6)")
@click.option("--rounds", "-r", default=3, help="Max consensus rounds")
@click.option("--config", "-c", type=click.Path(), help="Config file path")
def ask(query: tuple[str, ...], models: tuple[str, ...], rounds: int, config: str | None):
    """Submit a query to the consensus engine."""
    asyncio.run(_run_ask(" ".join(query), models=models, rounds=rounds, config_path=config))


@cli.command()
def models():
    """List all available models across configured providers."""
    asyncio.run(_run_list_models())


@cli.command()
def threads():
    """List recent threads."""
    asyncio.run(_run_list_threads())


@cli.command()
@click.argument("thread_id")
def show(thread_id: str):
    """Show a thread's consensus history."""
    asyncio.run(_run_show_thread(thread_id))


@cli.command()
def cost():
    """Show cumulative cost tracking."""
    asyncio.run(_run_cost_report())


async def _run_ask(query: str, **kwargs):
    console = Console()
    cfg = load_config(kwargs.get("config_path"))
    session_factory = await init_database(cfg.database_url)
    providers = create_providers(cfg)
    # ... wire up engine, display, run consensus
    ...


def main():
    cli()
```

### CLI Command Summary

| Command | Description | Phase |
|---------|-------------|-------|
| `duh ask "query"` | Run consensus on a query | 1 |
| `duh models` | List available models | 1 |
| `duh threads` | List recent threads | 1 |
| `duh show <thread_id>` | Display thread history with debate | 1 |
| `duh cost` | Cumulative cost report | 1 |
| `duh config` | Show/edit configuration | 1 |
| `duh feedback <thread_id>` | Record outcome feedback | 2 |
| `duh search "query"` | Semantic search over memory | 2 |

---

## 6. Testing Strategy

### Framework: pytest + pytest-asyncio

```
tests/
├── conftest.py                 # Shared fixtures
├── unit/
│   ├── test_consensus_states.py    # State machine transitions
│   ├── test_providers.py           # Provider adapter behavior
│   ├── test_memory_models.py       # ORM model validation
│   ├── test_cost.py                # Cost calculation accuracy
│   ├── test_config.py              # Config loading, validation, defaults
│   └── test_context_builder.py     # Context window management
├── integration/
│   ├── test_consensus_loop.py      # Full consensus loop with mock providers
│   ├── test_memory_persistence.py  # DB round-trip, queries, indexes
│   └── test_provider_registry.py   # Provider discovery and health checks
└── fixtures/
    ├── providers.py            # Mock provider implementations
    ├── responses.py            # Deterministic canned responses
    └── database.py             # In-memory SQLite setup
```

### Mock Provider for Testing

```python
# tests/fixtures/providers.py

from __future__ import annotations
from typing import AsyncIterator

from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ModelResponse,
    PromptMessage,
    StreamChunk,
    TokenUsage,
)


class MockProvider:
    """
    Deterministic provider for tests. Returns canned responses
    based on a response map keyed by model_id.
    """

    def __init__(
        self,
        provider_id: str = "mock",
        responses: dict[str, str] | None = None,
    ) -> None:
        self._provider_id = provider_id
        self._responses = responses or {}
        self._call_log: list[dict] = []

    @property
    def provider_id(self) -> str:
        return self._provider_id

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                provider_id=self._provider_id,
                model_id=model_id,
                display_name=f"Mock {model_id}",
                capabilities=ModelCapability.TEXT | ModelCapability.STREAMING,
                context_window=128_000,
                max_output_tokens=4096,
                input_cost_per_mtok=0.0,
                output_cost_per_mtok=0.0,
                is_local=True,
            )
            for model_id in self._responses
        ]

    async def send(
        self,
        messages: list[PromptMessage],
        model_id: str,
        **kwargs,
    ) -> ModelResponse:
        self._call_log.append({"model_id": model_id, "messages": messages})
        content = self._responses.get(model_id, "Mock response")
        return ModelResponse(
            content=content,
            model_info=(await self.list_models())[0],
            usage=TokenUsage(input_tokens=100, output_tokens=50),
            finish_reason="stop",
            latency_ms=10.0,
        )

    async def stream(
        self,
        messages: list[PromptMessage],
        model_id: str,
        **kwargs,
    ) -> AsyncIterator[StreamChunk]:
        content = self._responses.get(model_id, "Mock response")
        words = content.split()
        for i, word in enumerate(words):
            is_final = i == len(words) - 1
            yield StreamChunk(
                text=word + " ",
                is_final=is_final,
                usage=TokenUsage(input_tokens=100, output_tokens=len(words)) if is_final else None,
            )

    async def health_check(self) -> bool:
        return True
```

### Key Test Patterns

```python
# tests/conftest.py

import pytest
import pytest_asyncio

from duh.memory.models import Base
from duh.memory.session import init_database


@pytest_asyncio.fixture
async def db_session():
    """In-memory SQLite for each test — zero state bleed."""
    session_factory = await init_database("sqlite+aiosqlite://")
    async with session_factory() as session:
        yield session


@pytest.fixture
def mock_provider():
    """Provider with canned responses for deterministic consensus tests."""
    from tests.fixtures.providers import MockProvider
    return MockProvider(
        provider_id="mock",
        responses={
            "proposer": "I propose we use PostgreSQL because...",
            "challenger-1": "The flaw in this proposal is...",
            "challenger-2": "An alternative approach would be...",
            "reviser": "Incorporating the feedback, the revised approach...",
        },
    )
```

### Test Categories

| Category | What It Tests | Provider | Database |
|----------|---------------|----------|----------|
| Unit: states | State transitions, guard conditions | None | None |
| Unit: providers | Adapter request/response mapping | Mocked HTTP | None |
| Unit: cost | Token counting, cost calculation | None | None |
| Unit: config | Config loading, validation, defaults | None | None |
| Integration: consensus | Full loop with mock providers | MockProvider | In-memory SQLite |
| Integration: memory | DB round-trip, queries, relationships | None | In-memory SQLite |
| Integration: registry | Provider discovery, health checks | MockProvider | None |

### Running Tests

```bash
# All tests
pytest

# Unit only (fast, no I/O)
pytest tests/unit/

# Integration (slower, uses SQLite in-memory)
pytest tests/integration/

# With coverage
pytest --cov=duh --cov-report=term-missing
```

### No Live API Tests in CI

Tests against real provider APIs (Anthropic, OpenAI, etc.) are not part of CI. They are:
- Expensive (real token costs)
- Non-deterministic (model outputs vary)
- Slow (network latency)
- Require credentials

Live API tests exist as a separate `tests/live/` directory, run manually during development, excluded from CI via `pytest.ini` markers.

---

## 7. Configuration Format

### Decision: TOML

**Rationale**:
- TOML is the Python ecosystem standard (`pyproject.toml`, PEP 518/621). Users writing Python projects already know TOML.
- Human-readable and writable. Comments supported (YAML supports this too, JSON does not).
- Clear distinction between strings, integers, floats, booleans (JSON conflates via `1` vs `"1"`, YAML has the famous Norway problem where `NO` becomes `false`).
- Standard library support in Python 3.11+ (`tomllib`). For writing, use `tomli-w`.
- No indentation-sensitivity (unlike YAML).

**Rejected alternatives**:
- YAML: Indentation-sensitive, the Norway problem, implicit typing surprises. More expressive than needed.
- JSON: No comments. Painful to edit by hand. No trailing commas.

### Configuration File Location

```
~/.config/duh/config.toml       # User config (XDG standard)
./duh.toml                       # Project-local override
$DUH_CONFIG                      # Environment variable override
```

Merge order: defaults < user config < project config < env vars < CLI flags.

### Example Configuration

```toml
# duh configuration
# See: https://github.com/duh-project/duh/docs/configuration.md

[general]
# Maximum consensus rounds before committing
max_rounds = 3
# Default model for task decomposition (strongest available)
decomposer_model = "anthropic:claude-opus-4-6"
# Model for generating summaries (fast/cheap)
summary_model = "anthropic:claude-haiku-4-5"
# Show streaming output in CLI
stream_output = true


[database]
# SQLite (default) — just works, zero config
url = "sqlite+aiosqlite:///~/.local/share/duh/duh.db"
# PostgreSQL example:
# url = "postgresql+asyncpg://duh:password@localhost:5432/duh"


[cost]
# Warn when session cost exceeds this (USD). 0 = no warning.
warn_threshold = 1.00
# Hard stop when session cost exceeds this. 0 = no limit.
hard_limit = 10.00
# Show running cost in CLI
show_running_cost = true


# ─── Provider Configuration ───────────────────────────────────

[providers.anthropic]
enabled = true
api_key_env = "ANTHROPIC_API_KEY"    # Read key from this env var
# api_key = "sk-..."                 # Or hardcode (not recommended)
default_model = "claude-sonnet-4-5-20250929"
models = [
    "claude-opus-4-6",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
]


[providers.openai]
enabled = true
api_key_env = "OPENAI_API_KEY"
default_model = "gpt-4o"
# base_url override for Azure or compatible APIs
# base_url = "https://my-azure.openai.azure.com/v1"


[providers.google]
enabled = false
api_key_env = "GOOGLE_API_KEY"
default_model = "gemini-2.0-flash"


[providers.ollama]
enabled = true
base_url = "http://localhost:11434"
# No API key needed for local
# Models discovered automatically via Ollama API


# Custom OpenAI-compatible provider (LM Studio, vLLM, etc.)
[providers.custom.lmstudio]
enabled = false
base_url = "http://localhost:1234/v1"
display_name = "LM Studio"
# Models discovered via /v1/models endpoint


# ─── Consensus Configuration ──────────────────────────────────

[consensus]
# Models participating in consensus (references to provider:model)
# If empty, uses all available models
panel = [
    "anthropic:claude-opus-4-6",
    "openai:gpt-4o",
    "ollama:llama3:70b",
]

# Proposer selection strategy: "round_robin", "random", "strongest"
proposer_strategy = "round_robin"

# Challenge framings — which challenge types to use
challenge_types = ["flaw", "alternative", "risk", "devils_advocate"]

# Minimum challengers per round (if fewer models available, all challenge)
min_challengers = 2


# ─── Logging ──────────────────────────────────────────────────

[logging]
level = "INFO"             # DEBUG, INFO, WARNING, ERROR
file = ""                  # Log to file (empty = stderr only)
structured = false          # JSON structured logging
```

### Pydantic Validation

```python
# src/duh/config/schema.py

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    enabled: bool = True
    api_key: str | None = None
    api_key_env: str | None = None
    base_url: str | None = None
    default_model: str | None = None
    models: list[str] = Field(default_factory=list)
    display_name: str | None = None


class ConsensusConfig(BaseModel):
    panel: list[str] = Field(default_factory=list)
    proposer_strategy: str = "round_robin"
    challenge_types: list[str] = Field(
        default_factory=lambda: ["flaw", "alternative", "risk", "devils_advocate"]
    )
    min_challengers: int = 2


class CostConfig(BaseModel):
    warn_threshold: float = 1.00
    hard_limit: float = 10.00
    show_running_cost: bool = True


class DatabaseConfig(BaseModel):
    url: str = "sqlite+aiosqlite:///~/.local/share/duh/duh.db"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = ""
    structured: bool = False


class GeneralConfig(BaseModel):
    max_rounds: int = 3
    decomposer_model: str = ""
    summary_model: str = ""
    stream_output: bool = True


class DuhConfig(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    cost: CostConfig = Field(default_factory=CostConfig)
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    consensus: ConsensusConfig = Field(default_factory=ConsensusConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
```

---

## 8. Error Handling Patterns

### Exception Hierarchy

```python
# src/duh/core/errors.py

class DuhError(Exception):
    """Base exception for all duh errors."""
    pass


# ─── Provider Errors ──────────────────────────────────────────

class ProviderError(DuhError):
    """Base for provider-related errors."""
    def __init__(self, provider_id: str, message: str):
        self.provider_id = provider_id
        super().__init__(f"[{provider_id}] {message}")


class ProviderAuthError(ProviderError):
    """Invalid or missing API key."""
    pass


class ProviderRateLimitError(ProviderError):
    """Rate limit exceeded. Includes retry_after if available."""
    def __init__(self, provider_id: str, retry_after: float | None = None):
        self.retry_after = retry_after
        msg = f"Rate limited"
        if retry_after:
            msg += f" (retry after {retry_after}s)"
        super().__init__(provider_id, msg)


class ProviderTimeoutError(ProviderError):
    """Model call timed out."""
    pass


class ProviderOverloadedError(ProviderError):
    """Provider is overloaded (529, 503)."""
    pass


class ModelNotFoundError(ProviderError):
    """Requested model not available from this provider."""
    pass


# ─── Consensus Errors ─────────────────────────────────────────

class ConsensusError(DuhError):
    """Base for consensus protocol errors."""
    pass


class InsufficientModelsError(ConsensusError):
    """Not enough models available for meaningful consensus."""
    pass


class CostLimitExceededError(ConsensusError):
    """Hard cost limit reached."""
    def __init__(self, limit: float, current: float):
        self.limit = limit
        self.current = current
        super().__init__(f"Cost limit ${limit:.2f} exceeded (current: ${current:.2f})")


# ─── Configuration Errors ─────────────────────────────────────

class ConfigError(DuhError):
    """Invalid configuration."""
    pass


# ─── Memory Errors ────────────────────────────────────────────

class MemoryError(DuhError):
    """Database or memory layer error."""
    pass
```

### Provider Failure Strategies

The consensus loop must be resilient to individual provider failures. If one provider fails, the loop continues with remaining providers.

```python
# Pattern: Graceful degradation in the CHALLENGE phase

async def _handle_challenge(self, ctx: ConsensusContext) -> ConsensusState:
    challenge_tasks = [
        self._call_challenger(model_ref, proposal, framing)
        for model_ref, framing in challenge_assignments
    ]

    # gather with return_exceptions=True — no single failure kills the phase
    results = await asyncio.gather(*challenge_tasks, return_exceptions=True)

    successful_challenges = []
    failed_providers = []

    for result, (model_ref, _) in zip(results, challenge_assignments):
        if isinstance(result, Exception):
            failed_providers.append((model_ref, result))
            await self._events.emit("provider_error", {
                "model_ref": model_ref,
                "error": str(result),
                "phase": "challenge",
            })
        else:
            successful_challenges.append(result)

    # Need at least one successful challenge to proceed
    if not successful_challenges:
        raise ConsensusError(
            f"All challengers failed: {failed_providers}. Cannot proceed."
        )

    ctx.current_challenges = successful_challenges
    ...
```

### Retry Strategy

```python
# Exponential backoff with jitter for rate limits and transient errors

import asyncio
import random

from duh.core.errors import ProviderRateLimitError, ProviderOverloadedError, ProviderTimeoutError


async def with_retry(
    coro_factory,           # Callable that returns a coroutine
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    retryable: tuple = (ProviderRateLimitError, ProviderOverloadedError, ProviderTimeoutError),
):
    """
    Retry with exponential backoff + jitter.
    Only retries specific transient errors.
    Auth errors, model-not-found, etc. fail immediately.
    """
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except retryable as e:
            last_error = e
            if attempt == max_retries:
                raise

            # Use retry_after from rate limit if available
            if isinstance(e, ProviderRateLimitError) and e.retry_after:
                delay = e.retry_after
            else:
                delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)

            await asyncio.sleep(delay)

    raise last_error
```

### Partial Consensus

When some models fail but others succeed, the system produces a partial consensus rather than failing entirely:

- If the proposer fails: Select a different proposer model, retry.
- If some challengers fail: Continue with available challengers. Annotate the commitment with "N of M challengers responded."
- If the reviser fails: Commit the original proposal with challenges attached as unresolved.
- If the summary model fails: Skip summary for this turn, use raw content in context.
- If the database fails: Log to stderr, attempt in-memory fallback, warn user that persistence is degraded.

### Cost Guard

```python
# Check cost before every model call
async def _guard_cost(self, ctx: ConsensusContext) -> None:
    if self._config.cost.hard_limit > 0 and ctx.total_cost_usd >= self._config.cost.hard_limit:
        raise CostLimitExceededError(self._config.cost.hard_limit, ctx.total_cost_usd)
    if self._config.cost.warn_threshold > 0 and ctx.total_cost_usd >= self._config.cost.warn_threshold:
        await self._events.emit("cost_warning", {
            "threshold": self._config.cost.warn_threshold,
            "current": ctx.total_cost_usd,
        })
```

---

## 9. Async Patterns

### Core Pattern: asyncio for I/O-bound Parallelism

The consensus engine is I/O-bound — waiting on network calls to model APIs. CPU work (string processing, template rendering, database operations) is negligible. asyncio is the right concurrency model.

### Consensus Loop Orchestration

```python
# Simplified flow showing async patterns

async def run_consensus(query: str, providers: ProviderManager, config: DuhConfig):
    """
    The main async flow:

    1. DECOMPOSE: Single sequential call to strong model
    2. For each task:
       a. PROPOSE: Single sequential call (streaming for UI)
       b. CHALLENGE: Parallel fan-out to all challengers
       c. REVISE: Single sequential call (uses challenge results)
       d. COMMIT: Sequential DB write + parallel summary generation
    3. COMPLETE: Return results
    """

    # DECOMPOSE — sequential, one strong model
    tasks = await decompose(query, providers)

    for task in tasks:
        # PROPOSE — sequential, one model, streaming
        proposal = await propose(task, providers, stream=True)

        for round_num in range(config.general.max_rounds):
            # CHALLENGE — parallel fan-out
            # This is the key parallelism point:
            # Multiple models receive the proposal simultaneously
            challenges = await challenge_parallel(proposal, providers)

            # REVISE — sequential, one model synthesizes
            revision = await revise(proposal, challenges, providers)

            proposal = revision  # Revised proposal becomes next round's input

        # COMMIT — sequential DB write, parallel summary
        await commit(task, proposal, challenges, memory)


async def challenge_parallel(
    proposal: Proposal,
    providers: ProviderManager,
) -> list[Challenge]:
    """Fan out to all challenger models in parallel."""

    # Create tasks for each challenger
    challenger_coros = [
        providers.send(model_ref, build_challenge_prompt(proposal, framing))
        for model_ref, framing in get_challenger_assignments(providers)
    ]

    # Execute all in parallel — this is where we save wall-clock time
    results = await asyncio.gather(*challenger_coros, return_exceptions=True)

    # Process results, handle failures gracefully
    return [parse_challenge(r) for r in results if not isinstance(r, Exception)]
```

### Streaming Pattern

```python
# Streaming a model response while updating the CLI display

async def stream_with_display(
    provider: ModelProvider,
    messages: list[PromptMessage],
    model_id: str,
    display: ConsensusDisplay,
) -> ModelResponse:
    """
    Stream tokens from a model and update the CLI in real time.
    Collects the full response for storage.
    """
    full_text = ""
    usage = None

    async for chunk in provider.stream(messages, model_id):
        full_text += chunk.text
        display.update_streaming_text(full_text)

        if chunk.is_final:
            usage = chunk.usage

    return ModelResponse(
        content=full_text,
        usage=usage,
        # ... other fields
    )
```

### Timeout Management

```python
# Per-provider timeout with asyncio.wait_for

async def send_with_timeout(
    provider: ModelProvider,
    messages: list[PromptMessage],
    model_id: str,
    timeout_seconds: float = 120.0,
) -> ModelResponse:
    """Wrap provider.send with a timeout."""
    try:
        return await asyncio.wait_for(
            provider.send(messages, model_id),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError:
        raise ProviderTimeoutError(
            provider.provider_id,
            f"Model {model_id} timed out after {timeout_seconds}s",
        )
```

### Event Bus for UI Updates

```python
# src/duh/core/events.py

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine


class EventBus:
    """
    Simple async event bus for decoupling the consensus engine from the UI.
    The engine emits events; the CLI display subscribes to them.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable]] = defaultdict(list)

    def on(self, event: str, handler: Callable[..., Coroutine]) -> None:
        """Subscribe to an event."""
        self._handlers[event].append(handler)

    async def emit(self, event: str, data: Any = None) -> None:
        """Emit an event to all subscribers."""
        for handler in self._handlers.get(event, []):
            await handler(data)


# Usage:
# event_bus.on("state_transition", display.on_state_change)
# event_bus.on("stream_chunk", display.on_stream_chunk)
# event_bus.on("provider_error", display.on_provider_error)
# event_bus.on("cost_warning", display.on_cost_warning)
```

### Database Session Pattern

```python
# Async context manager for database operations

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession


class MemoryRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    @asynccontextmanager
    async def _session(self):
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def save_thread(self, thread: Thread) -> None:
        async with self._session() as session:
            session.add(thread)

    async def get_thread(self, thread_id: str) -> Thread | None:
        async with self._session() as session:
            return await session.get(Thread, thread_id)
```

---

## 10. Docker Setup

### Dockerfile

```dockerfile
# syntax=docker/dockerfile:1

# ─── Build stage ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first for cache efficiency
COPY pyproject.toml uv.lock ./

# Install dependencies (cached layer)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code
COPY src/ src/
COPY alembic.ini alembic/
COPY config/ config/

# Install the project itself
RUN uv sync --frozen --no-dev


# ─── Runtime stage ────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Security: non-root user
RUN groupadd --gid 1000 duh && \
    useradd --uid 1000 --gid duh --shell /bin/bash --create-home duh

WORKDIR /app

# Copy the virtual environment from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/config /app/config

# Ensure venv is on PATH
ENV PATH="/app/.venv/bin:$PATH"
ENV DUH_DATA_DIR="/data"

# Data directory for SQLite and logs
RUN mkdir -p /data && chown duh:duh /data
VOLUME ["/data"]

# Config directory (mount user config here)
RUN mkdir -p /config && chown duh:duh /config
VOLUME ["/config"]

USER duh

# Health check — verify the CLI loads
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD ["duh", "--version"]

ENTRYPOINT ["duh"]
CMD ["--help"]
```

### docker-compose.yml

```yaml
# docker-compose.yml — Local development and simple deployment

services:
  duh:
    build:
      context: .
      dockerfile: Dockerfile
    volumes:
      # Persist database and logs
      - duh-data:/data
      # Mount local config
      - ./config:/config:ro
    environment:
      # API keys — pass from host environment
      - ANTHROPIC_API_KEY
      - OPENAI_API_KEY
      - GOOGLE_API_KEY
      # Config override
      - DUH_CONFIG=/config/config.toml
      # Database (default: SQLite in /data)
      - DUH_DATABASE_URL=sqlite+aiosqlite:///data/duh.db
    # Override entrypoint for interactive use
    stdin_open: true
    tty: true

  # Optional: PostgreSQL for production-grade persistence
  postgres:
    image: postgres:16-alpine
    profiles: ["postgres"]  # Only starts with --profile postgres
    volumes:
      - pg-data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: duh
      POSTGRES_USER: duh
      POSTGRES_PASSWORD: ${DUH_PG_PASSWORD:-duh_dev_password}
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U duh"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  duh-data:
  pg-data:
```

### Running

```bash
# Build and run interactively
docker compose run --rm duh ask "What is the best database for a 10M user application?"

# Run with PostgreSQL backend
docker compose --profile postgres up -d postgres
docker compose run --rm \
  -e DUH_DATABASE_URL="postgresql+asyncpg://duh:duh_dev_password@postgres/duh" \
  duh ask "What is the best database for a 10M user application?"

# List models
docker compose run --rm duh models

# View threads
docker compose run --rm duh threads
```

### Development Without Docker

```bash
# Clone, install, run
uv sync
uv run duh ask "What is the best database for a 10M user application?"

# Or install globally
uv tool install .
duh ask "What is the best database for a 10M user application?"
```

---

## Appendix A: Dependency Summary

### Core Dependencies

| Package | Purpose | Phase |
|---------|---------|-------|
| `anthropic` | Claude provider SDK | 1 |
| `openai` | OpenAI / compatible provider SDK | 1 |
| `google-genai` | Gemini provider SDK | 1 |
| `sqlalchemy[asyncio]` | Database ORM | 1 |
| `aiosqlite` | Async SQLite driver | 1 |
| `alembic` | Database migrations | 1 |
| `rich` | CLI display, progress bars, panels | 1 |
| `click` | CLI argument parsing | 1 |
| `pydantic` | Config validation, data models | 1 |
| `tomli` / `tomli-w` | TOML config parsing (tomllib stdlib in 3.11+) | 1 |
| `asyncpg` | Async PostgreSQL driver (optional) | 1 |
| `textual` | Full TUI (if needed beyond Rich) | 2 |

### Development Dependencies

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `pytest-cov` | Coverage reporting |
| `ruff` | Linting and formatting |
| `mypy` | Static type checking |
| `pre-commit` | Git hooks for quality |

---

## Appendix B: Phase 1 Delivery Scope

Based on `projectbrief.md#Build Sequence`, Phase 1 (Core Loop — CLI POC) includes:

1. Provider adapters: Anthropic, OpenAI, Ollama (3 providers)
2. Consensus state machine: PROPOSE, CHALLENGE, REVISE, COMMIT (skip DECOMPOSE in Phase 1 — treat every query as a single task)
3. SQLite memory: Layer 1 only (threads, turns, contributions, summaries)
4. Turn/thread summaries via fast model
5. Rich CLI with live display
6. TOML configuration
7. Basic cost tracking
8. Docker distribution

**Not in Phase 1**: DECOMPOSE (multi-task), Layer 2 memory (decisions, patterns, outcomes), semantic search, web interface, network/federation, outcome tracking.

This keeps Phase 1 focused on proving the core value proposition: multi-model consensus produces better results than any single model, and you can see it happening.

---

## Appendix C: Open Design Questions for Team Discussion

1. **Proposer rotation vs. fixed**: Should the proposer rotate through models each task, or should the user pick a fixed proposer? Current design: configurable via `proposer_strategy`.

2. **DECOMPOSE complexity**: Task decomposition is a hard problem. Phase 1 skips it (every query = one task). When we add it in Phase 2, should decomposition itself be a consensus operation (multiple models decompose, then vote on task list)?

3. **Summary model selection**: Thread summaries should use the cheapest available model. If Ollama is configured with a local model, always prefer local for summaries (zero cost). How explicit should this routing be?

4. **Challenge round dynamics**: Fixed max_rounds=3 is a starting point. Should the engine detect "convergence" (challenges becoming trivial) and commit early? The adaptive stability detection paper (Section 3 of competitive landscape) suggests this is valuable.

5. **Embedding storage**: The schema uses JSON for vector storage (SQLite compatible). For PostgreSQL, pgvector is the right answer. Should we abstract this behind a VectorStore interface, or just conditional code based on database URL?

6. **Provider adapter as plugins**: Current design has adapters as modules inside the package. Should we support external adapter packages (e.g., `duh-provider-cohere`) for providers we don't ship? This adds complexity but enables community contributions.
