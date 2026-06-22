# Architectural Decisions

**Last Updated**: 2026-06-22

---

## 2026-02-15: Multi-Model Consensus Over Single-Model Routing

**Status**: Approved
**Context**: Existing frameworks (LangGraph, CrewAI, AutoGen) route tasks to individual models. Some research (MoA) shows multi-model collaboration improves quality.
**Decision**: duh runs structured consensus (PROPOSE → CHALLENGE → REVISE → COMMIT) across multiple models from multiple providers, not just routing to one.
**Alternatives**:
- Single best-model routing (simpler, cheaper, but loses diversity of perspective)
- MoA-style layered synthesis (proven to work, but loses dissent and doesn't accumulate knowledge)
**Consequences**: Higher token cost per query. Richer output. Dissent preserved. Knowledge accumulation possible.
**References**: `competitive-landscape.md#2`, MoA paper (ICLR 2025)

---

## 2026-02-15: Knowledge Accumulation as Core Product

**Status**: Approved
**Context**: All existing multi-model tools are stateless — each query starts from scratch.
**Decision**: Persistent memory is the core product, not the orchestration. Models are replaceable infrastructure; accumulated knowledge (decisions, reasoning, dissent, outcomes) is the durable value.
**Alternatives**:
- Session-only memory (simpler, like existing tools)
- External knowledge base integration (RAG-style, but doesn't generate its own knowledge)
**Consequences**: Requires robust database layer. System gets smarter over time. Creates moat against competitors.
**References**: `projectbrief.md#Core Tenets` (tenet 2)

---

## 2026-02-15: Federated Knowledge via Navigator Nodes

**Status**: Approved (design phase — implementation Phase 4)
**Context**: Individual instances accumulating knowledge in isolation is valuable but limited. Connected instances sharing knowledge is exponentially more valuable.
**Decision**: Lightweight navigator nodes index shared knowledge (metadata + pointers). Instances query navigators ("has anyone solved X?") and get back matching decisions with provenance. Full knowledge stays on source instances; navigators hold the map.
**Alternatives**:
- Centralized knowledge server (simpler, but single point of failure/control)
- Full peer-to-peer search (no navigator needed, but O(n) search doesn't scale)
- Blockchain-based knowledge registry (adds complexity without clear benefit)
**Consequences**: Requires network protocol design. Trust/quality signal needed. Anyone can run a navigator. No central authority.
**References**: `projectbrief.md#Architecture`, DNS/BitTorrent as architectural inspiration

---

## 2026-02-15: Local Models as First-Class Citizens

**Status**: Approved
**Context**: Most frameworks treat local models as fallbacks or development conveniences.
**Decision**: Local models (Ollama, LM Studio, llama.cpp, vLLM) participate equally in consensus and access the network's collective knowledge. A zero-cost local instance benefits from cloud-model-generated knowledge.
**Alternatives**:
- Cloud-only (simpler, but creates vendor dependency and excludes users who can't/won't use cloud APIs)
- Local as fallback (supports offline but treats local as second-class)
**Consequences**: Must handle heterogeneous model capabilities (different context windows, tool use support, quality levels). Knowledge democratization — expensive thinking done once, shared freely.
**References**: `projectbrief.md#Core Tenets` (tenets 6, 8)

---

## 2026-02-15: Forced Disagreement in Consensus Protocol

**Status**: Approved
**Context**: LLMs are sycophantic. If Claude proposes X, GPT will likely say "great idea, and also Y." False consensus is worse than a single model because it feels validated.
**Decision**: The CHALLENGE phase forces productive disagreement: "What's wrong with this?", "What would you do differently?", "What's the biggest risk?" Devil's advocate role assigned each round.
**Alternatives**:
- Natural consensus (simpler, but produces sycophantic agreement)
- Voting only (binary agree/disagree, loses nuance)
**Consequences**: Better quality output. Preserved dissent is valuable knowledge. May increase round count/cost. Protocol design is critical — naive debate doesn't always beat single strong model (per ICLR 2025 evaluation).
**References**: `competitive-landscape.md#3` (MAD evaluation caveat)

---

## 2026-02-15: Domain-Agnostic Design

**Status**: Approved
**Context**: Most multi-agent frameworks are developer-focused (code generation, software engineering).
**Decision**: duh is a general-purpose thinking tool. The consensus protocol works for any domain: code, business, science, agriculture, personal decisions, fact-checking, research.
**Alternatives**:
- Dev-focused first, expand later (faster to market, narrower audience)
- Vertical-specific tools (agriculture AI, legal AI, etc.)
**Consequences**: No domain-specific assumptions in core architecture. Broader potential market. Harder to market initially (no specific vertical story).
**References**: `projectbrief.md#Core Tenets` (tenet 7)

---

## 2026-02-15: Python + Docker for Distribution

**Status**: Approved
**Context**: Need to be installable anywhere — home servers, cloud VMs, laptops.
**Decision**: Python for the core (SDK ecosystem), Docker for distribution (one command install).
**Alternatives**:
- Rust (single binary, but thin SDK ecosystem — would hand-roll all provider integrations)
- Go (decent balance, but less AI ecosystem support than Python)
- Node.js (viable SDKs exist, but Python is the AI ecosystem lingua franca)
**Consequences**: Python packaging complexity mitigated by Docker. Performance is not a concern (bottleneck is network latency to model APIs). All provider SDKs available.
**References**: `techContext.md`

---

## 2026-02-15: Cost-Aware, Not Cost-Constrained

**Status**: Approved
**Context**: Multi-model consensus multiplies API costs. Some instinct is to restrict token usage.
**Decision**: Tokens are the currency. Token cost correlates with output quality. Show costs transparently, let users set thresholds, never silently degrade quality. Use cheap/local models for infrastructure tasks (summaries, routing), expensive models for thinking.
**Alternatives**:
- Budget caps with automatic degradation (cheaper, but defeats the purpose)
- Fixed model tiers (loses flexibility)
**Consequences**: Higher potential cost per query. User controls their spend. System always delivers best available quality.
**References**: `projectbrief.md#Cost Philosophy`

---

## 2026-02-15: SOTA Models for Phase 0 Thesis Validation

**Status**: Approved
**Context**: Phase 0 tests whether multi-model consensus beats single-model answers. Original plan used Sonnet 4.5 to isolate the method effect. User argued the thesis test should use the best available models.
**Decision**: Use Opus 4.6 + GPT-5.2 for the real benchmark (`--budget full`). Cheaper models (Sonnet + GPT-4o) available via `--budget small` for iterating on prompts/plumbing.
**Alternatives**:
- Sonnet-only (cheaper, isolates method over model, but doesn't test the actual product scenario)
- Opus-only without GPT (misses the cross-provider diversity that IS the product)
**Consequences**: Higher benchmark cost (~$60 full run vs ~$15). Results represent actual product quality. Budget flag enables cheap iteration.
**References**: `phase0/config.py:11-25` (BUDGETS dict)

---

## 2026-02-15: Date Grounding in All Prompts

**Status**: Approved
**Context**: Models may give different answers based on assumed date. Questions about technology, market conditions, and strategy are time-sensitive.
**Decision**: Inject `Today's date is YYYY-MM-DD` and temporal grounding instruction into every system prompt via `_grounding()` function.
**Alternatives**:
- No grounding (models use training date heuristics — inconsistent)
- Per-question date context (more precise but tedious)
**Consequences**: All answers temporally grounded. Consistent baseline across models. Trivial implementation cost.
**References**: `phase0/prompts.py:8-16` (_grounding function)

---

## 2026-02-15: Phase 0 Exit Decision — PROCEED

**Status**: Approved
**Context**: Phase 0 benchmark ran 17/50 questions (stopped early — sufficient signal). Auto-decision said ITERATE (33% J/S win rate below 60% threshold), but that metric measures "ranked #1 out of 4 methods" — a misleading bar when Consensus and Ensemble split multi-model wins.
**Decision**: PROCEED to v0.1. Head-to-head data clearly validates the thesis: Consensus beats Direct (47-88% depending on judge), beats Self-Debate (76.5%), scores higher on all 5 dimensions. The method works; prompts will improve in v0.1.
**Alternatives**:
- ITERATE (refine prompts, re-run) — delay for marginal improvement on a benchmark that already shows the pattern
- STOP (thesis invalidated) — contradicted by all head-to-head data
**Consequences**: v0.1 development begins. Phase 0 prompts carry forward as seeds. Prompt refinement is ongoing in v0.1 tasks 11-16 (consensus state handlers).
**References**: `results/analysis/`, `progress.md#Benchmark Results`

---

## 2026-02-15: Local Models Deferred to v0.1

**Status**: Approved
**Context**: Phase 0 benchmarks cloud SOTA models to validate the thesis. Ollama/local support was available in the plan.
**Decision**: Phase 0 uses only Anthropic + OpenAI cloud APIs. Local model support (Ollama via OpenAI-compatible base_url) begins in v0.1.
**Alternatives**:
- Include local models in Phase 0 (adds complexity, local quality would drag down results)
**Consequences**: Simpler Phase 0. Clean thesis test with best models. Local model integration proven in v0.1 with Ollama adapter.
**References**: `roadmap.md:138` (Ollama in v0.1)

---

## 2026-02-16: Voting as Parallel Fan-Out (Not State Machine)

**Status**: Approved
**Context**: v0.2 adds a voting protocol for tasks where consensus debate is overkill (factual questions, preference polls). Design choice: extend the state machine or build a separate parallel architecture.
**Decision**: Voting is a simple parallel fan-out: send the same prompt to all models independently, collect responses, aggregate via majority or weighted voting. NOT a state machine — no PROPOSE/CHALLENGE/REVISE cycle.
**Alternatives**:
- Extend state machine with VOTE state (adds complexity to an already complex machine)
- Sequential voting rounds (slower, no benefit for independent opinions)
**Consequences**: Simpler architecture for factual/preference tasks. Auto-classification (`classify_task_type()`) selects consensus vs voting. Consistent with ACL 2025 findings that parallel independent reasoning outperforms sequential debate for factual tasks.
**References**: `src/duh/consensus/voting.py`, `src/duh/consensus/classifier.py`

---

## 2026-02-16: Decomposition as Single-Model (Not Consensus)

**Status**: Approved
**Context**: v0.2 adds task decomposition. Open question: should DECOMPOSE itself be a consensus operation (multiple models debate how to break down the task)?
**Decision**: DECOMPOSE is a single-model operation. One model decomposes the task into a subtask DAG. Each subtask then runs through consensus independently.
**Alternatives**:
- Multi-model decomposition (models debate the breakdown — adds a full consensus round before any work begins)
- User-defined decomposition (manual, loses automation benefit)
**Consequences**: Faster decomposition (one model call vs full consensus). Simpler implementation. Each subtask still gets full consensus treatment. Decomposition quality is "good enough" from a single strong model.
**References**: `src/duh/consensus/decompose.py`, `src/duh/consensus/scheduler.py`

---

## 2026-02-16: Tool Protocol via Python Protocol (Structural Typing)

**Status**: Approved
**Context**: v0.2 adds tool-augmented reasoning. Tools need a common interface for the registry and augmented send loop.
**Decision**: Use Python `Protocol` class for the Tool interface — consistent with the existing provider adapter pattern. Tools implement `name`, `description`, `parameters_schema`, and `execute()`.
**Alternatives**:
- ABC base class (requires explicit inheritance, less flexible)
- Dict-based tools (no type safety)
- Decorator-based registration (implicit, harder to test)
**Consequences**: Structural typing means any object with the right methods is a tool — easy to extend. ToolRegistry handles lookup. tool_augmented_send handles the execute-and-resubmit loop.
**References**: `src/duh/tools/base.py`, `src/duh/tools/registry.py`, `src/duh/tools/augmented_send.py`

---

## 2026-02-16: Taxonomy Classification at COMMIT Time

**Status**: Approved
**Context**: v0.2 adds decision taxonomy (domain, category, tags, complexity). When should classification happen?
**Decision**: Classify at COMMIT time via a lightweight model call with structured output. The decision text is already finalized, so classification is accurate. Adds one cheap model call to the commit step.
**Alternatives**:
- Classify at query time (before consensus — less accurate, decision not yet formed)
- User-provided taxonomy (manual burden, inconsistent)
- Post-hoc batch classification (delayed, loses real-time value)
**Consequences**: Taxonomy is automatic and accurate. One additional cheap model call per decision. Structured metadata enables filtering, analytics, and outcome correlation.
**References**: `src/duh/consensus/handlers.py` (`handle_commit(classify=True)`, `_classify_decision()`)

---

## 2026-02-16: MCP Server Calls Python Directly (No REST Dependency)

**Status**: Approved
**Context**: v0.3 adds both a REST API and an MCP server. The MCP server could either call the REST API or import Python functions directly.
**Decision**: MCP server imports and calls Python functions directly (e.g., `_run_consensus`, `_ask_voting_async`). No REST dependency. `duh mcp` starts standalone without needing `duh serve`.
**Alternatives**:
- MCP wraps REST API (simpler, but adds network hop and requires running server)
- Shared library extracted (premature abstraction at this stage)
**Consequences**: MCP server is independently deployable. No latency overhead from REST round-trip. Both REST and MCP share the same underlying async functions. One fewer failure mode.
**References**: `src/duh/mcp/server.py`, `src/duh/cli/app.py`

---

## 2026-02-16: API Keys Local-Only (Hashed in SQLite/Postgres)

**Status**: Approved
**Context**: v0.3 REST API needs authentication. Options: JWT tokens, OAuth, or simple API keys.
**Decision**: Local API keys hashed with SHA-256, stored in the same database (SQLite/Postgres). `X-API-Key` header. No external auth provider. Keys created/revoked via CLI or API.
**Alternatives**:
- JWT tokens (more complex, needs secret management, overkill for single-instance)
- OAuth (requires external provider, adds significant complexity)
- No auth (insecure for any non-localhost deployment)
**Consequences**: Simple, self-contained auth. No external dependencies. Works with SQLite and Postgres. Rate limiting per key. Migration `004_v03_api_keys.py` adds the table.
**References**: `src/duh/api/middleware.py`, `src/duh/memory/models.py` (APIKey model)

---

## 2026-02-17: React Embedded in FastAPI (Single Origin)

**Status**: Approved
**Context**: v0.4 adds a web UI. Options: separate frontend service, or embed the built frontend in FastAPI.
**Decision**: Vite builds to `web/dist/`, FastAPI mounts as static files with SPA fallback. Single origin in production — no CORS issues, no separate deployment. Dev mode uses Vite's proxy to forward /api and /ws to FastAPI on :8080.
**Alternatives**:
- Separate frontend service (adds deployment complexity, CORS configuration, two processes)
- Server-side rendering with Jinja2 (loses React ecosystem, harder real-time updates)
- HTMX (simpler but insufficient for 3D visualization and complex interactivity)
**Consequences**: Single `duh serve` command serves everything. Docker deployment is one container. No CORS in production. Dev experience: two terminals (Vite :3000 + FastAPI :8080) with proxy.
**References**: `src/duh/api/app.py` (`_mount_frontend()`), `web/vite.config.ts` (proxy config)

---

## 2026-02-17: Three.js via React Three Fiber (Code-Split)

**Status**: Approved
**Context**: The 3D Decision Space visualization needs WebGL. Options: Three.js directly, React Three Fiber, D3.js with WebGL, or a 2D-only approach.
**Decision**: React Three Fiber (R3F) wraps Three.js in React components. Scene3D component is lazy-loaded via `React.lazy()`, keeping the 873KB Three.js chunk out of the main bundle. Mobile devices get a 2D SVG scatter fallback via `useMediaQuery` hook.
**Alternatives**:
- Raw Three.js (imperative, harder to integrate with React state)
- D3.js + WebGL (less 3D ecosystem support)
- 2D only (misses the flagship visualization experience)
- deck.gl (heavier, designed for maps not point clouds)
**Consequences**: 873KB lazy chunk only loads on Decision Space page. Main bundle stays at 278KB. InstancedMesh handles thousands of points efficiently. Mobile fallback ensures accessibility.
**References**: `web/src/components/decision-space/Scene3D.tsx`, `DecisionCloud.tsx`, `ScatterFallback.tsx`

---

## 2026-02-17: Zustand for Frontend State (Not Redux)

**Status**: Approved
**Context**: The web UI needs state management for WebSocket-driven consensus, thread lists, decision space filters, and user preferences.
**Decision**: Zustand 5 with 4 stores (consensus, threads, decision-space, preferences). Preferences store uses `zustand/persist` middleware for localStorage persistence.
**Alternatives**:
- Redux Toolkit (more boilerplate, overkill for this scale)
- React Context (insufficient for complex async state like WebSocket events)
- Jotai/Recoil (atomic, but stores are more natural for this domain)
**Consequences**: Minimal boilerplate. Stores are plain functions — easy to test without React rendering. Persist middleware gives free preferences persistence. No provider wrappers needed.
**References**: `web/src/stores/consensus.ts`, `threads.ts`, `decision-space.ts`, `preferences.ts`

---

## 2026-02-17: CSS Custom Properties with prefers-color-scheme (Not Tailwind Dark Mode)

**Status**: Approved
**Context**: The web UI uses 22 CSS custom properties for colors, glass, borders, radii. Need light/dark mode support.
**Decision**: Define all variables in `:root` (dark default) + `@media (prefers-color-scheme: light)` override. Also provide `.theme-dark`/`.theme-light` classes for manual override. No Tailwind `dark:` classes — all theming via CSS variables.
**Alternatives**:
- Tailwind `dark:` prefix (would require duplicating every color class, bloats HTML)
- JavaScript theme toggle with class swap (more code, flash on load)
- Dark-only (excludes light mode users)
**Consequences**: Automatic OS preference detection. Zero JS for theme switching. Manual override possible via class on any ancestor. All components automatically adapt — no per-component dark/light logic needed.
**References**: `web/src/theme/duh-theme.css`

---

## 2026-02-17: Markdown Rendering with Lazy Mermaid

**Status**: Approved
**Context**: LLM responses contain markdown (headers, lists, code, tables) that was rendered as raw text. Need full markdown parsing with code highlighting and diagram support.
**Decision**: Shared `<Markdown>` component using react-markdown + remark-gfm + rehype-highlight. Mermaid diagrams lazy-loaded via dynamic `import('mermaid')` — keeps the 498KB mermaid bundle out of the main chunk. highlight.js with github-dark-dimmed theme + light mode CSS overrides.
**Alternatives**:
- marked + DOMPurify (lighter but no React integration, manual sanitization)
- MDX (overkill, runtime compilation unnecessary)
- Bundling mermaid eagerly (bloats main bundle from 278KB to 1.1MB)
**Consequences**: Main bundle: 617KB (up from 278KB — react-markdown + highlight.js needed on all pages). Mermaid: 498KB lazy chunk only when mermaid blocks exist. Full GFM support (tables, task lists, strikethrough). Code syntax highlighting in 180+ languages. 5 components updated to use `<Markdown>` for LLM content.
**References**: `web/src/components/shared/Markdown.tsx`, used in ConsensusComplete, PhaseCard, TurnCard, DissentBanner

---

## 2026-02-17: create_all Only for In-Memory SQLite

**Status**: Approved
**Context**: `_create_db()` in `cli/app.py` called `Base.metadata.create_all()` unconditionally. This conflicts with alembic migrations for file-based SQLite and PostgreSQL: `create_all` creates tables from current models (bypassing alembic version tracking) but cannot add columns to existing tables. When the v0.5 migration added `user_id` to `threads`, `decisions`, and `api_keys`, the `users` table was already created by `create_all` but the FK columns were missing — causing `OperationalError: no such column: api_keys.user_id` at runtime.
**Decision**: Only call `create_all` when the database URL contains `:memory:` (in-memory SQLite used by tests and dev). File-based SQLite and PostgreSQL rely exclusively on alembic migrations for schema management.
**Alternatives**:
- Keep `create_all` with `checkfirst=True` (default) — doesn't help, `create_all` can't alter existing tables
- Run alembic migrations programmatically at startup — adds complexity, conflates app startup with migration
- Remove `create_all` entirely — breaks in-memory test fixtures that don't run alembic
**Consequences**: Tests continue to work (in-memory SQLite still uses `create_all`). Production databases must run `alembic upgrade head` after code updates. This was already the expected workflow but is now enforced.
**References**: `src/duh/cli/app.py:101-104`

---

## 2026-02-18: Epistemic Confidence — Separate Rigor from Confidence

**Status**: Approved
**Context**: The original `_compute_confidence()` in `handlers.py` measured challenge quality (ratio of genuine vs sycophantic challenges), producing a score in [0.5, 1.0]. This was misleading: a factual question ("What is the capital of France?") and a strategic question ("Will AI replace software engineers by 2035?") could both score 1.0 confidence if all challenges were genuine. But inherently uncertain questions should never report near-certain confidence.
**Decision**: Split into two metrics:
- **Rigor** (renamed from old confidence): measures challenge quality, [0.5, 1.0]
- **Confidence** (epistemic): `min(domain_cap(intent), rigor)` — rigor clamped by a per-domain ceiling based on question intent (factual=0.95, technical=0.90, creative=0.85, judgment=0.80, strategic=0.70, default=0.85).
**Alternatives**:
- Single blended score (simpler, but hides the two distinct signals)
- User-configurable caps (more flexible, but adds UX complexity without clear benefit)
- LLM-estimated confidence (model judges own uncertainty — unreliable, circular)
**Consequences**: Confidence scores are now more honest. Strategic questions max out at 70% even with perfect rigor. Rigor is preserved as a separate signal for calibration analysis. Requires `rigor` column added to Decision model. Full-stack change: ORM, handlers, CLI, API, WebSocket, MCP, frontend all updated.
**References**: `src/duh/consensus/handlers.py:641-670`, `src/duh/calibration.py`

---

## 2026-02-18: Lightweight SQLite Migrations (Not Alembic)

**Status**: Approved
**Context**: Adding the `rigor` column to the `decisions` table requires a migration for existing file-based SQLite databases. Alembic handles PostgreSQL migrations, but for SQLite (the default local dev DB), running `alembic upgrade head` is a friction point for casual users.
**Decision**: Created `src/duh/memory/migrations.py` with `ensure_schema()` that runs on startup for file-based SQLite only. Uses `PRAGMA table_info()` to detect missing columns and `ALTER TABLE` to add them. In-memory SQLite uses `create_all` (unchanged). PostgreSQL uses Alembic (unchanged).
**Alternatives**:
- Alembic-only (requires users to run migration command)
- create_all for all databases (can't alter existing tables)
- Manual migration instructions in docs (user friction)
**Consequences**: File-based SQLite databases auto-migrate on startup. Zero friction for local users. PostgreSQL still requires `alembic upgrade head`. Lightweight and self-contained.
**References**: `src/duh/memory/migrations.py`, `src/duh/cli/app.py:107-110`

---

## 2026-03-08: Native Provider Web Search Over DDG Proxy

**Status**: Approved
**Context**: The original web search tool used DuckDuckGo as a proxy — every provider's tool calls went through DDG, which returned index pages rather than real content. Most major providers now offer server-side web search that returns higher-quality results with citations.
**Decision**: Add `web_search: bool` parameter to the `ModelProvider.send()` protocol. When `config.tools.web_search.native` is true, each provider uses its native search capability: Anthropic (`web_search_20250305` server tool), Google (`GoogleSearch()` grounding), Mistral (`{"type": "web_search"}`), OpenAI (`web_search_options`), Perplexity (always native). DDG proxy remains as fallback for providers/models that don't support native search.
**Alternatives**:
- DDG-only (simpler, but returns low-quality index pages instead of real content)
- Single search provider for all (e.g., Bing API — adds external dependency and API key)
- Remove web search entirely (loses grounding capability)
**Consequences**: Higher quality search results with real content. Citations extractable from provider responses. Each provider has different native search API shape — increases per-provider complexity. Google grounding and function declarations can't coexist (grounding replaces function tools).
**References**: `src/duh/providers/anthropic.py`, `src/duh/providers/google.py`, `src/duh/providers/mistral.py`, `src/duh/providers/openai.py`, `src/duh/tools/augmented_send.py`

---

## 2026-03-08: Question Refinement Uses Most Expensive Model

**Status**: Approved
**Context**: Question refinement analyzes user questions before consensus to determine if clarification is needed. The analysis quality directly impacts downstream consensus quality — a poorly refined question wastes all subsequent model calls.
**Decision**: `analyze_question()` and `enrich_question()` in `src/duh/consensus/refine.py` use the most expensive configured model (sorted by cost), not the cheapest. The refinement step is a single model call, so the cost difference is minimal compared to the full consensus round it precedes.
**Alternatives**:
- Cheapest model (saves tokens, but poor analysis leads to poor consensus)
- User-configurable refinement model (adds UX complexity)
- Multi-model refinement (overkill — single strong model is sufficient for question analysis)
**Consequences**: Better question analysis quality. Marginal cost increase (one extra expensive model call). Graceful fallback on failure — original question proceeds to consensus unchanged.
**References**: `src/duh/consensus/refine.py`, `src/duh/api/routes/ask.py`, `src/duh/cli/app.py`

---

## 2026-03-08: Tools Enabled by Default

**Status**: Approved
**Context**: Web search was originally opt-in. Users who didn't know about the `--tools` flag got ungrounded responses. Most queries benefit from web search grounding.
**Decision**: `web_search` tool is enabled by default across CLI, REST API, and WebSocket paths. The `config.tools.web_search` section controls behavior. Native provider search is preferred when available.
**Alternatives**:
- Opt-in only (simpler, but most users miss it)
- Always-on with no config (inflexible for cost-sensitive users)
- Per-question tool selection (too much UX friction)
**Consequences**: Better default experience — responses are grounded in current information. Slightly higher cost per query (search tool calls). Users can disable via config if needed.
**References**: `src/duh/config/schema.py`, `src/duh/cli/app.py`, `src/duh/api/routes/ws.py`

---

## 2026-03-08: Citation Persistence on Contributions

**Status**: Approved
**Context**: Citations were emitted over WebSocket during live consensus but never persisted. Viewing a thread later from the Threads section showed no sources — undermining the trust value of native web search.
**Decision**: Add `citations_json` TEXT column to the `Contribution` model (nullable, JSON-encoded list of `{url, title}`). Track `proposal_citations` on `ConsensusContext` and archive to `RoundResult`. Serialize and persist during `_persist_consensus`. Thread detail API returns parsed citations on `ContributionResponse`. ThreadNav shows domain-grouped sources matching ConsensusNav.
**Alternatives**:
- Separate Citation table with FK to Contribution (more normalized, but adds query complexity for marginal benefit)
- Store citations only on Decision (loses per-role attribution)
- Don't persist (simpler, but citations are essential to trust)
**Consequences**: Citations survive beyond the WebSocket session. Thread detail view shows sources grouped by domain with role attribution (P/C/R). SQLite auto-migration handles existing databases. Slightly larger DB rows due to JSON text.
**References**: `src/duh/memory/models.py:146`, `src/duh/api/routes/threads.py`, `src/duh/api/routes/ws.py`, `web/src/components/threads/ThreadNav.tsx`

---

## 2026-03-08: Anthropic Streaming Internally in send()

**Status**: Approved
**Context**: Increasing `max_tokens` to 32768 triggered Anthropic SDK's 10-minute timeout error: "Streaming is required for operations that may take longer than 10 minutes." The `send()` method used non-streaming `messages.create()`.
**Decision**: `send()` now calls `_collect_stream()` which uses `messages.stream()` as a context manager and collects the final `Message` via `get_final_message()`. The returned object is identical to `messages.create()` output, so all downstream parsing (citations, tool calls, text concatenation) works unchanged.
**Alternatives**:
- Keep non-streaming and lower max_tokens (loses citation content to truncation)
- Full streaming to frontend (larger change, separate concern)
- Increase Anthropic client timeout (fragile, doesn't scale)
**Consequences**: No more timeout errors at any max_tokens value. Test mocks must mock `messages.stream` context manager instead of `messages.create`. Marginal latency increase from stream overhead (negligible vs network time).
**References**: `src/duh/providers/anthropic.py:222-229`

---

## 2026-03-08: Parallel Challenge Streaming via as_completed

**Status**: Approved
**Context**: Challengers were already running in parallel via `asyncio.gather` in `handle_challenge`, but the WebSocket handler sent all results after ALL challengers finished. Users saw nothing until the slowest challenger responded.
**Decision**: New `_stream_challenges()` function in `ws.py` uses `asyncio.as_completed()` to send each challenge result to the frontend immediately as each completes. Builds `ChallengeResult` objects and updates `ctx.challenges` directly, bypassing `handle_challenge`.
**Alternatives**:
- Keep batched approach (simpler, but poor UX — users wait for slowest model)
- Token-level streaming per challenger (much more complex, requires protocol changes)
- Sequential challengers (defeats the purpose of multi-model)
**Consequences**: First challenger to respond appears immediately. More engaging real-time experience. WS test mocks now patch `_stream_challenges` instead of `handle_challenge`. Challenge order in UI reflects completion speed, not configuration order.
**References**: `src/duh/api/routes/ws.py:253-347`, `tests/unit/test_api_ws.py`

---

## 2026-06-22: Incremental Per-Round Persistence Over Single Write at COMPLETE

**Status**: Approved (implemented)
**Context**: All three persistence paths (CLI, WebSocket, REST) built the full thread in memory and wrote once at COMPLETE. A crash mid-run lost the entire consensus. REST additionally had a "lite" path that saved only the decision.
**Decision**: A single shared `IncrementalPersister` (`src/duh/memory/persist.py`): create the thread `active` up front, commit each finished round in its own transaction, finalize to `complete` at the end. All three entry points use it. `_run_consensus` exposes the created thread id via an additive `on_thread_created` callback (keeping the 8-tuple return stable).
**Alternatives**:
- Keep single-write (simpler, but mid-run crash = total loss)
- Write-ahead log / event sourcing (more robust, much heavier for a SQLite app)
- Bump `_run_consensus` to a 9-tuple to return the id (breaks ~7 callers + test mocks)
**Consequences**: Mid-run crash leaves a real partial `active` thread. Three duplicated implementations collapsed into one. Final DB state identical to before, so state-asserting tests stayed green.
**References**: `tasks/2026-06/260622_incremental-persistence.md`, `src/duh/memory/persist.py`

---

## 2026-06-22: Empirical Behavior Probing + Propose-Only Catalog Refresh Over Trusting Feeds

**Status**: Approved (implemented)
**Context**: The model catalog goes stale (new models, price changes, deprecations). A community feed (truefoundry/models) has the data but is unreliable on *behavioral* fields — it was wrong about GPT-5.5 rejecting temperature.
**Decision**: Model IDs come from live provider APIs; pricing/context/status from the feed, cross-checked against known anchors; **temperature/behavior is probed against the live endpoint, never trusted**. `scripts/refresh_catalog.py` is a manual, propose-only tool — it diffs and reports, never auto-edits `catalog.py`. Temperature membership is encoded in `NO_TEMPERATURE_MODELS` (OpenAI) and `ANTHROPIC_NO_TEMPERATURE_MODELS`.
**Alternatives**:
- Trust the feed wholesale (would have shipped a gpt-5.5 temperature bug)
- Runtime fetch of the catalog (adds a third-party dependency to billing-critical cost math + an availability surface)
- Self-healing retry on the "temperature deprecated" 400 (more robust; deferred as a cross-provider safety net — see open follow-up)
**Consequences**: No fabricated catalog data. The refresh tool caught two of my own context-window mistakes during development. The static-set approach must be maintained per release — the tool now probes both OpenAI and Anthropic so drift is visible. Note: this class of bug bit users twice (gpt-5.5, then Opus 4.8).
**References**: `tasks/2026-06/260622_model-catalog-refresh.md`, `scripts/refresh_catalog.py`

---

## 2026-06-22: One OpenAI-Compatible Adapter for Any Host (provider_id)

**Status**: Approved (implemented)
**Context**: `OpenAIProvider`'s `provider_id` was hardcoded to `"openai"`, so it couldn't serve a second OpenAI-compatible host (e.g. Cloudflare Workers AI) without colliding. Adding GLM-5.2 needed a distinct provider.
**Decision**: `OpenAIProvider` takes an optional `provider_id` and resolves its catalog/capabilities from it. `_setup_providers` registers any enabled provider that has a `base_url` + key as an OpenAI-compatible adapter under its config name. Cloudflare is configured purely from `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_WORKERS_AI_TOKEN`.
**Alternatives**:
- A bespoke `CloudflareProvider` class (duplicates the OpenAI adapter)
- Repoint the existing `openai` provider's base_url (would replace real OpenAI — can't run both)
**Consequences**: Any OpenAI-compatible host (Cloudflare, Groq, Together, OpenRouter, AI Gateway) works by config alone. GLM-5.2 runs alongside the existing panel.
**References**: `tasks/2026-06/260622_cloudflare-glm-provider.md`, `src/duh/providers/openai.py`

---

## 2026-06-22: One Shared ConsensusReport for Live and History Views

**Status**: Approved (implemented)
**Context**: The live view and the stored-thread view rendered the decision differently, and history couldn't show the executive summary (the thread-detail API never returned the overview).
**Decision**: `ThreadDetailResponse` returns `overview`; a shared `ConsensusReport` component renders the decision block (meters, Copy/Export at top, executive-overview-first with the full decision in a disclosure, dissent) for both `ConsensusComplete` and `ThreadDetail`. Export differs per-view via an `exportSlot` (store-based dropdown live; shared `ExportMenu` for stored threads).
**Alternatives**:
- Keep two displays (the divergence the user objected to)
- Force the live view to build a `ThreadDetail` object to reuse `ExportMenu` (awkward — no turns/contributions mid-run)
**Consequences**: Identical rendering across both contexts; history finally shows the executive summary. Export stays per-view but in the same position.
**References**: `tasks/2026-06/260622_unified-consensus-report.md`, `web/src/components/consensus/ConsensusReport.tsx`
