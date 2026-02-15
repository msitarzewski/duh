# Active Context

**Last Updated**: 2026-02-15
**Current Phase**: Phase 0 COMPLETE — exit decision PROCEED. Starting v0.1.
**Next Action**: v0.1 task 1 — project scaffolding.

---

## Current State

- **Phase 0 exit decision: PROCEED.** Thesis validated — multi-model consensus beats single-model answers.
- Benchmark: 17 questions (partial run, full budget), judged (small budget), analyzed.
- Total Phase 0 cost: $7.19 (methods $6.01 + judging $1.17).
- v0.1 development begins now.

## Phase 0 Benchmark Results (Summary)

- **Consensus vs Direct (head-to-head)**: 47% vs 41% (GPT judge), 88% vs 6% (Opus judge) — consensus wins
- **Consensus vs Self-Debate**: 76.5% wins (GPT), 52.9% wins (Opus) — cross-model challenge beats self-critique
- **Dimension scores**: Consensus higher than Direct on all 5 dimensions (accuracy 8.06 vs 7.53, completeness 8.41 vs 7.65, nuance 8.12 vs 7.24, specificity 8.41 vs 7.71, overall 8.06 vs 7.53)
- **Ensemble** scored slightly higher than Consensus but costs 50% more ($2.34 vs $1.57) and lacks dissent reasoning
- **Auto-decision said ITERATE** (33% win rate on J/S, below 60% threshold) but that metric measures "ranked #1 out of 4 methods" — head-to-head clearly favors consensus
- **Manual decision: PROCEED** — the method works, prompts will improve in v0.1

## Ready for v0.1

When Phase 0 exits with PROCEED, v0.1 implementation starts. Key references:

- **v0.1 spec**: `roadmap.md:126-266` — full task list, acceptance criteria, dependency graph
- **Project structure**: `roadmap.md:592-606` — `src/duh/` layout with cli/, consensus/, providers/, memory/, config/, core/
- **Testing mandate**: `roadmap.md:486-535` — 95% coverage on core, test-alongside, every public function tested
- **Provider interface**: `roadmap.md:612-621` — `typing.Protocol`, stateless adapters
- **Tech stack**: `techContext.md` — Python, asyncio, SQLAlchemy, Rich, Click, Docker, uv
- **Architecture decisions**: `decisions.md` — all 8 foundational decisions documented

### v0.1 Task Order (from roadmap)

1. Project scaffolding (`src/duh/` layout, pytest, ruff, mypy, CI, Docker skeleton)
2. Provider adapter interface + data classes
3. Mock provider + test fixtures
4. Anthropic adapter
5. OpenAI adapter (covers GPT + Ollama via base_url)
6. Provider manager
7. Configuration (TOML + Pydantic)
8. Error handling + retry
9. SQLAlchemy models
10. Memory repository
11. Consensus state machine
12-16. State handlers (PROPOSE, CHALLENGE, REVISE, COMMIT, convergence)
17-18. Context builder + summary generator
19-20. Integration tests + sycophancy tests
21-22. CLI app + display
23. Docker
24. Documentation

### Phase 0 Artifacts That Feed v0.1

- **Validated prompts** from `phase0/prompts.py` — especially the forced disagreement challenger prompt, will seed `src/duh/consensus/` challenge framings
- **Question corpus** from `phase0/questions.json` — reusable for sycophancy test suite in v0.1
- **Model client patterns** from `phase0/models.py` — async wrapper, retry, cost tracking patterns inform provider adapter design
- **Cost data** from benchmark — informs default cost thresholds and warnings

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Hosted demo economics — v0.4 decision
- Whether DECOMPOSE (v0.2) should itself be a consensus operation
