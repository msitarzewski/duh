# v0.3 Build Status

**Last Updated**: 2026-02-16
**Branch**: v0.3.0
**Status**: **COMPLETE** — All 17 tasks done

---

## Task Status (17 tasks)

| # | Task | Status | Tests Added |
|---|------|--------|-------------|
| T1 | Mistral provider adapter | DONE | 29 tests |
| T2 | Export formatters + CLI | DONE | 13 tests |
| T3 | Batch mode CLI | DONE | 29 tests |
| T4 | API config schema | DONE | 21 tests |
| T5 | FastAPI app + serve command | DONE | 4 tests |
| T6 | API key model + repository | DONE | 10 tests |
| T7 | Auth + rate-limit middleware | DONE | 16 tests |
| T8 | POST /api/ask endpoint | DONE | 10 tests |
| T9 | GET /api/threads endpoints | DONE | 13 tests |
| T10 | Remaining CRUD endpoints | DONE | 15 tests |
| T11 | WebSocket /ws/ask streaming | DONE | 11 tests |
| T12 | MCP server implementation | DONE | 18 tests |
| T13 | Python client library | DONE | client tests |
| T14 | Integration tests | DONE | v0.3 API integration tests |
| T15 | Documentation | DONE | MkDocs pages |
| T16 | Alembic migration (API keys) | DONE (part of T6) | - |
| T17 | Version bump to 0.3.0 | DONE | - |

## Test Count: 1318 passing

## Files Created/Modified in v0.3

### New source files:
- `src/duh/providers/mistral.py` — Mistral adapter (4 models)
- `src/duh/api/__init__.py` — API package
- `src/duh/api/app.py` — FastAPI factory, lifespan, middleware, route registration
- `src/duh/api/middleware.py` — APIKeyMiddleware, RateLimitMiddleware, hash_api_key()
- `src/duh/api/routes/__init__.py` — Routes package
- `src/duh/api/routes/ask.py` — POST /api/ask (consensus, voting, decompose)
- `src/duh/api/routes/threads.py` — GET /api/threads, GET /api/threads/{id}
- `src/duh/api/routes/crud.py` — GET /api/recall, POST /api/feedback, GET /api/models, GET /api/cost
- `src/duh/api/routes/ws.py` — WebSocket /ws/ask streaming
- `src/duh/mcp/__init__.py` — MCP package
- `src/duh/mcp/server.py` — MCP server (duh_ask, duh_recall, duh_threads tools)
- `alembic/versions/004_v03_api_keys.py` — API keys migration

### Modified source files:
- `pyproject.toml` — Added mistralai, fastapi, uvicorn, mcp deps
- `src/duh/config/schema.py` — Added APIConfig, mistral provider default
- `src/duh/cli/app.py` — Added export, batch, serve, mcp commands + Mistral registration
- `src/duh/memory/models.py` — Added APIKey model
- `src/duh/memory/repository.py` — Added API key CRUD methods

### New test files:
- `tests/unit/test_providers_mistral.py` (29)
- `tests/unit/test_cli_export.py` (13)
- `tests/unit/test_cli_batch.py` (29)
- `tests/unit/test_config_v03.py` (21)
- `tests/unit/test_api_app.py` (4)
- `tests/unit/test_api_keys.py` (10)
- `tests/unit/test_api_middleware.py` (16)
- `tests/unit/test_api_ask.py` (10)
- `tests/unit/test_api_threads.py` (13)
- `tests/unit/test_api_crud.py` (15)
- `tests/unit/test_api_ws.py` (11)
- `tests/unit/test_mcp_server.py` (18)

### Client library (T13 — in progress):
- `client/pyproject.toml`
- `client/src/duh_client/__init__.py`
- `client/src/duh_client/client.py` — DuhClient class, async+sync, all endpoints
- `client/tests/test_client.py`

## What To Do Next

1. **Merge v0.3.0 branch** into main
2. **Deploy updated docs** to GitHub Pages
3. **Begin v0.4 planning** — see `activeContext.md` for next priorities

## REST API Endpoints Summary

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/health | Health check |
| POST | /api/ask | Run consensus/voting/decompose |
| GET | /api/threads | List threads |
| GET | /api/threads/{id} | Thread detail |
| GET | /api/recall | Search past decisions |
| POST | /api/feedback | Record outcome |
| GET | /api/models | List available models |
| GET | /api/cost | Cost summary |
| WS | /ws/ask | Stream consensus phases |

## CLI Commands Added in v0.3

- `duh export <thread-id> --format json|markdown`
- `duh batch <file> --protocol --rounds --format`
- `duh serve --host --port --reload`
- `duh mcp`

## Dependencies Added in v0.3

- `mistralai>=1.0`
- `fastapi>=0.115`
- `uvicorn[standard]>=0.30`
- `mcp>=1.0`
- `httpx>=0.27` (client library)
