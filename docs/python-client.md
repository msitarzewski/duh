# Python Client

The `duh-client` package provides async and sync Python clients for the duh REST API.

## Installation

```bash
pip install duh-client
```

## Quick start

### Async usage

```python
from duh_client import DuhClient

async with DuhClient("http://localhost:8080", api_key="your-key") as client:
    result = await client.ask("What is the best auth strategy?")
    print(result.decision)
    print(f"Confidence: {result.confidence:.0%}")
    print(f"Cost: ${result.cost:.4f}")
```

### Sync usage

```python
from duh_client import DuhClient

client = DuhClient("http://localhost:8080")
result = client.ask_sync("Compare REST vs GraphQL")
print(result.decision)
```

## Client initialization

```python
DuhClient(
    base_url="http://localhost:8080",  # Server URL
    api_key=None,                       # Optional API key
    timeout=120.0,                      # Request timeout in seconds
)
```

The API key is sent as the `X-API-Key` header on every request. If no API key is provided and the server has no keys configured, requests proceed without authentication.

## Methods

### ask / ask_sync

Run a consensus query.

```python
result = await client.ask(
    "What database should I use for a new SaaS product?",
    protocol="consensus",   # "consensus", "voting", or "auto"
    rounds=3,               # Max consensus rounds
    decompose=False,        # Decompose into subtasks
    tools=False,            # Enable tool use
)

result.decision       # str -- the consensus decision
result.confidence     # float -- confidence score (0.0-1.0)
result.dissent        # str | None -- preserved dissent
result.cost           # float -- total cost in USD
result.thread_id      # str | None -- thread ID for later reference
result.protocol_used  # str -- protocol that was used
```

### threads / threads_sync

List past consensus threads.

```python
threads = await client.threads(status="complete", limit=10, offset=0)

for t in threads:
    print(f"{t.thread_id[:8]}  [{t.status}]  {t.question}")
```

Returns a list of `ThreadSummary` with `thread_id`, `question`, `status`, `created_at`.

### show

Get a thread with its full debate history.

```python
detail = await client.show("a1b2c3d4")  # Prefix matching supported

print(detail["question"])
for turn in detail["turns"]:
    print(f"Round {turn['round_number']}")
    for c in turn["contributions"]:
        print(f"  [{c['role']}] {c['model_ref']}: {c['content'][:80]}")
```

Returns the full thread dict (see [GET /api/threads/{id}](api-reference.md#get-apithreadsthread_id)).

### recall / recall_sync

Search past decisions by keyword.

```python
results = await client.recall("database", limit=5)

for r in results:
    print(f"{r.thread_id[:8]}  {r.question}")
    if r.decision:
        print(f"  Decision: {r.decision[:100]}")
        print(f"  Confidence: {r.confidence:.0%}")
```

Returns a list of `RecallResult` with `thread_id`, `question`, `decision`, `confidence`.

### feedback

Record an outcome for a past decision.

```python
await client.feedback(
    "a1b2c3d4",
    "success",
    notes="Deployed to production, no issues",
)
```

### models / models_sync

List available models.

```python
models = await client.models()

for m in models:
    print(f"{m['provider_id']}:{m['model_id']}  ctx:{m['context_window']:,}")
```

### cost

Get cumulative cost summary.

```python
cost = await client.cost()

print(f"Total: ${cost['total_cost']:.4f}")
for m in cost["by_model"]:
    print(f"  {m['model_ref']}: ${m['cost']:.4f} ({m['calls']} calls)")
```

### health / health_sync

Check if the server is reachable.

```python
if await client.health():
    print("Server is up")
```

Returns `True` if the server responds with 200, `False` otherwise.

## Error handling

```python
from duh_client import DuhClient, DuhAPIError

try:
    result = await client.ask("question")
except DuhAPIError as e:
    print(f"API error: HTTP {e.status_code}: {e.detail}")
```

`DuhAPIError` is raised for any HTTP 4xx/5xx response with `status_code` and `detail` attributes.

## Full example

```python
import asyncio
from duh_client import DuhClient

async def main():
    async with DuhClient("http://localhost:8080") as client:
        # Check health
        if not await client.health():
            print("Server is not running")
            return

        # Ask a question
        result = await client.ask(
            "What are the trade-offs between PostgreSQL and MySQL for SaaS?",
            rounds=2,
        )
        print(f"Decision: {result.decision}")
        print(f"Confidence: {result.confidence:.0%}")
        print(f"Cost: ${result.cost:.4f}")

        # Record feedback later
        if result.thread_id:
            await client.feedback(result.thread_id, "success")

        # Search past decisions
        results = await client.recall("database")
        print(f"\nFound {len(results)} past decisions about databases")

asyncio.run(main())
```
