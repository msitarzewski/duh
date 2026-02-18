# Active Context

**Last Updated**: 2026-02-17
**Current Phase**: v0.5 + Export Feature
**Next Action**: Merge v0.5.0 to main. Export to Markdown & PDF feature implemented.

## Next Task: Model Selection Controls + Provider Updates

### Context
Users can't control which models participate in consensus. `select_proposer()` picks highest `output_cost_per_mtok`, `select_challengers()` picks next-costliest. Problems: no user control (`ConsensusConfig.panel` exists but unused), Google catalog outdated, Perplexity should be challengers-only (search-grounded), Anthropic missing `claude-sonnet-4-6`.

### Changes (6 steps)

1. **Update provider model catalogs**
   - `src/duh/providers/google.py:34-67` — Gemini 3 GA + early-access models (web search for latest)
   - `src/duh/providers/anthropic.py:36-61` — Add `claude-sonnet-4-6`
   - `src/duh/providers/perplexity.py:35-60` — Verify current model IDs/pricing

2. **Add `proposer_eligible` flag to ModelInfo**
   - `src/duh/providers/base.py:28-45` — Add `proposer_eligible: bool = True`
   - `src/duh/providers/perplexity.py` — Set `proposer_eligible=False` (challengers only, user decision)

3. **Wire `ConsensusConfig.panel` + update selection functions**
   - `src/duh/consensus/handlers.py:185-202` (`select_proposer`) — Accept optional `panel`, filter to `proposer_eligible=True`
   - `src/duh/consensus/handlers.py:322-356` (`select_challengers`) — Accept optional `panel`
   - `src/duh/cli/app.py:236-246`, `src/duh/api/routes/ws.py:108,128`, `src/duh/api/routes/ask.py` — Pass panel

4. **Add CLI flags**: `--proposer MODEL_REF`, `--challengers MODEL_REF,MODEL_REF`, `--panel MODEL_REF,...`
   - `src/duh/cli/app.py` (ask command)

5. **Add to REST API**: Optional `panel`, `proposer`, `challengers` fields in ask request body
   - `src/duh/api/routes/ask.py`

6. **Tests**: Update `test_propose_handler.py`, `test_challenge_handler.py` for panel filtering + proposer_eligible. Test CLI flags. Fix any tests with hardcoded model catalogs.

7. **Documentation + CLI help**
   - `docs/cli/ask.md` — Document `--proposer`, `--challengers`, `--panel` flags
   - `docs/api-reference.md` — Document panel/proposer/challengers in `/api/ask`
   - `docs/concepts/providers-and-models.md` — Update model lists, model selection explanation
   - `docs/getting-started/configuration.md` — Document `[consensus] panel` config
   - `docs/reference/config-reference.md` — Add panel, proposer_strategy fields
   - `src/duh/cli/app.py` — Update Click help strings for new flags
   - `docs/index.md` — Update feature list if needed

### Current model cost ranking (for reference)
| Model | output_cost | Provider |
|-------|------------|----------|
| Opus 4.6 | $25.00 | anthropic |
| Sonar Pro | $15.00 | perplexity |
| Sonnet 4.5 | $15.00 | anthropic |
| GPT-5.2 | $14.00 | openai |
| Gemini 3 Pro | $12.00 | google |
| Gemini 2.5 Pro | $10.00 | google |
| Mistral Medium | $8.10 | mistral |
| o3 | $8.00 | openai |
| Sonar Deep Research | $8.00 | perplexity |
| Mistral Large | $6.00 | mistral |
| Haiku 4.5 | $5.00 | anthropic |

---

## Current State

- **v0.5 + Export feature on branch `v0.5.0`.** All v0.5 tasks done + export feature added.
- **6 providers shipping**: Anthropic (3 models), OpenAI (3 models), Google (4 models), Mistral (4 models), Perplexity (3 models) — 17 total.
- **1539 Python unit/load tests + 122 Vitest tests** (1661 total), ruff clean.
- **~60 Python source files + 67 frontend source files** (~127 total).
- REST API, WebSocket streaming, MCP server, Python client library, web UI all built.
- Multi-user auth (JWT + RBAC), PostgreSQL support, Prometheus metrics, backup/restore, Playwright E2E.
- CLI commands: `duh ask`, `duh recall`, `duh threads`, `duh show`, `duh models`, `duh cost`, `duh serve`, `duh mcp`, `duh batch`, `duh export`, `duh feedback`, `duh backup`, `duh restore`, `duh user-create`, `duh user-list`.
- Export: `duh export <id> --format pdf/markdown --content full/decision --no-dissent -o file`
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
