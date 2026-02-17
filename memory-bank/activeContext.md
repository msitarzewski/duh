# Active Context

**Last Updated**: 2026-02-16
**Current Phase**: v0.3 COMPLETE — "It's Accessible"
**Next Action**: Merge v0.3.0 branch to main, deploy docs, begin v0.4 planning.

---

## Current State

- **v0.3 COMPLETE.** All 17 tasks done across 7 phases.
- **5 providers shipping**: Anthropic (3 models), OpenAI (3 models), Google (4 models), Mistral (4 models) — 14 total.
- 1318 tests passing, ruff clean, mypy strict clean (50 source files, 5 providers).
- REST API (FastAPI + uvicorn), WebSocket streaming, MCP server, Python client library all built.
- New CLI commands: `duh serve`, `duh mcp`, `duh batch`, `duh export`.
- MkDocs docs site live at https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh
- Branch: `v0.3.0` (ready to merge)

## v0.3 Completed Tasks (17/17)

All phases complete. See `v03-build-status.md` for per-task detail.

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Foundation | T1 Mistral, T2 Export, T3 Batch | Done |
| Phase 2: API Core | T4 Config, T5 FastAPI, T6 API Keys, T7 Auth | Done |
| Phase 3: REST Endpoints | T8 /ask, T9 /threads, T10 /recall+more | Done |
| Phase 4: Streaming | T11 WebSocket | Done |
| Phase 5: MCP | T12 MCP Server | Done |
| Phase 6: Client | T13 duh-client | Done |
| Phase 7: Ship | T14 Integration tests, T15 Docs, T17 Version bump | Done |

## v0.3 Architecture (Decided)

- **MCP server calls Python directly** — no REST dependency. `duh mcp` starts standalone.
- **REST API reuses existing async functions** — FastAPI endpoints wrap `_run_consensus`, `_ask_voting_async`, etc.
- **WebSocket uses existing `stream()` methods** — phase-level events during consensus.
- **API keys are local-only** — hashed in SQLite/Postgres, `X-API-Key` header.
- **Mistral adapter follows OpenAI pattern** — chat completion API with similar shapes.
- **Client library is a thin REST wrapper** — async httpx + sync convenience wrappers in `client/`.

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Hosted demo economics — v0.4 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
