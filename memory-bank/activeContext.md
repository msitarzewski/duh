# Active Context

**Last Updated**: 2026-02-17
**Current Phase**: v0.5 COMPLETE — "It Scales"
**Next Action**: Merge `v0.5.0` branch to main, create PR. Then begin v1.0.0 planning.

---

## Current State

- **v0.5 COMPLETE on branch `v0.5.0`.** All 18 tasks done. Ready to merge to main.
- **6 providers shipping**: Anthropic (3 models), OpenAI (3 models), Google (4 models), Mistral (4 models), Perplexity (3 models) — 17 total.
- **1354 Python unit/load tests + 117 Vitest tests** (1471 total), ruff clean.
- **~60 Python source files + 66 frontend source files** (~126 total).
- REST API, WebSocket streaming, MCP server, Python client library, web UI all built.
- Multi-user auth (JWT + RBAC), PostgreSQL support, Prometheus metrics, backup/restore, Playwright E2E.
- CLI commands: `duh ask`, `duh recall`, `duh threads`, `duh show`, `duh models`, `duh cost`, `duh serve`, `duh mcp`, `duh batch`, `duh export`, `duh feedback`, `duh backup`, `duh restore`, `duh user-create`, `duh user-list`.
- Docs: production-deployment.md, monitoring.md, authentication.md added.
- MkDocs docs site: https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh

## v0.5 Delivered

**Theme**: Production hardening, multi-user, enterprise readiness.
**18 tasks across 7 phases** — all complete.

### What Shipped
- User accounts + JWT auth + RBAC (admin/contributor/viewer) — `api/auth.py`, `api/rbac.py`, `models.py:User`
- PostgreSQL support (asyncpg) with connection pooling (`pool_pre_ping`, compound indexes)
- Perplexity provider adapter (6th provider, search-grounded) — `providers/perplexity.py`
- Prometheus metrics (`/api/metrics`) + extended health checks (`/api/health/detailed`)
- Backup/restore CLI (`duh backup`, `duh restore`) with SQLite copy + JSON export/import
- Playwright E2E browser tests (`web/e2e/`)
- Per-user + per-provider rate limiting (middleware keys by user_id > api_key > IP)
- Production deployment documentation (3 new guides)
- 26 multi-user integration tests + 12 load tests (latency, concurrency, rate limiting)
- Alembic migration `005_v05_users.py` (users table, user_id FKs on threads/decisions/api_keys)

### New Source Files (v0.5)
- `src/duh/api/auth.py` — JWT authentication endpoints
- `src/duh/api/rbac.py` — Role-based access control
- `src/duh/api/metrics.py` — Prometheus metrics endpoint
- `src/duh/api/health.py` — Extended health checks
- `src/duh/memory/backup.py` — Backup/restore utilities
- `src/duh/providers/perplexity.py` — Perplexity provider adapter
- `alembic/versions/005_v05_users.py` — User migration
- `docs/guides/production-deployment.md`, `authentication.md`, `monitoring.md`

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred to post-1.0
- A2A protocol — deferred to post-1.0
