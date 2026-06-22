# Active Context

**Last Updated**: 2026-06-22
**Current Phase**: Catalog refresh + tooling, incremental persistence, Cloudflare/GLM provider, unified report — all merged to main (PRs #16–#21)
**Next Action**: Continue feature work or address open questions

## Latest Work (2026-06-22) — PRs #16–#21

### Model Catalog Refresh + Refresh Tool (PR #16 catalog, #19)
- Added frontier models (Opus 4.8/4.7, GPT-5.5, GPT-5.4 mini, Gemini 3.5 Flash); dropped deprecated o3
- Fixed GA context windows (Opus 4.6 + Sonnet 4.6 → 1M; Sonnet 4.5 stays 200k — its 1M is beta-gated)
- **Temperature sets** (the recurring gotcha): `NO_TEMPERATURE_MODELS` (OpenAI) gained `gpt-5.5`;
  new `ANTHROPIC_NO_TEMPERATURE_MODELS` (Opus 4.8/4.7) fixed a production 400. `AnthropicProvider`
  omits `temperature` for those in `send`/`stream`. The OpenAI no-temp set is coupled to
  `_REASONING_EFFORT_MODELS` (effort=high forces temperature=default).
- `scripts/refresh_catalog.py` — propose-only drift detector: diffs catalog vs truefoundry feed +
  live APIs, hashes a per-model projection (`scripts/catalog_snapshot.json`), discovers new models,
  and empirically probes OpenAI + Anthropic temperature. **Feed is reliable for price, wrong for behavior.**

### Incremental Persistence + REST Unification (PR #16 persist, #17)
- New `src/duh/memory/persist.py` `IncrementalPersister`: create thread `active` up front →
  `persist_round()` commits each finished round → `finalize()` marks `complete` + attaches
  overview/followups/usage. Mid-run crash leaves a real partial thread instead of nothing.
- `ConsensusContext.snapshot_round()` extracted from `_archive_round`
- WS streams `thread_started` (real id) early for mid-run deep-linking
- REST `/api/ask` now persists the **full** debate via the shared path (was lite/decision-only);
  `_run_consensus` gained an additive `on_thread_created` callback — 8-tuple return unchanged
- 3 duplicated persist paths consolidated into the one module

### Cloudflare Workers AI + Zhipu GLM-5.2 (PR #18)
- `cloudflare` provider via Workers AI's OpenAI-compatible endpoint; `@cf/zai-org/glm-5.2` in catalog
  (262k ctx, $1.40/$4.40 per Mtok)
- `OpenAIProvider` generalized with optional `provider_id` → serves any OpenAI-compatible host
- `.env`: `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_WORKERS_AI_TOKEN` → loader builds the base URL
- Live-validated (text + JSON mode); shows in `duh models`

### Unified Consensus Report + Overview in History (PR #20, #21)
- Copy/Export moved to top of report; dropdown downward + opaque + click-outside
- `ThreadDetailResponse` now returns `overview` (history previously couldn't show the executive summary)
- New shared `ConsensusReport` component renders **both** live (`ConsensusComplete`) and history
  (`ThreadDetail`) identically; export per-view via an `exportSlot`
- Markdown parity confirmed (same `<Markdown>`; `.duh-prose` has no own font-size)

### End-of-session state
- **1677 Python + 204 Vitest tests**, mypy clean (63 files), ruff clean, build clean
- **Open follow-ups**: (1) self-healing temperature retry as a cross-provider safety net (this bug
  hit twice: gpt-5.5, then Opus 4.8); (2) gitignore `web/tsconfig.tsbuildinfo` (tracked build artifact)

---

## Prior Work (2026-06-21)

### Token Usage Tracking (end-to-end)
- `ProviderManager` accumulates `total_input_tokens` / `total_output_tokens` alongside `total_cost`, all reset in `reset_cost()`
- Token usage exposed on `AskResponse`, WS `complete` event, and `ThreadDetailResponse`
- **Thread-level `usage_json` total** persisted across all three persistence paths (REST `_persist_result`, WS `_persist_consensus`, CLI `persist_consensus`)
  - Fixes stored thread usage always reading 0 — `RoundResult` carries no per-contribution token counts, so the per-contribution sum was always 0
- `_build_thread_detail` prefers stored `usage_json`, falls back to per-contribution sum for threads saved before the column existed
- `usage_json` TEXT column on Thread model + `ensure_schema()` auto-migration (mirrors `followups_json` pattern)
- Frontend `CostTicker` renders `↑input ↓output` token counts; wired through `ConsensusPanel`, `ConsensusComplete`, and `ThreadDetail` header
- `npm/like-duh` CLI wrapper verified end-to-end (resolves Python `duh` via DUH_PATH → PATH → uvx → pipx)
- Verified live (thread 37592e86): response, GET thread detail, and raw DB `usage_json` all matched
- 1657 Python + 204 Vitest tests passing, mypy clean (62 files), ruff clean, build clean
- **Known follow-up (not addressed)**: no durable/incremental persistence — mid-run crash still loses the whole consensus (single write at COMPLETE)

---

## Prior Work (2026-03-20)

### Thread Detail View — Consensus Parity
- Replaced `TurnCard` with `PhaseCard` in `ThreadDetail.tsx` — rounds now render PROPOSE/CHALLENGE/REVISE phases matching the live consensus view
- Added `turnToPhaseData()` helper to transform `Turn.contributions` (grouped by `role`) into PhaseCard props
- `ThreadNav.tsx` upgraded to phase-level navigation: PROPOSE, individual challenger model names, REVISE per round (was round-level only)
- Header renamed from "ROUNDS" to "PROGRESS" matching `ConsensusNav`
- Feedback section moved from bottom to right after decision block
- Scroll anchor IDs: `thread-round-N-propose`, `thread-round-N-challenge`, `thread-round-N-revise`
- `TurnCard` still exists but no longer used in production code

### PDF Export Overhaul
- **Cover page**: centered "duh." brand (36pt cyan) + "consensus engine" subtitle, quoted question (italic, curly quotes), centered metadata
- **Table of Contents**: own page, dark header bar, dot leaders, clickable cyan page numbers linking to sections
- **Section headers**: colored background bars with white text (Decision=green, Dissent=amber, Consensus Process=gray, Sources=gray-blue)
- **Phase-grouped contributions**: PROPOSE (green accent), CHALLENGE (amber accent), REVISE (blue accent) — each with phase label + provider-colored model ref
- **Confidence/rigor meters**: labeled progress bars with colored fills (green for confidence, cyan for rigor)
- **Sources section**: consolidated at end of document, numbered, with clickable URL links and hostname display
- **Page break**: Decision/Dissent on initial pages, Consensus Process starts on new page
- **TOC overflow fix**: TOC renders on dedicated page to prevent fpdf2 page-count mismatch

### Server & UI Fixes
- `_create_db()`: file-based SQLite now runs `Base.metadata.create_all()` before `ensure_schema()` — fixes crash on fresh databases with no tables
- `ensure_schema()`: `_get_columns()` returns `None` for missing tables, all migration blocks skip gracefully
- `ExportMenu` dropdown: opaque `--color-surface-solid` background (was transparent `--glass-bg`), hover state uses `--color-surface-hover` (was undefined `--color-bg-tertiary`)
- Thread header `GlassPanel`: `relative z-10` + opaque background so export dropdown renders above sibling Decision panel

### Test Updates
- `thread-nav.test.tsx`: "ROUNDS"→"PROGRESS", new phase-level entry test, updated empty-contributions test
- All 1652 Python + 199 Vitest tests passing

---

## Prior Work (2026-03-09)

### Follow-up Questions (new end-to-end feature)
- `generate_followups()` in `src/duh/consensus/handlers.py:930` — uses cheapest model with JSON mode to suggest 3 follow-up questions after consensus completes
- Prompt asks for different angles: deeper technical detail, practical implications, risks/edge cases, related decisions
- `followups` field added to `ConsensusContext` in `machine.py`
- `_run_consensus` returns 8-tuple now (was 7): `(decision, confidence, rigor, dissent, cost, overview, citations, followups)`
- All callers updated: CLI ask, CLI auto, CLI decompose, CLI batch, REST API, WebSocket, MCP server
- **Persistence**: `followups_json` TEXT column on Thread model + SQLite auto-migration in `ensure_schema()`
- **Thread detail API**: returns `followups` parsed from `followups_json`
- **WebSocket**: sends `followups` in `complete` event, persists via `_persist_consensus`
- **Frontend**: `ConsensusNav` + `ThreadNav` show clickable follow-ups in Disclosure section
  - Clicking a follow-up calls `submitQuestion()` to start a new consensus
  - `consensus.ts` store: `followups` state, included in reset
  - `types.ts`: `followups` on `ThreadDetail` and `WSComplete`

### Revision Citations (enhancement to existing citation system)
- `revision_citations` field added to both `ConsensusContext` and `RoundResult` in `machine.py`
- `handle_revise()` now accepts `tool_registry` + `web_search` params — enables tool-augmented revision with web search
- `handle_revise()` extracts citations from response into `ctx.revision_citations`
- `handle_propose()` now extracts `proposal_citations` directly in handler (moved from ws.py)
- WebSocket sends revision citations in REVISE `phase_complete` event
- `_persist_consensus` saves revision citations to DB as `citations_json` on reviser contribution
- `ConsensusPanel.tsx` passes `revisionCitations` to REVISE phase card
- `ConsensusNav.tsx` includes revision citations in Sources section (role: 'revise')
- `_run_consensus` citation collection now includes revision citations from both round history and current round

### CLI Enhancements
- Top-level `--rounds` and `--challengers` options on `cli()` group cascade to subcommands (subcommand wins if both set)
- `_parse_challengers()` accepts either int count or comma-separated model refs (e.g. `3` or `openai:gpt-5,google:gemini-2.5-pro`)
- `challenger_count` param flows through `_run_consensus` → `select_challengers(count=N)`
- **CLI DB persistence**: new `persist_consensus()` function in `app.py` — CLI `ask` command now persists full consensus round history to DB (proposals, challenges, revisions, citations, decisions, overview, followups)
- `_ask_async` creates DB factory via `_create_db()`, disposes engine in `finally` block
- Top-level `--rounds` also cascades into `batch` subcommand

### Calibration Date Filters (frontend)
- `CalibrationDashboard.tsx`: category dropdown + since/until date inputs + Apply button
- `INTENT_CATEGORIES` constant: `['factual', 'technical', 'creative', 'judgment', 'strategic']`
- `calibration.ts` store: `since`/`until` state + `setSince`/`setUntil` setters, passed to API call
- Store tests: 4 new tests for date filter state and API param passing

### Provider Updates
- **OpenAI**: `_REASONING_EFFORT_MODELS` set (gpt-5, gpt-5-mini, gpt-5-nano, gpt-5.2, gpt-5.4) — sends `reasoning_effort: "high"` when no function tools present (incompatible with tools on /v1/chat/completions)
- **OpenAI**: also sends `reasoning_effort: "high"` in structured output path (`_send_structured`)
- **OpenAI**: `gpt-5.2` added to `NO_TEMPERATURE_MODELS` in `catalog.py`
- **Perplexity**: retry logic for `APIConnectionError` — 2 attempts, 1s delay between retries
- **Perplexity**: `APIConnectionError` mapped to `ProviderTimeoutError`

### Infrastructure
- `alembic/env.py`: `DUH_DATABASE_URL` env var overrides `alembic.ini` — `_resolve_url()` used in offline, online sync, and online async migration paths
- `.gitignore`: `npm/like-duh/node_modules/` added

### Test Updates
- All test files updated for 8-tuple `_run_consensus` return value
- `test_cli_display.py`: new `TestShowCitations` class (8 tests — empty, single, dedup, grouping, sort, title fallback, no-url skip, numbered)
- `test_cli_display.py`: new `TestShowFinalDecisionOverview` class (2 tests — shows/hides overview panel)
- `test_cli_tools.py`: mock return values corrected from 4-tuple to 8-tuple
- `test_providers_openai.py`: test switched from `gpt-5.2` to `gpt-4o` (since 5.2 now has special reasoning_effort behavior)
- `stores.test.ts`: 4 new calibration date filter tests
- `test_cli_batch.py`, `test_cli_voting.py`, `test_mcp_server.py`: 8-tuple updates

---

## Current State

- **Branch `main`** — all work committed and pushed (through PR #21)
- All previous features intact (v0.1-v0.6, PR #13-#21)
- 1677 Python + 204 Vitest tests passing, mypy clean (63 files), build clean

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) -- v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) -- deferred to post-1.0
- A2A protocol -- deferred to post-1.0
