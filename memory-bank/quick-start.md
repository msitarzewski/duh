# Quick Start — Session Entry Point

**Last Updated**: 2026-02-16

---

## Where We Are

**v0.3 COMPLETE** — "It's Accessible". REST API, MCP server, Python client, Mistral adapter — all shipped.

- 1318 tests, 50 source files, 5 providers (Anthropic, OpenAI, Google, Mistral, local via Ollama)
- Version 0.3.0, branch `v0.3.0` ready to merge to main
- MkDocs docs live at https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh

## Starting a Session

Load these files:
1. `activeContext.md` — current state, v0.3 summary, open questions
2. `roadmap.md:330+` — future version specs
3. `techContext.md` — tech stack + all decided patterns
4. `decisions.md` — 15 ADRs, all foundational + v0.2 decisions

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

## Key Files

| Area | Files |
|------|-------|
| CLI | `src/duh/cli/app.py`, `src/duh/cli/display.py` |
| Consensus | `src/duh/consensus/machine.py`, `src/duh/consensus/handlers.py` |
| Voting | `src/duh/consensus/voting.py`, `src/duh/consensus/classifier.py` |
| Decomposition | `src/duh/consensus/decompose.py`, `src/duh/consensus/scheduler.py`, `src/duh/consensus/synthesis.py` |
| Tools | `src/duh/tools/base.py`, `src/duh/tools/registry.py`, `src/duh/tools/augmented_send.py` |
| Tool impls | `src/duh/tools/web_search.py`, `src/duh/tools/code_exec.py`, `src/duh/tools/file_read.py` |
| Providers | `src/duh/providers/base.py`, `anthropic.py`, `openai.py`, `google.py`, `mistral.py` |
| Memory | `src/duh/memory/models.py`, `repository.py`, `context.py`, `summary.py` |
| Config | `src/duh/config/schema.py`, `src/duh/config/loader.py` |
| Core | `src/duh/core/errors.py`, `src/duh/core/retry.py` |
| REST API | `src/duh/api/app.py`, `src/duh/api/middleware.py`, `src/duh/api/routes/` |
| MCP Server | `src/duh/mcp/server.py` |
| Client | `client/src/duh_client/client.py` |
| Migrations | `alembic/versions/001_v01_baseline.py`, `002_v02_schema.py`, `003_v02_votes.py`, `004_v03_api_keys.py` |

### Key Architecture Patterns

- **Provider adapter**: `src/duh/providers/openai.py` — template for new adapters
- **CLI command**: `src/duh/cli/app.py` — Click commands, async wrappers
- **Config schema**: `src/duh/config/schema.py` — Pydantic models with defaults
- **Repository**: `src/duh/memory/repository.py` — async CRUD, flush-not-commit
- **Consensus loop**: `src/duh/cli/app.py` — `_run_consensus()` reusable for REST
- **REST route**: `src/duh/api/routes/ask.py` — FastAPI endpoint wrapping consensus
- **MCP tool**: `src/duh/mcp/server.py` — direct Python calls, no REST dependency
