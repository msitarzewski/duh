# Quick Start — Session Entry Point

**Last Updated**: 2026-02-16

---

## Where We Are

**v0.2 COMPLETE** — Voting, decomposition, tool-augmented reasoning, taxonomy, outcome tracking all shipped.

- 1093 tests, 39 source files, 4 providers (Anthropic, OpenAI, Google, local via Ollama)
- Version 0.2.0, mypy strict clean, ruff clean
- MkDocs docs live at https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh

## Starting v0.3

Load these files:
1. `activeContext.md` — current state, v0.2 feature list, open questions
2. `roadmap.md:267+` — v0.3 spec (REST API, MCP server, Python client)
3. `techContext.md` — tech stack + v0.2 additions
4. `decisions.md` — 15 ADRs, all foundational + v0.2 decisions documented
5. `progress.md` — milestone history through v0.2

### v0.3 Likely Scope

- REST API (FastAPI)
- MCP server
- Python client library
- Possibly: WebSocket streaming, API auth

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

# Development
uv sync                                    # install deps
uv run pytest tests/ -v                    # run all tests
uv run mypy src/duh/                       # type check
uv run ruff check --fix src/ tests/        # lint + fix
uv run ruff format src/ tests/             # format
uv run alembic upgrade head                # run migrations

# Phase 0 (benchmark — already built)
uv run python -m phase0.runner --pilot --budget small
uv run python -m phase0.runner --budget full
uv run python -m phase0.judge --budget full
uv run python -m phase0.analyze
```

## Key Files (v0.2)

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

### Key Patterns From Phase 0 to Reuse

- `phase0/models.py` — async client pattern, retry with backoff, normalized response
- `phase0/prompts.py` — forced disagreement challenger prompt (seed for consensus challenge framings)
- `phase0/config.py` — Pydantic config, cost tracking per model
- `phase0/questions.json` — reusable as sycophancy test corpus

### Things NOT to Carry Forward From Phase 0

- Phase 0 is a benchmark script, not product code. Don't extend it — build from `src/duh/` layout.
- Phase 0's `ModelClient` is a monolith. v0.1+ uses per-provider adapters behind a `Protocol`.
- Phase 0 has no tests. v0.1+ has test-alongside mandate.
