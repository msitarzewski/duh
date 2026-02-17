# Active Context

**Last Updated**: 2026-02-16
**Current Phase**: v0.3 — "It's Accessible"
**Next Action**: Begin Phase 1 tasks (Mistral adapter, export, batch mode).

---

## Current State

- **v0.2 COMPLETE + post-v0.2 polish merged.** Subtask progress display shipped.
- **4 providers shipping**: Anthropic (3 models), OpenAI (3 models), Google (4 models) — 10 total.
- 1093 tests passing, ruff clean, mypy strict clean (39 source files, 4 providers).
- MkDocs docs site live at https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh
- Branch: `v0.3.0` created from `main`

## v0.3 Task List

### Phase 1: Foundation (independent, parallelizable)

1. **Mistral provider adapter** — `src/duh/providers/mistral.py`. Follow OpenAI adapter pattern. Known models: mistral-large, mistral-medium, mistral-small, codestral. Dep: `mistralai>=1.0`. Tests: send, stream, health_check, error mapping, model listing.
2. **Export formatters + CLI** — `duh export <thread-id> --format json|markdown`. Export full thread with debate history. `src/duh/cli/export.py` or extend `app.py`. Tests: JSON output structure, markdown rendering, missing thread handling.
3. **Batch mode CLI** — `duh batch questions.txt`. Read questions from file (one per line or JSONL), run consensus on each, output results. `src/duh/cli/batch.py` or extend `app.py`. Tests: file parsing, sequential execution, error handling, output formatting.

### Phase 2: API Core

4. **API config schema** — Add `APIConfig` to `src/duh/config/schema.py`: host, port, api_keys list, cors_origins, rate_limit. Extend TOML config with `[api]` section. Tests: defaults, validation, TOML loading.
5. **FastAPI app + serve command** — `src/duh/api/app.py` (FastAPI app factory), `duh serve` CLI command (runs uvicorn). Deps: `fastapi>=0.115`, `uvicorn[standard]>=0.30`. Lifespan handler for DB + provider setup. Tests: app creation, lifespan, serve command.
6. **API key model + repository** — `APIKey` SQLAlchemy model (id, key_hash, name, created_at, revoked_at). Repository methods: create_api_key, validate_api_key, revoke_api_key, list_api_keys. Migration `004_v03_api_keys.py`. Tests: CRUD, hash validation, revocation.
7. **Auth + rate-limit middleware** — API key validation middleware (header `X-API-Key`), rate limiting (per-key, configurable). CORS middleware from config. Tests: valid key, invalid key, revoked key, rate limit enforcement, CORS headers.

### Phase 3: REST Endpoints

8. **POST /api/ask** — Consensus, voting, and decompose protocols via REST. Request body: question, protocol, rounds, decompose, tools. Response: decision, confidence, dissent, cost, thread_id. Reuses `_run_consensus`, `_ask_voting_async`, `_ask_decompose_async` logic. Tests: all three protocols, error responses, cost tracking.
9. **GET /api/threads + /api/threads/{id}** — List and detail endpoints. Query params: status, limit, offset. Detail includes full debate history (turns, contributions, decisions). Tests: listing, filtering, pagination, prefix matching, 404.
10. **GET /api/recall + POST /api/feedback + GET /api/models + GET /api/cost** — Remaining CRUD endpoints mirroring CLI. Tests: search, feedback recording, model listing, cost aggregation.

### Phase 4: Streaming

11. **WebSocket /ws/ask** — Real-time streaming of consensus phases. Client sends question, server streams phase events (propose_start, propose_content, challenge_start, etc.) as JSON messages. Uses existing `stream()` provider methods. Tests: connection lifecycle, message format, error handling, disconnect.

### Phase 5: MCP Server

12. **MCP server implementation** — `src/duh/mcp/server.py`. Expose as MCP tools: `duh_ask` (question, protocol, rounds), `duh_recall` (query, limit), `duh_threads` (status, limit). Direct Python calls (no REST dependency). `duh mcp` CLI command starts the server. Dep: `mcp>=1.0`. Tests: tool schemas, tool execution, error handling.

### Phase 6: Python Client

13. **Python client library** — `duh-client` package (separate `pyproject.toml` in `client/` or top-level). Wraps REST API. `DuhClient` class: ask(), recall(), threads(), show(), feedback(), models(), cost(). Async and sync interfaces. Dep: `httpx>=0.27`. Tests: all methods, error handling, auth header.

### Phase 7: Quality + Ship

14. **Integration tests** — API end-to-end (full consensus via REST), WebSocket streaming, MCP tool invocation, client library against test server, batch processing, export round-trip.
15. **Documentation** — MkDocs pages: API reference (OpenAPI), Python client quickstart, MCP server guide, batch mode guide, export guide. Update README.
16. **Alembic migration for API keys** — `004_v03_api_keys.py` (if not done in T6).
17. **Version bump to 0.3.0** — `pyproject.toml`, `__init__.py`, CHANGELOG, README badge.

### Dependency Graph

```
Phase 1 (independent):  T1, T2, T3

Phase 2 (sequential):   T4 → T5 → T6 → T7

Phase 3 (after T5+T7):  T8, T9, T10

Phase 4 (after T5+T7):  T11

Phase 5 (after T1):     T12

Phase 6 (after T8-T10): T13

Phase 7 (after all):    T14 → T15 → T17
```

### New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `>=0.115` | REST API framework |
| `uvicorn[standard]` | `>=0.30` | ASGI server |
| `httpx` | `>=0.27` | Python client HTTP |
| `mistralai` | `>=1.0` | Mistral provider SDK |
| `mcp` | `>=1.0` | MCP server SDK |

## Key Architecture Decisions for v0.3

- **MCP server calls Python directly** — no REST dependency. `duh mcp` starts standalone.
- **REST API reuses existing async functions** — `_run_consensus`, `_ask_voting_async`, etc. are already protocol-agnostic. FastAPI endpoints wrap them.
- **WebSocket uses existing `stream()` methods** — all 4 providers already implement streaming. WS endpoint orchestrates phase-level events.
- **API keys are local-only** — hashed in SQLite/Postgres, no external auth service. Simple `X-API-Key` header.
- **Mistral adapter follows OpenAI pattern** — both are chat completion APIs with similar shapes.
- **Client library is a thin REST wrapper** — async httpx under the hood, sync convenience wrappers.

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Hosted demo economics — v0.4 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
