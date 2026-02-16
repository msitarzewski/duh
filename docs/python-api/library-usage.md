# Library Usage

Use duh as a Python library for programmatic consensus, custom providers, and integration into your own applications.

## Installation

```bash
uv add duh
# or
pip install duh
```

## Providers

### Register providers

```python
from duh.providers.anthropic import AnthropicProvider
from duh.providers.openai import OpenAIProvider
from duh.providers.manager import ProviderManager

pm = ProviderManager(cost_hard_limit=10.0)

# Register Anthropic
anthropic_prov = AnthropicProvider(api_key="sk-ant-...")
await pm.register(anthropic_prov)

# Register OpenAI
openai_prov = OpenAIProvider(api_key="sk-...")
await pm.register(openai_prov)

# Register a local model (Ollama via OpenAI-compatible API)
local_prov = OpenAIProvider(base_url="http://localhost:11434/v1")
await pm.register(local_prov)
```

### Discover models

```python
models = pm.list_all_models()
for model in models:
    print(f"{model.model_ref}: {model.display_name} ({model.context_window:,} ctx)")
```

### Send a prompt directly

```python
from duh.providers.base import PromptMessage

provider, model_id = pm.get_provider("anthropic:claude-opus-4-6")
response = await provider.send(
    messages=[
        PromptMessage(role="system", content="You are a helpful assistant."),
        PromptMessage(role="user", content="What is consensus?"),
    ],
    model_id=model_id,
    max_tokens=1024,
    temperature=0.7,
)
print(response.content)
print(f"Tokens: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
```

## Consensus

### Run the full protocol

```python
from duh.consensus.machine import ConsensusContext, ConsensusState, ConsensusStateMachine
from duh.consensus.handlers import (
    handle_propose,
    handle_challenge,
    handle_revise,
    handle_commit,
    select_proposer,
    select_challengers,
)
from duh.consensus.convergence import check_convergence

# Create context
ctx = ConsensusContext(
    thread_id="my-thread-1",
    question="What database should I use for a new SaaS product?",
    max_rounds=3,
)
sm = ConsensusStateMachine(ctx)

for round_num in range(ctx.max_rounds):
    # PROPOSE
    sm.transition(ConsensusState.PROPOSE)
    proposer = select_proposer(pm)
    await handle_propose(ctx, pm, proposer)

    # CHALLENGE
    sm.transition(ConsensusState.CHALLENGE)
    challengers = select_challengers(pm, proposer)
    await handle_challenge(ctx, pm, challengers)

    # REVISE
    sm.transition(ConsensusState.REVISE)
    await handle_revise(ctx, pm)

    # COMMIT
    sm.transition(ConsensusState.COMMIT)
    await handle_commit(ctx)

    # Check convergence
    if check_convergence(ctx):
        break

sm.transition(ConsensusState.COMPLETE)

print(f"Decision: {ctx.decision}")
print(f"Confidence: {ctx.confidence:.0%}")
print(f"Cost: ${pm.total_cost:.4f}")
if ctx.dissent:
    print(f"Dissent: {ctx.dissent}")
```

### State machine details

The `ConsensusStateMachine` enforces valid transitions with guard conditions:

```python
# Check if a transition is valid
if sm.can_transition(ConsensusState.PROPOSE):
    sm.transition(ConsensusState.PROPOSE)

# See all currently valid transitions
valid = sm.valid_transitions()

# Check terminal state
if sm.is_terminal:
    print("Consensus complete or failed")

# Force a failure
sm.fail("Something went wrong")
```

## Memory

### Create and query threads

```python
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from duh.memory.models import Base
from duh.memory.repository import MemoryRepository

engine = create_async_engine("sqlite+aiosqlite:///duh.db")
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)

SessionFactory = async_sessionmaker(engine, expire_on_commit=False)

async with SessionFactory() as session:
    repo = MemoryRepository(session)

    # Create a thread
    thread = await repo.create_thread("What database should I use?")

    # Create a turn
    turn = await repo.create_turn(thread.id, round_number=1, state="propose")

    # Add a contribution
    await repo.add_contribution(
        turn_id=turn.id,
        model_ref="anthropic:claude-opus-4-6",
        role="proposer",
        content="PostgreSQL is the best choice...",
        input_tokens=150,
        output_tokens=500,
        cost_usd=0.013,
        latency_ms=1200.0,
    )

    # Save a decision
    await repo.save_decision(
        turn_id=turn.id,
        thread_id=thread.id,
        content="PostgreSQL is the best choice...",
        confidence=0.85,
        dissent="Some concern about operational complexity",
    )

    await session.commit()

    # Search
    results = await repo.search("database", limit=10)
    for t in results:
        print(f"{t.id[:8]}: {t.question}")

    # List threads
    threads = await repo.list_threads(status="complete", limit=20)

    # Get full thread with history
    full_thread = await repo.get_thread(thread.id)
```

## Cost tracking

```python
# Track costs during consensus
print(f"Total: ${pm.total_cost:.4f}")
print(f"By provider: {pm.cost_by_provider}")

# Record usage manually
from duh.providers.base import TokenUsage

model_info = pm.get_model_info("anthropic:claude-opus-4-6")
usage = TokenUsage(input_tokens=1000, output_tokens=500)
call_cost = pm.record_usage(model_info, usage)
print(f"This call: ${call_cost:.4f}")

# Reset cost accumulator
pm.reset_cost()
```

## Configuration

### Load config programmatically

```python
from duh.config.loader import load_config

# Load with auto-discovery
config = load_config()

# Load specific file
config = load_config(path="./my-config.toml")

# Load with overrides
config = load_config(overrides={
    "general": {"max_rounds": 5},
    "cost": {"hard_limit": 20.0},
})

print(f"Max rounds: {config.general.max_rounds}")
print(f"DB URL: {config.database.url}")
```

## Custom provider

Implement the `ModelProvider` protocol to add your own provider:

```python
from duh.providers.base import (
    ModelCapability,
    ModelInfo,
    ModelProvider,
    ModelResponse,
    PromptMessage,
    StreamChunk,
    TokenUsage,
)
from collections.abc import AsyncIterator


class MyProvider:
    """Custom provider implementing ModelProvider protocol."""

    @property
    def provider_id(self) -> str:
        return "my-provider"

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(
                provider_id="my-provider",
                model_id="my-model-v1",
                display_name="My Model v1",
                capabilities=ModelCapability.TEXT | ModelCapability.SYSTEM_PROMPT,
                context_window=8192,
                max_output_tokens=4096,
                input_cost_per_mtok=0.0,
                output_cost_per_mtok=0.0,
                is_local=True,
            )
        ]

    async def send(
        self,
        messages: list[PromptMessage],
        model_id: str,
        *,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stop_sequences: list[str] | None = None,
    ) -> ModelResponse:
        # Your implementation here
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
        # Your implementation here
        ...

    async def health_check(self) -> bool:
        return True
```

Register it:

```python
pm = ProviderManager()
my_prov = MyProvider()
await pm.register(my_prov)
```

## Next steps

- [Providers and Models](../concepts/providers-and-models.md) -- Provider architecture details
- [How Consensus Works](../concepts/how-consensus-works.md) -- Protocol internals
- [Errors](../reference/errors.md) -- Error hierarchy for exception handling
