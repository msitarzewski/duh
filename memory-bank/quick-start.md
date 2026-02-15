# Quick Start — Session Entry Point

**Last Updated**: 2026-02-15

---

## Where We Are

Phase 0 **COMPLETE — exit decision PROCEED**. Thesis validated: multi-model consensus beats single-model answers.

Benchmark results: 17 questions, consensus wins head-to-head vs direct (47-88% depending on judge), beats self-debate 76.5%. Total cost $7.19. Full results in `results/analysis/`.

**Now starting v0.1.**

## Starting v0.1

Load these files:
1. `activeContext.md` — has v0.1 task order and Phase 0 artifacts that feed forward
2. `roadmap.md:126-266` — v0.1 spec, acceptance criteria, 24 tasks with dependency graph
3. `roadmap.md:486-535` — testing mandate (non-negotiable)
4. `roadmap.md:592-621` — project structure and provider interface
5. `techContext.md` — tech stack
6. `decisions.md` — 11 ADRs, all foundational decisions documented

### v0.1 First Tasks

1. **Project scaffolding**: `src/duh/` layout, pytest + pytest-asyncio + pytest-cov + ruff + mypy, CI pipeline, Docker skeleton
2. **Provider adapter interface**: `ModelProvider` protocol, `ModelInfo`, `ModelResponse`, `StreamChunk`, `TokenUsage` data classes
3. **Mock provider + test fixtures**: `MockProvider` with deterministic responses, canned response library, in-memory DB fixture

These three are the foundation — everything else depends on them.

### Key Patterns From Phase 0 to Reuse

- `phase0/models.py` — async client pattern, retry with backoff, normalized response
- `phase0/prompts.py` — forced disagreement challenger prompt (seed for consensus challenge framings)
- `phase0/config.py` — Pydantic config, cost tracking per model
- `phase0/questions.json` — reusable as sycophancy test corpus

### Things NOT to Carry Forward From Phase 0

- Phase 0 is a benchmark script, not product code. Don't extend it — build v0.1 from scratch following `src/duh/` layout.
- Phase 0's `ModelClient` is a monolith. v0.1 uses per-provider adapters behind a `Protocol`.
- Phase 0 has no tests. v0.1 has test-alongside mandate from task 1.

## Project Commands

```bash
# Phase 0 (already built)
uv run python -m phase0.runner --pilot --budget small   # cheap iteration
uv run python -m phase0.runner --budget full             # real benchmark
uv run python -m phase0.judge --budget full              # judge results
uv run python -m phase0.analyze                          # generate report

# Dependencies
uv sync                                                  # install deps
```
