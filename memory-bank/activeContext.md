# Active Context

**Last Updated**: 2026-02-16
**Current Phase**: v0.2 COMPLETE. Preparing v0.3.
**Next Action**: Plan v0.3 task breakdown (REST API, MCP server, Python client).

---

## Current State

- **v0.2 Tasks 1-22 COMPLETE.** All tasks including integration tests, docs, version bump.
- **4 providers shipping**: Anthropic (3 models), OpenAI (3 models), Google (4 models) — 10 total.
- 1093 tests passing, ruff clean, mypy strict clean (39 source files, 4 providers).
- MkDocs docs site live at https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh

### v0.2 Features

- **Voting protocol** — `duh ask --protocol voting|consensus|auto`, parallel fan-out + majority/weighted aggregation
- **Decomposition** — `duh ask --decompose`, DECOMPOSE state, topological scheduler, synthesis
- **Tool-augmented reasoning** — `duh ask --tools`, web search, code execution, file read
- **Decision taxonomy** — automatic classification at COMMIT time via lightweight model call
- **Outcome tracking** — `duh feedback <thread_id> --result --notes`, outcome context in future rounds
- **Feedback CLI** — record real-world outcomes for knowledge accumulation

## Phase 0 Benchmark Results (Summary)

- **Consensus vs Direct (head-to-head)**: 47% vs 41% (GPT judge), 88% vs 6% (Opus judge) — consensus wins
- **Consensus vs Self-Debate**: 76.5% wins (GPT), 52.9% wins (Opus) — cross-model challenge beats self-critique
- **Dimension scores**: Consensus higher than Direct on all 5 dimensions (accuracy 8.06 vs 7.53, completeness 8.41 vs 7.65, nuance 8.12 vs 7.24, specificity 8.41 vs 7.71, overall 8.06 vs 7.53)
- **Ensemble** scored slightly higher than Consensus but costs 50% more ($2.34 vs $1.57) and lacks dissent reasoning
- **Auto-decision said ITERATE** (33% win rate on J/S, below 60% threshold) but that metric measures "ranked #1 out of 4 methods" — head-to-head clearly favors consensus
- **Manual decision: PROCEED** — the method works, prompts will improve in v0.1

## v0.1 Task List (ALL DONE)

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
25. ~~Documentation~~ DONE
26. ~~Google Gemini adapter~~ DONE (added post-v0.1, 22 tests)

## v0.2 Task List (ALL DONE)

1. ~~Alembic migrations (001 baseline, 002 v0.2 schema)~~ DONE
2. ~~Structured output (response_format, tools, tool_calls on providers)~~ DONE
3. ~~JSON extract~~ DONE
4. ~~Challenge framings (4 types, round-robin)~~ DONE
5. ~~Tool framework (Tool protocol, ToolRegistry)~~ DONE
6. ~~Tool-augmented send~~ DONE
7. ~~Config schema (ToolsConfig, VotingConfig, DecomposeConfig, TaxonomyConfig)~~ DONE
8. ~~Models + repo (Outcome, Subtask, Vote, taxonomy fields)~~ DONE
9. ~~Taxonomy at COMMIT~~ DONE
10. ~~Feedback CLI~~ DONE
11. ~~Outcome context~~ DONE
12. ~~Display (show_taxonomy, show_outcome)~~ DONE
13. ~~DECOMPOSE state + handler~~ DONE
14. ~~Scheduler (TopologicalSorter)~~ DONE
15. ~~Synthesis~~ DONE
16. ~~Decomposition CLI integration~~ DONE
17. ~~Voting + classifier~~ DONE
18. ~~Voting CLI + persistence + display~~ DONE
19. ~~Tool implementations (web_search, code_exec, file_read)~~ DONE
20. ~~Provider tool call parsing~~ DONE
21. ~~Tool integration in handlers~~ DONE
22. ~~Tool CLI setup~~ DONE
23. ~~Integration tests (Phase 6)~~ DONE
24. ~~README + docs update~~ DONE
25. ~~Version bump to 0.2.0~~ DONE

## Ready for v0.3

Key references:
- **v0.3 scope**: REST API, MCP server, Python client library
- **Tech stack**: `techContext.md` — FastAPI (likely), MCP SDK
- **Architecture**: `decisions.md` — all foundational decisions documented
- **Patterns**: Handler pattern, Tool protocol, provider adapter pattern all established in v0.1/v0.2

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
- ~~Whether DECOMPOSE should itself be a consensus operation~~ RESOLVED: No, decomposition is single-model (simpler, sufficient)
- ~~Testing framework~~ RESOLVED: pytest + pytest-asyncio, asyncio_mode=auto
