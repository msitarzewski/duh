# Progress

**Last Updated**: 2026-06-22

---

## Current State (2026-06-22): Catalog, Persistence, Cloudflare/GLM, Unified Report

Merged to `main` via PRs #16–#21 (details in `tasks/2026-06/README.md` and `activeContext.md`):
- **Model catalog refresh** + propose-only `scripts/refresh_catalog.py` drift tool; OpenAI + Anthropic
  temperature correctness (`NO_TEMPERATURE_MODELS`, `ANTHROPIC_NO_TEMPERATURE_MODELS`)
- **Incremental persistence** (`IncrementalPersister`) across CLI/WS/REST — mid-run crash leaves a real partial thread
- **Cloudflare Workers AI provider** with Zhipu GLM-5.2; `OpenAIProvider` generalized to any OpenAI-compatible host
- **Unified `ConsensusReport`** for live + history; history now shows the executive summary
- **Temperature self-heal**: providers retry once without temperature on a temperature-related 400
  and learn the model (`src/duh/providers/temperature.py`) — cross-provider safety net, live-verified
- **Prior (2026-06-21)**: token usage tracking end-to-end + `npm/like-duh` wrapper
- **Tests**: 1681 Python + 204 Vitest, mypy clean (64 files), ruff clean, build clean
- **No open follow-ups outstanding from this session** (temperature retry + tsbuildinfo both done)

---

## Prior State: Thread View Parity + PDF Overhaul + Server Fixes

### Thread View Parity + PDF Overhaul + Server/UI Fixes (2026-03-20)

- **Thread detail view**: replaced `TurnCard` with `PhaseCard` rendering — PROPOSE/CHALLENGE/REVISE phases match live consensus view
  - `turnToPhaseData()` transforms `Turn.contributions` by role into PhaseCard props
  - `ThreadNav` upgraded to phase-level navigation (PROPOSE, individual challenger models, REVISE)
  - Feedback section moved to top (right after decision)
- **PDF export overhaul**: branded cover page ("duh." + "consensus engine"), quoted question, styled TOC with dot leaders + clickable page links
  - Colored section header bars (Decision=green, Dissent=amber, Consensus Process=gray)
  - Phase-grouped contributions with accent colors per phase
  - Confidence/rigor labeled progress bars
  - Consolidated Sources section at end with numbered clickable URLs
  - TOC on dedicated page to prevent fpdf2 overflow error
- **Server fix**: `create_all` for fresh file-based SQLite before `ensure_schema()` — no more crash on empty DB
- **UI fixes**: opaque ExportMenu dropdown, opaque thread header with z-index for dropdown visibility, fixed undefined `--color-bg-tertiary` hover token
- Tests: 1652 Python + 199 Vitest (was 198, +1 new phase-level nav test)

---

## Previous State: Post PR #14 — Follow-ups, Revision Citations, CLI Persistence

### Follow-up Questions + Revision Citations + CLI Persistence + Provider Updates (2026-03-09)

- **Follow-up questions**: `generate_followups()` uses cheapest model w/ JSON mode to suggest 3 follow-up questions after consensus
  - `followups` on ConsensusContext, `followups_json` TEXT on Thread model + migration
  - `_run_consensus` now returns 8-tuple (was 7, added `followups`)
  - All callers updated: CLI, REST, WS, MCP, batch, decompose
  - Frontend: clickable follow-ups in ConsensusNav + ThreadNav (Disclosure), triggers new consensus
  - WS `complete` event includes `followups`, thread detail API returns them
- **Revision citations**: `handle_revise()` now accepts `tool_registry` + `web_search`, extracts citations
  - `revision_citations` on ConsensusContext + RoundResult, persisted to DB
  - `handle_propose()` now extracts proposal_citations directly in handler
  - WS sends revision citations in REVISE phase, ConsensusNav includes them in Sources
- **CLI persistence**: new `persist_consensus()` in `app.py` — CLI `ask` saves full round history to DB
  - `_ask_async` creates DB factory, disposes engine in finally block
- **CLI enhancements**: top-level `--rounds` and `--challengers` cascade to subcommands
  - `_parse_challengers()` accepts int count or comma-separated model refs
- **Calibration date filters**: frontend category + since/until date inputs on CalibrationDashboard
- **OpenAI**: `reasoning_effort: "high"` for GPT-5.x models (when no tools), gpt-5.2 in NO_TEMPERATURE_MODELS
- **Perplexity**: retry logic for APIConnectionError (2 attempts, 1s delay)
- **Alembic**: `DUH_DATABASE_URL` env var overrides alembic.ini
- Tests: new TestShowCitations (8), TestShowFinalDecisionOverview (2), calibration date filter tests (4), all 8-tuple updates

### Question Refinement + Native Web Search + Citations (2026-03-08, merged PR #13 + #14)

- **Question refinement**: pre-consensus clarification step (analyze → clarify → enrich → consensus)
  - `src/duh/consensus/refine.py`, API routes (`/api/refine`, `/api/enrich`), CLI `--refine` flag
  - Frontend: `RefinementPanel.tsx` tabbed UI, consensus store `'refining'` status
  - Graceful fallback on failure → original question proceeds to consensus
- **Native provider web search**: Anthropic/Google/Mistral/OpenAI/Perplexity use server-side search
  - `web_search: bool` param on `ModelProvider.send()` protocol
  - `config.tools.web_search.native` flag controls behavior
  - DDG proxy still available as fallback for non-native providers
- **Citations**: `Citation` dataclass on `ModelResponse`, extracted per provider, displayed in frontend
  - `CitationList` shared component, `ConsensusNav` collapsible Sources sidebar section
  - WS events include `citations` array for PROPOSE and CHALLENGE phases
- **Tools enabled by default**: `web_search` (DuckDuckGo) wired through all paths (CLI, REST, WS)
- **Provider tool format fix**: each provider transforms generic tool defs to native API format
- **Sidebar UX**: new-question button + collapsible sidebar toggle
- **Citation persistence**: `citations_json` on Contribution model, SQLite migration, thread detail API returns citations
- **Domain-grouped Sources**: ConsensusNav + ThreadNav group citations by hostname with Disclosure, P/C/R role badges
- **Anthropic streaming**: `send()` uses `_collect_stream()` internally to avoid 10-min timeout on large max_tokens
- **Parallel challenge streaming**: `_stream_challenges()` sends each result to frontend as it completes via `asyncio.as_completed`
- **max_tokens 32768**: bumped from 16384 across all handlers — citations are essential to trust
- 1641 Python tests + 194 Vitest tests (1835 total), build clean

### Z-index Fix + GPT-5.4 + .env Docs (2026-03-07)

- Z-index stacking context fix, GPT-5.4 model catalog entry, .env.example provider keys
- Password reset flow, SMTP mail module, JWT-scoped tokens
- 1603 Python tests + 185 Vitest tests (1788 total)

### Consensus Navigation & Collapsible Sections

- **Shared `Disclosure` primitive** — reusable chevron + toggle component used across PhaseCard, TurnCard, ConsensusComplete, DissentBanner, ThreadDetail
- **Sticky right-side nav** — `ConsensusNav` (live consensus) and `ThreadNav` (thread detail) show round/phase progress, individual challenger model names, scroll-to-section on click
- **Decision-first layout** — `ConsensusComplete` and thread final decision surface to the top when consensus is complete, collapsible via Disclosure
- **Per-challenger collapsibility** — each individual challenger is its own Disclosure within the CHALLENGE phase, nav shows short model names (e.g. `gpt-4`, `gemini`)
- **DissentBanner refactored** — uses Disclosure, parses `[model:name]:` prefix to extract model attribution and display ModelBadge
- **Responsive** — nav hidden on mobile (`hidden lg:block`), collapsible sections still work
- **Both views** — ConsensusPage (live streaming) and ThreadDetailPage (stored threads) share the same patterns
- 1586 Python tests + 166 Vitest tests (1752 total), build clean
- New files: Disclosure.tsx, ConsensusNav.tsx, ThreadNav.tsx, consensus-nav.test.tsx, thread-nav.test.tsx

### Epistemic Confidence Phase A

- **Renamed `_compute_confidence` → `_compute_rigor`** — old "confidence" measured challenge quality, now called "rigor"
- **Added `rigor` field** to Decision ORM model, ConsensusContext, RoundResult, SubtaskResult, VoteResult, VotingAggregation, SynthesisResult
- **Domain caps** — confidence capped by question intent: factual (0.95), technical (0.90), creative (0.85), judgment (0.80), strategic (0.70), default (0.85)
- **Epistemic formula**: `confidence = min(domain_cap(intent), rigor)` — rigor clamped by domain ceiling
- **Calibration module** — `src/duh/calibration.py` computes ECE (Expected Calibration Error) from decisions with outcomes
- **`duh calibration` CLI command** — shows calibration analysis with bucket breakdown
- **`GET /api/calibration` endpoint** — serves calibration data with category/date filters
- **Calibration frontend** — CalibrationDashboard, CalibrationPage, calibration Zustand store
- **SQLite migration** — `src/duh/memory/migrations.py` adds rigor column on startup for file-based SQLite
- **Full-stack propagation** — rigor shown in CLI, API, WebSocket, MCP, frontend across all views
- **Enhanced PDF export** — research-paper quality: header/footer, TOC, provider callouts, confidence meter, Unicode TTF
- 1586 Python tests + 126 Vitest tests (1712 total), ruff clean, mypy strict clean
- New files: calibration.py, migrations.py, test_calibration.py, test_confidence_scoring.py, test_cli_calibration.py, CalibrationDashboard.tsx, CalibrationPage.tsx, calibration.ts

### v0.5 Additions

- User accounts: User ORM model, JWT auth (bcrypt + PyJWT), RBAC (admin/contributor/viewer)
- PostgreSQL support: asyncpg driver, configurable connection pooling (pool_size, max_overflow, pool_pre_ping)
- Perplexity provider: 6th cloud provider (sonar, sonar-pro, sonar-deep-research), citation parsing
- Prometheus metrics: `/api/metrics` endpoint with counters, histograms, gauges (no external deps)
- Extended health checks: `/api/health/detailed` with DB connectivity, provider health, uptime, version
- Backup/restore: `duh backup` (SQLite copy or JSON export), `duh restore` (with `--merge` mode)
- Per-user rate limiting: middleware keys by user_id > api_key > IP, per-provider RPM limits in config
- Compound indexes: `(thread_id, created_at)` on decisions, `(category, genus)` on decisions, `(turn_id, role)` on contributions
- Playwright E2E tests: navigation, consensus form, decision space, preferences
- 26 multi-user integration tests: user isolation, admin access, registration flow, RBAC, JWT validation, deactivation
- 12 load tests: p50/p95/p99 latency, concurrent requests (10/50/100), rate limiting under load, sustained throughput
- Alembic migration `005_v05_users.py`: users table, nullable user_id FK on threads/decisions/api_keys
- 3 new docs: production-deployment.md, authentication.md, monitoring.md
- Version 0.5.0 across pyproject.toml, __init__.py, api/app.py
- 1539 Python tests + 122 Vitest tests (1661 total), ruff clean

### v0.4 Additions (Previously Shipped)

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
| 2026-02-17 | v0.5 T1-T3 (Phase 1: DB & Multi-User) — User model + migration, JWT auth, RBAC | Done |
| 2026-02-17 | v0.5 T4-T5 (Phase 2: PostgreSQL) — asyncpg support, connection pooling + indexes | Done |
| 2026-02-17 | v0.5 T6-T8 (Phase 3: Rate Limiting & Monitoring) — per-user rate limits, Prometheus metrics, health checks | Done |
| 2026-02-17 | v0.5 T9 (Phase 4: Perplexity) — Perplexity provider adapter (sonar, sonar-pro, sonar-deep-research) | Done |
| 2026-02-17 | v0.5 T10-T11 (Phase 5: Backup/Restore) — backup CLI, restore CLI with merge mode | Done |
| 2026-02-17 | v0.5 T12-T13 (Phase 6: Playwright) — E2E setup + core flows, extended tests | Done |
| 2026-02-17 | v0.5 T14-T18 (Phase 7: Ship) — multi-user integration tests, load tests, docs, migration finalized, version bump | Done |
| 2026-02-17 | v0.5.0 — "It Scales" | **Complete** |
| 2026-02-17 | Export to Markdown & PDF (CLI + API + Web UI) | Done |
| 2026-02-18 | Epistemic Confidence Phase A (rigor + domain caps + calibration) | Done |
| 2026-02-18 | Consensus nav + collapsible sections + decision-first layout | Done |
| 2026-02-19 | UX cleanup: collapse defaults, max_tokens 16384, cross-provider challengers, truncation detection, glass exports, PDF BI font fix | Done |
| 2026-02-19 | v0.6 T1-T5: Frontend auth (auth store, API client auth, login page, route protection, dev mode) | Done |
| 2026-02-19 | v0.6 T6: Batch feedback on threads list (inline Pass/Partial/Fail buttons, backend outcome enrichment) | Done |
| 2026-02-19 | v0.6 T7: Frontend auth + feedback tests (11 auth store + 8 auth component tests) | Done |
| 2026-02-19 | v0.6 T8: Documentation (web-ui auth, authentication guide, epistemic-confidence concept doc) | Done |
| 2026-02-19 | v0.6 T9: Version bump to 0.6.0 | Done |
| 2026-02-19 | v0.6.0 — "It's Honest" | **Complete** |
| 2026-02-20 | Fix sign-out bug: replaced broken mousedown outside-click handler with backdrop pattern in TopBar | Pending verification |
| 2026-02-20 | Auto-generate JWT secret in config loader for dev environments | Done |
| 2026-03-07 | Password reset + .env support + TopBar z-index fix | Done |
| 2026-03-07 | Z-index stacking context fix: tokens, isolate, click-outside pattern | Done |
| 2026-03-07 | GPT-5.4 added to model catalog (1M ctx, $2.50/$15.00, no-temperature) | Done |
| 2026-03-07 | .env.example updated with provider API key placeholders | Done |
| 2026-03-07 | README updated with all provider env vars | Done |
| 2026-03-08 | Question refinement (analyze → clarify → enrich → consensus) | Done (PR #13) |
| 2026-03-08 | Native provider web search (Anthropic/Google/Mistral/OpenAI/Perplexity) | Done (PR #13) |
| 2026-03-08 | Citations extraction + frontend CitationList + ConsensusNav Sources | Done (PR #13) |
| 2026-03-08 | Tools enabled by default (web_search wired through CLI/REST/WS) | Done (PR #13) |
| 2026-03-08 | Provider tool format fix (generic → native transform per provider) | Done (PR #13) |
| 2026-03-08 | Sidebar UX (new-question button, collapsible toggle) | Done (PR #13) |
| 2026-03-08 | README rewrite + CLI citation display (7-tuple _run_consensus) | Done (PR #14) |
| 2026-03-09 | Follow-up questions (generate, persist, display, clickable) | In Progress |
| 2026-03-09 | Revision citations (handle_revise with tools/search, persist, display) | In Progress |
| 2026-03-09 | CLI DB persistence (persist_consensus, _ask_async DB factory) | In Progress |
| 2026-03-09 | CLI top-level --rounds/--challengers cascade + _parse_challengers | In Progress |
| 2026-03-09 | Calibration date filters (frontend category/since/until) | In Progress |
| 2026-03-09 | OpenAI reasoning_effort for GPT-5.x, gpt-5.2 catalog | In Progress |
| 2026-03-09 | Perplexity retry logic for APIConnectionError | In Progress |
| 2026-03-09 | Alembic DUH_DATABASE_URL env var support | In Progress |
