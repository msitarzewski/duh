# Active Context

**Last Updated**: 2026-02-16
**Current Phase**: v0.1 in progress.
**Next Action**: v0.1 task 25 — Documentation.

---

## Current State

- **v0.1 Tasks 1-24 COMPLETE.** Through Docker.
- 681 tests passing, ruff clean, mypy strict clean (25 source files).
- Next: task 25 (Documentation) — final v0.1 task.

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

### v0.1 Task Order (revised — error hierarchy and config moved earlier)

1. ~~Project scaffolding~~ DONE
2. ~~Core error hierarchy + base types~~ DONE
3. ~~Provider adapter interface + data classes~~ DONE
4. ~~Configuration (TOML + Pydantic)~~ DONE
5. ~~Mock provider + test fixtures~~ DONE
6. ~~Anthropic adapter~~ DONE
7. ~~OpenAI adapter (GPT + Ollama via base_url)~~ DONE
8. ~~Retry with backoff utility~~ DONE
9. ~~Provider manager~~ DONE
10. ~~SQLAlchemy models~~ DONE
11. ~~Memory repository~~ DONE
12. ~~Consensus state machine~~ DONE
13. ~~PROPOSE handler~~ DONE
14. ~~CHALLENGE handler~~ DONE
15. ~~REVISE handler~~ DONE
16. ~~COMMIT handler~~ DONE
17. ~~Convergence detection~~ DONE
18. ~~Context builder~~ DONE
19. ~~Summary generator~~ DONE
20. ~~Integration tests (full loop with mock providers)~~ DONE
21. ~~Sycophancy test suite~~ DONE
22. ~~CLI app~~ DONE (Click commands)
23. ~~CLI display (Rich Live panels)~~ DONE
24. ~~Docker~~ DONE
25. Documentation

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
