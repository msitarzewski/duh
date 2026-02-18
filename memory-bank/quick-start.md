# Quick Start — Session Entry Point

**Last Updated**: 2026-02-17

---

## Where We Are

**v0.5 COMPLETE** — "It Scales". Multi-user auth, PostgreSQL, production hardening.

- 1354 Python tests + 12 load tests + 117 Vitest tests (1483 total), ~60 Python + 66 frontend source files
- 6 providers (Anthropic, OpenAI, Google, Mistral, Perplexity, local via Ollama) — 17 models
- Version 0.5.0, branch `v0.5.0`, ready to merge to main
- MkDocs docs live at https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh

## Starting a Session

Load these files:
1. `activeContext.md` — current state, v0.5 complete, open questions
2. `roadmap.md:513+` — v1.0 spec (next version)
3. `techContext.md` — tech stack + all decided patterns (Python + frontend)
4. `decisions.md` — 18 ADRs, all foundational + v0.2 + v0.3 + v0.4 decisions

## Project Commands

```bash
# CLI
duh ask "question"                         # standard consensus
duh ask "question" --decompose             # decompose into subtasks
duh ask "question" --protocol voting       # voting protocol
duh ask "question" --protocol auto         # auto-classify task type
duh ask "question" --tools                 # tool-augmented reasoning
duh feedback <thread_id> --result good     # record outcome
duh recall "query"                         # search past decisions
duh threads                                # list threads
duh show <thread_id>                       # show thread details
duh models                                 # list available models
duh cost                                   # show cost summary
duh serve                                  # start REST API + web UI
duh serve --reload                         # dev mode with hot reload
duh mcp                                    # start MCP server
duh batch questions.txt                    # batch mode
duh export <thread_id> --format json       # export thread
duh backup /path/to/backup.json           # backup database
duh restore /path/to/backup.json          # restore database
duh user-create                           # create user account
duh user-list                             # list users

# Backend Development
uv sync                                    # install deps
uv run pytest tests/ -v                    # run all tests
uv run mypy src/duh/                       # type check
uv run ruff check --fix src/ tests/        # lint + fix
uv run ruff format src/ tests/             # format
uv run alembic upgrade head                # run migrations

# Frontend Development
cd web && npm ci                           # install deps
cd web && npm run dev                      # Vite dev server (:3000, proxies to :8080)
cd web && npm run build                    # production build to dist/
cd web && npm test                         # run Vitest tests
cd web && npx tsc --noEmit                 # TypeScript check

# Docker
docker compose up                          # full stack on :8080
```

## Key Files

| Area | Files |
|------|-------|
| CLI | `src/duh/cli/app.py`, `src/duh/cli/display.py` |
| Consensus | `src/duh/consensus/machine.py`, `src/duh/consensus/handlers.py` |
| Voting | `src/duh/consensus/voting.py`, `src/duh/consensus/classifier.py` |
| Decomposition | `src/duh/consensus/decompose.py`, `src/duh/consensus/scheduler.py`, `src/duh/consensus/synthesis.py` |
| Tools | `src/duh/tools/base.py`, `src/duh/tools/registry.py`, `src/duh/tools/augmented_send.py` |
| Tool impls | `src/duh/tools/web_search.py`, `src/duh/tools/code_exec.py`, `src/duh/tools/file_read.py` |
| Providers | `src/duh/providers/base.py`, `anthropic.py`, `openai.py`, `google.py`, `mistral.py`, `perplexity.py` |
| Memory | `src/duh/memory/models.py`, `repository.py`, `context.py`, `summary.py` |
| Config | `src/duh/config/schema.py`, `src/duh/config/loader.py` |
| Core | `src/duh/core/errors.py`, `src/duh/core/retry.py` |
| REST API | `src/duh/api/app.py`, `src/duh/api/middleware.py`, `src/duh/api/routes/` |
| Auth/RBAC | `src/duh/api/auth.py`, `src/duh/api/rbac.py` |
| Monitoring | `src/duh/api/metrics.py`, `src/duh/api/health.py` |
| Backup | `src/duh/memory/backup.py` |
| MCP Server | `src/duh/mcp/server.py` |
| Client | `client/src/duh_client/client.py` |
| Migrations | `alembic/versions/001_v01_baseline.py` through `005_v05_users.py` |
| Frontend theme | `web/src/theme/duh-theme.css` (22 CSS vars, dark/light), `web/src/theme/animations.css` (keyframes + `.duh-prose`) |
| Markdown | `web/src/components/shared/Markdown.tsx` (react-markdown + highlight.js + mermaid lazy) |
| Frontend API | `web/src/api/client.ts`, `web/src/api/websocket.ts`, `web/src/api/types.ts` |
| Frontend stores | `web/src/stores/consensus.ts`, `threads.ts`, `decision-space.ts`, `preferences.ts` |
| Consensus UI | `web/src/components/consensus/ConsensusPanel.tsx`, `QuestionInput.tsx`, `PhaseCard.tsx`, `StreamingText.tsx` |
| Threads UI | `web/src/components/threads/ThreadBrowser.tsx`, `ThreadDetail.tsx` |
| Decision Space | `web/src/components/decision-space/DecisionSpace.tsx`, `Scene3D.tsx`, `DecisionCloud.tsx` |
| Layout | `web/src/components/layout/Shell.tsx`, `Sidebar.tsx`, `TopBar.tsx` |
| Shared | `web/src/components/shared/GlassPanel.tsx`, `GlowButton.tsx`, `Badge.tsx`, `PageTransition.tsx`, `Markdown.tsx` |
| Pages | `web/src/pages/ConsensusPage.tsx`, `ThreadsPage.tsx`, `DecisionSpacePage.tsx`, `PreferencesPage.tsx` |
| Vitest config | `web/vitest.config.ts`, `web/src/test-setup.ts` |
| Frontend tests | `web/src/__tests__/shared-components.test.tsx`, `stores.test.ts`, `api-client.test.ts`, `websocket.test.ts`, `consensus-components.test.tsx` |

### Key Architecture Patterns

- **Provider adapter**: `src/duh/providers/openai.py` — template for new adapters
- **CLI command**: `src/duh/cli/app.py` — Click commands, async wrappers
- **Config schema**: `src/duh/config/schema.py` — Pydantic models with defaults
- **Repository**: `src/duh/memory/repository.py` — async CRUD, flush-not-commit
- **Consensus loop**: `src/duh/cli/app.py` — `_run_consensus()` reusable for REST
- **REST route**: `src/duh/api/routes/ask.py` — FastAPI endpoint wrapping consensus
- **MCP tool**: `src/duh/mcp/server.py` — direct Python calls, no REST dependency
- **Frontend component**: `web/src/components/shared/GlassPanel.tsx` — glassmorphism pattern
- **Zustand store**: `web/src/stores/consensus.ts` — WebSocket-driven state machine
- **3D visualization**: `web/src/components/decision-space/DecisionCloud.tsx` — InstancedMesh point cloud
