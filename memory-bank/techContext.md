# Technical Context

**Last Updated**: 2026-10-29

---

## Language: Python

**Rationale**: Every major LLM provider has a first-class Python SDK:
- `anthropic` — Claude (Anthropic)
- `openai` — GPT, o-series (OpenAI)
- `google-genai` — Gemini (Google)
- `mistralai` — Mistral
- `cohere` — Command R (Cohere)
- Local providers (Ollama, LM Studio, vLLM) mostly expose OpenAI-compatible APIs

Python's `asyncio` handles the parallel API call pattern (fan out to multiple models, await all, synthesize). The bottleneck is network latency, not CPU — Python is plenty fast for this.

Rust was considered for single-binary distribution, but the SDK ecosystem is thin. You'd be hand-rolling HTTP clients against every provider's REST API. Maintenance burden not justified.

## Distribution: Docker

**Rationale**: "Install anywhere" without fighting Python packaging. User runs `docker run duh` and they're up. Works on home servers, cloud VMs, Raspberry Pi.

Secondary distribution options (future):
- `pipx` / `uv` for Python-native users
- PyInstaller for single binary (if demand exists)

## Database: SQLAlchemy

**Rationale**: Abstracts the storage backend. User sets a connection string in config:
- `sqlite:///duh.db` — default, zero-config, local
- `postgresql://user:pass@host/db` — scale path, managed hosting
- `mysql://user:pass@host/db` — alternative scale path

Migrations via Alembic. Schema changes don't require changing the database engine.

### Alembic Migrations (v0.3)

- `001_v01_baseline.py` — Thread, Turn, Contribution, TurnSummary, ThreadSummary, Decision tables
- `002_v02_schema.py` — Outcome, Subtask tables; taxonomy fields on Decision (domain, category, tags, complexity)
- `003_v02_votes.py` — Vote table for voting protocol persistence
- `004_v03_api_keys.py` — APIKey table for REST API authentication

## CLI UI: Rich / Textual

**Rationale**: Python's `rich` library provides live terminal output — progress bars, parallel task display, streaming. Translates directly to web interface concepts later. `textual` for more complex TUI if needed.

Target CLI experience:
```
Task: Design auth system for mobile app

| PROPOSE ────────────────────────────────
| Proposer: Claude Opus 4.6
| ████████████░░ generating...
└─────────────────────────────────────────

| CHALLENGE (parallel) ───────────────────
| GPT-5.2      ████████████████ done
| Gemini 3 Pro ██████████░░░░░ generating...
| Mistral Large ███████████████ done
└─────────────────────────────────────────

Round 1/3 · 3 models engaged · $0.04 spent
```

## Provider Adapters: Plugin Architecture

**Rationale**: One adapter per provider. Common interface: send prompt, get response, stream tokens. The consensus engine doesn't know or care which provider responded.

Most local providers already speak the OpenAI-compatible API, so the Ollama/LM Studio adapter may just be the OpenAI adapter pointed at a different URL.

## Local Model Protocol: OpenAI-Compatible API

**Rationale**: Ollama, LM Studio, vLLM, text-generation-inference all expose this. One adapter covers most local providers.

## Tool Framework (v0.2)

**Rationale**: Consensus reasoning benefits from grounding in real-world data (web search), code verification (execution), and document access (file read).

- **Tool protocol**: Python `Protocol` class (`src/duh/tools/base.py`) — structural typing, consistent with provider pattern
- **ToolRegistry**: Register tools by name, lookup, list available tools (`src/duh/tools/registry.py`)
- **tool_augmented_send**: Loop that sends to provider, detects tool_calls, executes tools, re-sends with results (`src/duh/tools/augmented_send.py`)
- **Implementations**:
  - `web_search.py` — DuckDuckGo search via `duckduckgo-search>=7.0` package
  - `code_exec.py` — asyncio subprocess execution with timeout and output truncation
  - `file_read.py` — safe file reading with path traversal rejection, binary rejection, 100KB max

## Frontend: React 19 + Vite 6 + Tailwind 4 (v0.4)

**Rationale**: Modern React with latest tooling. Vite for fast builds and HMR. Tailwind for utility-first CSS without custom build complexity.

### Frontend Stack

- **React 19** — latest stable, concurrent features
- **Vite 6** — build tool + dev server with HMR, API proxy for development
- **Tailwind 4** — utility CSS via `@tailwindcss/vite` plugin
- **TypeScript** — strict mode, path aliases (`@/`)
- **Zustand 5** — lightweight state management (4 stores: consensus, threads, decision-space, preferences)
- **Three.js / React Three Fiber** — 3D Decision Space visualization (lazy-loaded, code-split)
- **@react-three/drei** — R3F helpers (Html overlay, camera controls)
- **react-router-dom 7** — client-side routing (6 pages)
- **Vitest 3** + @testing-library/react — component and store testing
- **react-markdown** + remark-gfm + rehype-highlight — markdown rendering in LLM output
- **highlight.js** — code syntax highlighting (github-dark-dimmed theme, light mode overrides)
- **mermaid** — diagram rendering (lazy-loaded via dynamic `import()`, 498KB separate chunk)

### Frontend Architecture

- `web/src/theme/duh-theme.css` — 22 CSS custom properties (dark default + light via `prefers-color-scheme`) + `.theme-dark`/`.theme-light` manual overrides
- `web/src/theme/animations.css` — keyframes, utility classes, `.duh-prose` markdown typography
- `web/src/api/` — typed fetch client + ConsensusWebSocket class
- `web/src/stores/` — Zustand stores with actions (consensus drives WebSocket state machine)
- `web/src/components/` — shared, layout, consensus, threads, decision-space, preferences
- `web/src/pages/` — route-level components
- `web/src/hooks/` — custom hooks (useMediaQuery)

### Frontend Build

- Vite builds to `web/dist/` (sourcemaps enabled)
- Main bundle: ~617KB (gzip: ~189KB) — includes react-markdown + highlight.js
- Three.js chunk: ~873KB lazy-loaded only on Decision Space page (gzip: ~235KB)
- Mermaid chunk: ~498KB lazy-loaded only when ```mermaid code blocks are rendered (gzip: ~139KB)
- FastAPI mounts `web/dist/` as static files with SPA fallback route
- Docker: Node.js 22 build stage copies dist/ to runtime image

## Native Provider Web Search (2026-03-08)

**Rationale**: DuckDuckGo proxy returned index pages, not real content. Major providers now offer server-side search with higher quality results and extractable citations.

- `web_search: bool` param on `ModelProvider.send()` protocol
- `config.tools.web_search.native` flag (default: true)
- Per-provider implementation:
  - **Anthropic**: `web_search_20250305` server tool in tools[] — skip generic→native transform for entries with `type` key
  - **Google**: `GoogleSearch()` grounding replaces function tools (can't coexist with `function_declarations`)
  - **Mistral**: native search is not advertised on this chat adapter; registered generic web search remains available
  - **OpenAI**: `web_search_options={}` only for `_SEARCH_MODELS` set; standard models fall back to DDG
  - **Perplexity**: no-op (always searches natively)
- `tool_augmented_send`: removes generic search only when the selected model actually supports native search; otherwise retains fallback search

## Citations (2026-03-08)

**Rationale**: Native web search returns structured citation data. Surfacing sources improves trust and verifiability.

- `Citation` dataclass (url, title, snippet) on `ModelResponse.citations`
- Extraction per provider:
  - **Anthropic**: `web_search_tool_result` blocks → `web_search_result` entries
  - **Google**: `candidate.grounding_metadata.grounding_chunks[].web` → uri/title
  - **Perplexity**: `response.citations` list (strings or objects)
- WebSocket: `phase_complete` (PROPOSE) and `challenge` events include `citations` array
- Frontend: `CitationList` shared component (numbered deduped links, hostname fallback), `ConsensusNav` collapsible Sources

## Question Refinement (2026-03-08)

**Rationale**: Ambiguous or underspecified questions produce low-quality consensus. A pre-consensus refinement step catches missing context.

- `src/duh/consensus/refine.py` — `analyze_question()` + `enrich_question()`
- Uses most expensive configured model (quality matters more than cost for a single call)
- API: `POST /api/refine`, `POST /api/enrich`
- CLI: `duh ask --refine "question"` (default `--no-refine`)
- Frontend: consensus store `'refining'` status → `RefinementPanel.tsx` (tabbed UI, Skip button)
- Graceful fallback: any failure → proceed with original question

## Anthropic Streaming Internals (2026-03-08)

**Rationale**: Anthropic SDK requires streaming for requests that may exceed 10 minutes. With `max_tokens=32768`, non-streaming `messages.create()` hit this limit.

- `AnthropicProvider.send()` now calls `_collect_stream()` internally
- Uses `messages.stream()` context manager → `get_final_message()` returns identical `Message` object
- All downstream parsing (citations, tool calls, text blocks) unchanged
- Test mocks must mock `messages.stream` (async context manager), not `messages.create`

## Parallel Challenge Streaming (2026-03-08)

**Rationale**: Challengers ran in parallel but results were batched. Users saw nothing until the slowest challenger responded.

Updated by the approved 2026-10-29 consolidation:
- `src/duh/consensus/handlers.py:523` is the shared challenge implementation, using completion-order callbacks and cancellation/drain on fatal errors.
- Typed engine events let consumers forward individual results immediately while archived rounds retain input selection order.
- Transport-specific `_stream_challenges` helpers remain compatibility adapters; current engine tests patch the shared handler.

## Key Technical Patterns

### Async-First
Everything is `async`/`await`. Model calls, database operations, network requests. The consensus loop fans out to multiple models in parallel and collects responses.

### State Machine for Consensus
The protocol (DECOMPOSE -> PROPOSE -> CHALLENGE -> REVISE -> COMMIT -> NEXT) is a state machine with well-defined transitions, inputs, and outputs per state.

### Voting Protocol (v0.2)
Parallel fan-out to all models, independent responses, majority/weighted aggregation. NOT a state machine — simpler architecture for factual/preference tasks. Auto-classification selects consensus vs voting via `classify_task_type()`.

### Decomposition Protocol (v0.2)
DECOMPOSE state produces `SubtaskSpec` DAG. `schedule_subtasks()` uses `TopologicalSorter` for parallel execution respecting dependencies. `synthesize()` merges results with merge/prioritize strategies.

### Summary Generation
Turn and thread summaries generated by fast/cheap model (Haiku-class or local) after each turn. Thread summary regenerated (not appended) to stay coherent. Raw data always preserved in database.

### Context Window Management
Pass thread summary + recent raw turns + current task context to models each round. Don't pass full history — it exceeds context windows and wastes tokens.

### WebSocket Streaming (v0.3 + v0.4)
The shared engine emits typed phase/challenge/round/completion events. `src/duh/api/routes/ws.py:120` translates them to the established `phase_start`, `phase_complete`, `challenge`, `challenge_error`, `commit`, and `complete` messages. The frontend parses these messages and drives Zustand state transitions.

### Embedded Frontend (v0.4)
React app built by Vite to `web/dist/`, served by FastAPI as static files. SPA fallback route serves `index.html` for client-side routing. No separate frontend server in production — single origin for API and UI.

## Decided (v0.4)

- **Project structure**: `src/duh/` with cli/, consensus/, providers/, memory/, config/, core/, tools/, api/, mcp/ + `web/` with src/, theme, api, stores, components, pages
- **Testing**: pytest + pytest-asyncio + pytest-cov (1641 tests), Vitest + @testing-library/react (194 tests), asyncio_mode=auto
- **CI/CD**: GitHub Actions (lint, typecheck, test) + docs deployment to GitHub Pages
- **Provider interface**: `typing.Protocol` (structural typing), stateless adapters
- **Provider search**: native search follows model capability; unsupported models retain configured generic search fallback. Mistral chat does not advertise native web search.
- **Memory schema**: SQLAlchemy ORM — Thread, Turn, Contribution, TurnSummary, ThreadSummary, Decision, Outcome, Subtask, Vote, APIKey
- **Configuration**: TOML with Pydantic validation, layered merge (defaults < user < project < env < CLI)
- **Error handling**: DuhError hierarchy with ProviderError, ConsensusError, ConfigError, StorageError
- **Tool framework**: Tool protocol + ToolRegistry + tool_augmented_send, 3 built-in tools
- **Voting**: Parallel fan-out + majority/weighted aggregation, TaskType auto-classification
- **Decomposition**: DECOMPOSE state, TopologicalSorter scheduler, merge/prioritize synthesis
- **Taxonomy**: Classification at COMMIT time via structured output, domain/category/tags/complexity
- **Outcome tracking**: Feedback CLI, outcome context injection in future rounds
- **REST API**: FastAPI app factory, API key auth + rate limiting, 10 endpoints + WebSocket
- **MCP server**: Direct Python calls (no REST dependency), 3 tools (duh_ask, duh_recall, duh_threads)
- **Python client**: `duh-client` package in `client/`, async httpx + sync wrappers
- **Web UI**: React 19 + Vite 6 + Tailwind 4 + Three.js, embedded in FastAPI, 6 pages
- **State management**: Zustand 5 with persist middleware for preferences
- **3D visualization**: Three.js via R3F, InstancedMesh point cloud, code-split lazy loading
- **Design system**: 22 CSS custom properties with dark/light mode, glassmorphism, 9+ animation keyframes
- **Markdown rendering**: react-markdown + remark-gfm + rehype-highlight in `Markdown` shared component
- **Light/dark mode**: `prefers-color-scheme` auto-detection + `.theme-dark`/`.theme-light` manual override classes
- **Documentation**: MkDocs Material, deployed to GitHub Pages
- **~63 Python source files + ~81 frontend source files**, mypy strict clean, ruff clean, 0 TS errors
- **Question refinement**: pre-consensus clarification step (analyze → clarify → enrich → consensus)
- **Native web search**: per-provider server-side search with citation extraction
- **Citations**: `Citation` dataclass, `CitationList` component, ConsensusNav Sources sidebar
- **Tools by default**: web_search enabled across CLI/REST/WS paths

## Dependencies

### Python (pyproject.toml)
- `anthropic>=0.40.0` — Anthropic Claude SDK
- `openai>=1.50.0` — OpenAI SDK (also covers Ollama)
- `google-genai>=1.0` — Google Gemini SDK
- `mistralai>=1.0` — Mistral SDK
- `sqlalchemy[asyncio]>=2.0` — ORM + async support
- `aiosqlite>=0.20.0` — async SQLite driver
- `alembic>=1.13` — database migrations
- `rich>=13.0` — terminal UI
- `click>=8.1` — CLI framework
- `pydantic>=2.0` — config validation
- `pydantic-settings>=2.0` — env var loading
- `duckduckgo-search>=7.0` — web search tool
- `fastapi>=0.115` — REST API framework
- `uvicorn[standard]>=0.30` — ASGI server
- `mcp>=1.0` — MCP server SDK
- `httpx>=0.27` — async HTTP client

### Frontend (web/package.json)
- `react` ^19.2, `react-dom` ^19.2 — UI framework
- `react-router-dom` ^7.13 — client-side routing
- `three` ^0.172, `@react-three/fiber` ^9.5, `@react-three/drei` ^10.7 — 3D rendering
- `zustand` ^5.0 — state management
- `tailwindcss` ^4.1, `@tailwindcss/vite` ^4.1 — utility CSS
- `vite` ^6.4, `@vitejs/plugin-react` ^4.7 — build tooling
- `typescript` ^5.9 — type checking
- `vitest` ^3.2, `@testing-library/react` ^16.3, `@testing-library/jest-dom` ^6.9, `happy-dom` ^20.6 — testing
- `react-markdown`, `remark-gfm`, `rehype-highlight` — markdown rendering
- `highlight.js` — code syntax highlighting
- `mermaid` — diagram rendering (lazy-loaded)

## Not Yet Decided

- Network protocol for federated sharing (post-1.0)
- Vector search solution for SQLite (v1.0)
- Client library packaging: monorepo `client/` dir vs separate repo
- MCP server transport: stdio vs SSE vs streamable HTTP
- Playwright E2E test setup

## Security Foundation (2026-10-29)

- App composition: `src/duh/api/app.py:41` provides explicit engine/frontend/diagnostic/middleware switches; CORS wraps authentication; static paths are resolved and contained.
- Authentication: `src/duh/api/auth.py:139` validates HTTP/WS credentials against active users/API keys. WebSocket work starts after the bounded authentication frame.
- Provider calls: `src/duh/providers/base.py:24` bounds retries and response collection; `src/duh/providers/base.py:43` drains sibling work on fatal errors. Provider configuration exposes `timeout_seconds` (default 120).
- Utility output: existing adapters accept an explicit closed JSON schema in `response_format`; Anthropic requires a schema rather than the unconstrained string mode.
- File reads: `tools.file_read_allowed_dir` must be configured before registration at `src/duh/cli/app.py:235`.
- Reset links: `auth.public_base_url` or `DUH_PUBLIC_BASE_URL` supplies the trusted origin; password resets bind to the current password hash and use a conditional update.
- Container: build and runtime environments use `/app/.venv` with a non-editable installation. npm wrappers no longer auto-install or execute an unrelated registry package.
- Status: source and documentation included in the authorized feature-branch commit; not deployed. See `tasks/2026-10/261029_security-foundation.md`.

## Memory Bank Privacy Policy

Record public interfaces, implementation patterns, verified checks, and remaining work. Never copy credentials, personal contact details, local account identifiers, machine addresses, connection strings with real values, or restricted downstream implementation into this Memory Bank. Use repository-relative paths and clearly marked examples. Keep approved-on-branch status distinct from publication or deployment.

## Shared Engine and Run-Scoped Usage (2026-10-29)

- Public API: `src/duh/consensus/engine.py:35` defines immutable EngineOptions; `src/duh/consensus/engine.py:64` defines the typed result. `run_consensus` at line 237 awaits typed event sinks; `stream_consensus` at line 422 exposes bounded asynchronous iteration with worker cancellation/drain on close.
- Consumers: CLI, REST, WebSocket, MCP, and scheduler use that shared loop. `src/duh/cli/app.py:276` preserves the existing eight-tuple return interface. `src/duh/memory/persist.py:37` owns the common incremental-storage adapter; the core does not own rendering or storage.
- Usage scopes: `src/duh/providers/manager.py:165` creates execution-local ContextVar ledgers. Nested calls reuse the owning budget; child scopes measure subtasks separately while charging the parent. Concurrent independent requests do not inherit each other's totals.
- Telemetry compatibility: total_cost/input/output and per-provider cost read the active scope when present, and cumulative telemetry otherwise. aggregate_usage explicitly exposes cumulative totals. Resetting usage during an active run is rejected.
- Refinement: `src/duh/cli/app.py:595` keeps refinement and consensus/voting/auto/decomposition in one event loop, provider manager, ledger, and hard budget; final costs include the preliminary calls.
- Framing validation: `src/duh/config/schema.py:30` constrains configured challenge keys; `src/duh/consensus/handlers.py:515` validates execution overrides before provider work. Supported keys are flaw, alternative, risk, and devils_advocate.
- Contribution identity: `src/duh/consensus/machine.py:37` and `src/duh/consensus/engine.py:50` carry occurrence identity so repeated model/framing calls retain measured usage despite out-of-order completion.
- Failure boundaries: awaited event-sink errors and thread-created callback errors abort execution. Iteration shutdown drains owned tasks; configured provider deadlines and fatal error propagation remain in effect.
- Validation: 1,733 Python tests passed (12 load tests excluded), mypy for 65 source files, Ruff/formatting, and Docker smoke on Python 3.11 passed. Coverage was not remeasured; frontend source is unchanged by this batch.
- Status: source `0a4dc9f` approved for rollout; APPLY IN PROGRESS, deployment verification pending. See `tasks/2026-10/261029_shared-engine.md`.
