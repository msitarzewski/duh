# Progress

**Last Updated**: 2026-02-17

---

## Current State: v0.4 COMPLETE — Web UI with 3D Decision Space

### v0.4 Additions

- React 19 + Vite 6 + Tailwind 4 + TypeScript frontend (66 source files)
- 3D Decision Space: Three.js point cloud (R3F + drei), lazy-loaded, code-split (873KB)
- Real-time WebSocket consensus streaming in browser
- Thread browser with search, filtering, pagination
- Preferences panel (rounds, protocol, cost threshold)
- Glassmorphism design system with CSS custom properties, 9+ animation keyframes
- Page transitions, micro-interactions, ConfidenceMeter animation
- Mobile-responsive with 2D SVG scatter fallback
- 117 Vitest tests (shared components, stores, API client, WebSocket, consensus components)
- Backend: /api/decisions/space endpoint, /api/share/{token}, static file serving + SPA fallback
- Docker: multi-stage build with Node.js 22 frontend stage
- Docs: web-ui.md, web-quickstart.md, updated mkdocs.yml
- Version 0.4.0 across pyproject.toml, __init__.py, api/app.py

### v0.3 Additions (Previously Shipped)

### What's Built

Phase 0 benchmark framework — fully functional, pilot-tested on 5 questions.

**Files** (`phase0/`):
- `config.py` — Pydantic config, budget presets (`--budget small|full`), cost tracking with per-model pricing
- `models.py` — Async `ModelClient` wrapping `anthropic.AsyncAnthropic` + `openai.AsyncOpenAI`, retries with backoff, normalized `ModelResponse`
- `prompts.py` — All prompt templates with date grounding injected into every system prompt. Forced disagreement challenger, self-debate critic, ensemble synthesizer, blind judge
- `methods.py` — 4 benchmark methods: Direct (A), Self-Debate (B), Consensus (C), Ensemble (D)
- `questions.py` — Question loader with pilot selection (one per category)
- `questions.json` — 50 benchmark questions across 5 categories (15 judgment/strategy, 10 risk, 10 factual reasoning, 10 creative, 5 adversarial)
- `runner.py` — Orchestrator with checkpointing (resume from interrupts), Rich progress display, `--pilot`/`--budget` flags
- `judge.py` — Blind LLM-as-judge: randomized answer order, 2 independent judges, JSON structured output, `--budget` flag
- `analyze.py` — Win rates, head-to-head, per-category breakdown, dimension scores, inter-judge agreement, cost summary, auto exit decision

**Project root**:
- `pyproject.toml` — `uv`-managed, deps: anthropic, openai, pydantic, pydantic-settings, rich
- `.gitignore` — Python, .env, results/
- `README.md` — Setup + usage

### Pilot Run Results

- 5 questions (one per category), `--budget small` (Sonnet + GPT-4o)
- 55 API calls, 168,862 tokens, $1.64, ~31 minutes
- Runner checkpointing works, progress display clean (httpx logs suppressed)
- First results looked promising — user said "The first test was amazing"

### Budget Presets

| Preset | Claude Model | GPT Model | Est. Pilot Cost | Est. Full Cost |
|--------|-------------|-----------|-----------------|----------------|
| `small` | Sonnet 4.5 | GPT-4o | ~$2 | ~$15 |
| `full` | Opus 4.6 | GPT-5.2 | ~$10 | ~$60 |

### Benchmark Results

- 17 questions evaluated (partial 50-question run, stopped early — sufficient signal)
- Methods run with `--budget full` (Opus 4.6 + GPT-5.2), judging with `--budget small` (Sonnet + GPT-4o)
- **Consensus beats Direct** head-to-head: 47% vs 41% (GPT judge), 88% vs 6% (Opus judge)
- **Consensus beats Self-Debate**: 76.5% wins — cross-model challenge > self-critique
- Consensus higher on all dimensions: accuracy, completeness, nuance, specificity, overall
- Total cost: $7.19 (methods $6.01 + judging $1.17)
- **Exit decision: PROCEED**

---

## Milestone History

| Date | Milestone | Status |
|------|-----------|--------|
| 2026-02-15 | Memory bank + roadmap created by 4-agent team | Done |
| 2026-02-15 | Phase 0 implementation complete | Done |
| 2026-02-15 | Pilot run successful (5 Qs, small budget) | Done |
| 2026-02-15 | Benchmark run (17 Qs) + exit decision: PROCEED | Done |
| 2026-02-15 | v0.1 Task 1: Project scaffolding | Done |
| 2026-02-15 | v0.1 Task 2: Core error hierarchy | Done |
| 2026-02-15 | v0.1 Task 3: Provider adapter interface | Done |
| 2026-02-15 | v0.1 Task 4: Configuration | Done |
| 2026-02-15 | v0.1 Task 5: Mock provider + test fixtures | Done |
| 2026-02-15 | v0.1 Task 6: Anthropic adapter | Done |
| 2026-02-15 | v0.1 Task 7: OpenAI adapter (GPT + Ollama) | Done |
| 2026-02-15 | v0.1 Task 8: Retry with backoff utility | Done |
| 2026-02-16 | v0.1 Tasks 9-25: Full implementation + docs | Done |
| 2026-02-16 | v0.1.0 — "It Works & Remembers" | **Complete** |
| 2026-02-16 | Google Gemini adapter (Gemini 3 + 2.5) | Done |
| 2026-02-16 | MkDocs site + GitHub Pages deployment | Done |
| 2026-02-16 | GitHub repo created: msitarzewski/duh | Done |
| 2026-02-16 | v0.2 T1-T7 (Phase 1: Foundation) — Alembic migrations, structured output, JSON extract, challenge framings, tool framework, tool-augmented send, config schema | Done |
| 2026-02-16 | v0.2 T8-T12 (Phase 2: Taxonomy + Outcomes) — models/repo, taxonomy at COMMIT, feedback CLI, outcome context, display | Done |
| 2026-02-16 | v0.2 T13-T15 (Phase 3: Decomposition) — DECOMPOSE state + handler, scheduler, synthesis | Done |
| 2026-02-16 | v0.2 T16-T17 (Phase 4: Voting + Decompose CLI) — voting + classifier, decompose CLI integration | Done |
| 2026-02-16 | v0.2 T18-T22 (Phase 5: Tools + Voting CLI) — voting CLI, tool implementations, provider tool parsing, tool handler integration, tool CLI setup | Done |
| 2026-02-16 | v0.2 Phase 6 — Integration tests, README, version bump to 0.2.0 | Done |
| 2026-02-16 | v0.2.0 — "It Thinks Deeper" | **Complete** |
| 2026-02-16 | Subtask progress display (decompose scheduler) | Done |
| 2026-02-16 | v0.3 task breakdown planned (17 tasks, 7 phases) | Done |
| 2026-02-16 | v0.3.0 branch created from main | Done |
| 2026-02-16 | v0.3 T1-T3 (Phase 1: Foundation) — Mistral adapter, export CLI, batch mode CLI | Done |
| 2026-02-16 | v0.3 T4-T7 (Phase 2: API Core) — API config, FastAPI app, API keys, auth middleware | Done |
| 2026-02-16 | v0.3 T8-T10 (Phase 3: REST Endpoints) — /api/ask, /api/threads, /api/recall+more | Done |
| 2026-02-16 | v0.3 T11 (Phase 4: Streaming) — WebSocket /ws/ask | Done |
| 2026-02-16 | v0.3 T12 (Phase 5: MCP) — MCP server (duh_ask, duh_recall, duh_threads) | Done |
| 2026-02-16 | v0.3 T13 (Phase 6: Client) — Python client library (duh-client) | Done |
| 2026-02-16 | v0.3 T14-T17 (Phase 7: Ship) — Integration tests, docs, version bump | Done |
| 2026-02-16 | v0.3.0 — "It's Accessible" | **Complete** |
| 2026-02-17 | v0.4 Web UI scaffolding (React 19 + Vite 6 + Tailwind 4 + TS) | Done |
| 2026-02-17 | v0.4 Design system (CSS vars, glassmorphism, animations) | Done |
| 2026-02-17 | v0.4 API client + TypeScript types + Zustand stores | Done |
| 2026-02-17 | v0.4 Layout shell + routing (6 pages) | Done |
| 2026-02-17 | v0.4 Consensus page + WebSocket streaming | Done |
| 2026-02-17 | v0.4 Thread browser + thread detail pages | Done |
| 2026-02-17 | v0.4 3D Decision Space (Three.js/R3F, InstancedMesh, code-split) | Done |
| 2026-02-17 | v0.4 Decision Space interaction + mobile 2D fallback | Done |
| 2026-02-17 | v0.4 Share links + preferences page | Done |
| 2026-02-17 | v0.4 Backend: /api/decisions/space, /api/share, static serving | Done |
| 2026-02-17 | v0.4 Docker multi-stage with Node.js 22 frontend build | Done |
| 2026-02-17 | v0.4 Animations + micro-interactions + polish | Done |
| 2026-02-17 | v0.4 117 Vitest tests (5 test files) | Done |
| 2026-02-17 | v0.4 MkDocs documentation (web-ui.md, web-quickstart.md) | Done |
| 2026-02-17 | v0.4 Version bump to 0.4.0 | Done |
| 2026-02-17 | v0.4.0 — "It Has a Face" | **Complete** |
