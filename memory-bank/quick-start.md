# Quick Start — Session Entry Point

**Last Updated**: 2026-02-16

---

## Where We Are

**v0.3 IN PROGRESS** — "It's Accessible". REST API, MCP server, Python client, Mistral adapter.

- 1093 tests, 39 source files, 4 providers (Anthropic, OpenAI, Google, local via Ollama)
- Version 0.2.0 shipping, v0.3 branch active
- MkDocs docs live at https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh
- Branch: `v0.3.0`

## Starting a v0.3 Session

Load these files:
1. `activeContext.md` — v0.3 task list (17 tasks, 7 phases), dependency graph, architecture decisions
2. `roadmap.md:330+` — v0.3 spec (REST API, MCP server, Python client)
3. `techContext.md` — tech stack + v0.2 additions + v0.3 new deps
4. `decisions.md` — 15 ADRs, all foundational + v0.2 decisions

### v0.3 Task Phases

| Phase | Tasks | Status |
|-------|-------|--------|
| Phase 1: Foundation | T1 Mistral, T2 Export, T3 Batch | Pending |
| Phase 2: API Core | T4 Config, T5 FastAPI, T6 API Keys, T7 Auth | Pending |
| Phase 3: REST Endpoints | T8 /ask, T9 /threads, T10 /recall+more | Pending |
| Phase 4: Streaming | T11 WebSocket | Pending |
| Phase 5: MCP | T12 MCP Server | Pending |
| Phase 6: Client | T13 duh-client | Pending |
| Phase 7: Ship | T14 Integration tests, T15 Docs, T17 Version bump | Pending |

### Key Architecture Patterns to Follow

- **Provider adapter**: `src/duh/providers/openai.py` — template for Mistral adapter
- **CLI command**: `src/duh/cli/app.py` — Click commands, async wrappers
- **Config schema**: `src/duh/config/schema.py` — Pydantic models with defaults
- **Repository**: `src/duh/memory/repository.py` — async CRUD, flush-not-commit
- **Consensus loop**: `src/duh/cli/app.py:150-252` — `_run_consensus()` reusable for REST

## Project Commands

```bash
# v0.2 CLI (current)
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

# v0.3 CLI (planned)
duh serve                                  # start REST API server
duh mcp                                    # start MCP server
duh batch questions.txt                    # batch mode
duh export <thread_id> --format json       # export thread

# Development
uv sync                                    # install deps
uv run pytest tests/ -v                    # run all tests
uv run mypy src/duh/                       # type check
uv run ruff check --fix src/ tests/        # lint + fix
uv run ruff format src/ tests/             # format
uv run alembic upgrade head                # run migrations
```

## Key Files (v0.2 — extend for v0.3)

| Area | Files |
|------|-------|
| CLI | `src/duh/cli/app.py`, `src/duh/cli/display.py` |
| Consensus | `src/duh/consensus/machine.py`, `src/duh/consensus/handlers.py` |
| Voting | `src/duh/consensus/voting.py`, `src/duh/consensus/classifier.py` |
| Decomposition | `src/duh/consensus/decompose.py`, `src/duh/consensus/scheduler.py`, `src/duh/consensus/synthesis.py` |
| Tools | `src/duh/tools/base.py`, `src/duh/tools/registry.py`, `src/duh/tools/augmented_send.py` |
| Tool impls | `src/duh/tools/web_search.py`, `src/duh/tools/code_exec.py`, `src/duh/tools/file_read.py` |
| Providers | `src/duh/providers/base.py`, `src/duh/providers/anthropic.py`, `src/duh/providers/openai.py`, `src/duh/providers/google.py` |
| Memory | `src/duh/memory/models.py`, `src/duh/memory/repository.py`, `src/duh/memory/context.py`, `src/duh/memory/summary.py` |
| Config | `src/duh/config/schema.py`, `src/duh/config/loader.py` |
| Core | `src/duh/core/errors.py`, `src/duh/core/retry.py` |
| Migrations | `alembic/versions/001_v01_baseline.py`, `002_v02_schema.py`, `003_v02_votes.py` |

### v0.3 New File Areas

| Area | Files (planned) |
|------|-------|
| REST API | `src/duh/api/app.py`, `src/duh/api/routes/`, `src/duh/api/middleware.py` |
| MCP Server | `src/duh/mcp/server.py` |
| Mistral | `src/duh/providers/mistral.py` |
| Client | `client/` or `src/duh_client/` |
