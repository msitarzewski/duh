# REST API Reference

duh exposes a REST API via `duh serve` for programmatic access to the consensus engine.

## Starting the server

```bash
duh serve                          # Default: 127.0.0.1:8080
duh serve --host 0.0.0.0 --port 9000
duh serve --reload                 # Auto-reload for development
```

Server configuration lives in `[api]` in your config file. See [Config Reference](reference/config-reference.md#api).

## Authentication

API requests are authenticated via the `X-API-Key` header:

```bash
curl -H "X-API-Key: your-key" http://localhost:8080/api/ask ...
```

In **development mode** (no API keys configured in the database), authentication is skipped and all requests are allowed.

Rate limiting applies per API key (or per IP when unauthenticated). Default: 60 requests per minute. Rate limit headers are returned on every response:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Max requests per window |
| `X-RateLimit-Remaining` | Remaining requests in current window |

## Endpoints

### POST /api/ask

Run a consensus query.

**Request body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `question` | string | *required* | The question to get consensus on |
| `protocol` | string | `"consensus"` | Protocol: `consensus`, `voting`, or `auto` |
| `rounds` | integer | `3` | Max consensus rounds |
| `decompose` | boolean | `false` | Decompose into subtasks first |
| `tools` | boolean | `false` | Enable tool use |
| `panel` | list[string] | `null` | Restrict to these model refs only (e.g. `["anthropic:claude-opus-4-6", "openai:gpt-5.2"]`) |
| `proposer` | string | `null` | Override the proposer model ref |
| `challengers` | list[string] | `null` | Override the challenger model refs |

**Response (200):**

```json
{
  "decision": "PostgreSQL is the better choice for most SaaS products...",
  "confidence": 0.85,
  "dissent": "Some concern about operational complexity",
  "cost": 0.0342,
  "thread_id": "a1b2c3d4-...",
  "protocol_used": "consensus"
}
```

**Example:**

```bash
curl -X POST http://localhost:8080/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What database should I use for a new SaaS product?"}'
```

With voting protocol:

```bash
curl -X POST http://localhost:8080/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "REST vs GraphQL?", "protocol": "voting"}'
```

**Error responses:**

| Status | Cause |
|--------|-------|
| 400 | Invalid request or duh error |
| 401 | Missing or invalid API key |
| 429 | Rate limit exceeded |
| 502 | Consensus engine error |
| 503 | Provider error (model API unreachable) |

---

### GET /api/threads

List past consensus threads.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `status` | string | *all* | Filter by status: `active`, `complete`, `failed` |
| `limit` | integer | `20` | Max results |
| `offset` | integer | `0` | Pagination offset |

**Response (200):**

```json
{
  "threads": [
    {
      "thread_id": "a1b2c3d4-...",
      "question": "What database should I use?",
      "status": "complete",
      "created_at": "2026-02-15T10:30:00"
    }
  ],
  "total": 1
}
```

**Example:**

```bash
curl http://localhost:8080/api/threads?limit=5&status=complete
```

---

### GET /api/threads/{thread_id}

Get a thread with its full debate history. Supports prefix matching (minimum 8 characters).

**Response (200):**

```json
{
  "thread_id": "a1b2c3d4-...",
  "question": "What database should I use?",
  "status": "complete",
  "created_at": "2026-02-15T10:30:00",
  "turns": [
    {
      "round_number": 1,
      "state": "propose",
      "contributions": [
        {
          "model_ref": "anthropic:claude-opus-4-6",
          "role": "proposer",
          "content": "PostgreSQL is the best choice...",
          "input_tokens": 150,
          "output_tokens": 500,
          "cost_usd": 0.013
        }
      ],
      "decision": {
        "content": "The choice depends on your workload...",
        "confidence": 0.85,
        "dissent": null
      }
    }
  ]
}
```

**Example:**

```bash
curl http://localhost:8080/api/threads/a1b2c3d4
```

**Errors:**

| Status | Cause |
|--------|-------|
| 400 | Ambiguous thread ID prefix |
| 404 | Thread not found |

---

### GET /api/recall

Search past decisions by keyword.

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | *required* | Search keyword |
| `limit` | integer | `10` | Max results |

**Response (200):**

```json
{
  "results": [
    {
      "thread_id": "a1b2c3d4-...",
      "question": "What database should I use?",
      "decision": "PostgreSQL is the best choice...",
      "confidence": 0.85
    }
  ],
  "query": "database"
}
```

**Example:**

```bash
curl "http://localhost:8080/api/recall?query=database&limit=5"
```

---

### POST /api/feedback

Record an outcome for a past decision.

**Request body:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `thread_id` | string | *required* | Thread ID (full or prefix) |
| `result` | string | *required* | `success`, `failure`, or `partial` |
| `notes` | string | `null` | Optional notes about the outcome |

**Response (200):**

```json
{
  "status": "recorded",
  "thread_id": "a1b2c3d4-..."
}
```

**Example:**

```bash
curl -X POST http://localhost:8080/api/feedback \
  -H "Content-Type: application/json" \
  -d '{"thread_id": "a1b2c3d4", "result": "success", "notes": "Worked great"}'
```

---

### GET /api/models

List available models across all configured providers.

**Response (200):**

```json
{
  "models": [
    {
      "provider_id": "anthropic",
      "model_id": "claude-opus-4-6",
      "display_name": "Claude Opus 4.6",
      "context_window": 200000,
      "max_output_tokens": 4096,
      "input_cost_per_mtok": 15.0,
      "output_cost_per_mtok": 75.0
    }
  ],
  "total": 5
}
```

**Example:**

```bash
curl http://localhost:8080/api/models
```

---

### GET /api/cost

Show cumulative cost from all stored contributions.

**Response (200):**

```json
{
  "total_cost": 0.0342,
  "total_input_tokens": 2450,
  "total_output_tokens": 1890,
  "by_model": [
    {
      "model_ref": "anthropic:claude-opus-4-6",
      "cost": 0.028,
      "calls": 2
    },
    {
      "model_ref": "openai:gpt-5.2",
      "cost": 0.0062,
      "calls": 1
    }
  ]
}
```

**Example:**

```bash
curl http://localhost:8080/api/cost
```

---

### GET /api/health

Health check endpoint. Not authenticated.

**Response (200):**

```json
{
  "status": "ok"
}
```

---

### WebSocket /ws/ask

Stream consensus phases in real-time over WebSocket.

**Client sends:**

```json
{"question": "What database should I use?", "rounds": 3}
```

Optional model selection fields: `panel` (list of model refs), `proposer` (model ref), `challengers` (list of model refs).

**Server streams events:**

```json
{"type": "phase_start", "phase": "PROPOSE", "model": "anthropic:claude-opus-4-6", "round": 1}
{"type": "phase_complete", "phase": "PROPOSE", "content": "PostgreSQL is..."}
{"type": "phase_start", "phase": "CHALLENGE", "models": ["openai:gpt-5.2"], "round": 1}
{"type": "challenge", "model": "openai:gpt-5.2", "content": "I disagree..."}
{"type": "phase_complete", "phase": "CHALLENGE"}
{"type": "phase_start", "phase": "REVISE", "model": "anthropic:claude-opus-4-6", "round": 1}
{"type": "phase_complete", "phase": "REVISE", "content": "The choice depends..."}
{"type": "commit", "confidence": 0.85, "dissent": null, "round": 1}
{"type": "complete", "decision": "The choice depends...", "confidence": 0.85, "cost": 0.04}
```

**Event types:**

| Type | Description |
|------|-------------|
| `phase_start` | A consensus phase is starting. Includes `phase`, `model`/`models`, `round`. |
| `phase_complete` | A phase finished. Includes `content` for PROPOSE and REVISE. |
| `challenge` | Individual challenge from a model. |
| `commit` | Round committed with `confidence` and `dissent`. |
| `complete` | Consensus finished. Final `decision`, `confidence`, and `cost`. |
| `error` | Something went wrong. Includes `message`. |

**Example (JavaScript):**

```javascript
const ws = new WebSocket("ws://localhost:8080/ws/ask");
ws.onopen = () => {
  ws.send(JSON.stringify({question: "What database should I use?", rounds: 3}));
};
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.type, data);
};
```

## OpenAPI docs

When the server is running, interactive API docs are available at:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`
- **OpenAPI JSON**: `http://localhost:8080/openapi.json`
