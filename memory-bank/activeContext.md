# Active Context

**Last Updated**: 2026-03-08
**Current Phase**: `question-refinement` branch — pre-consensus question refinement, native web search, citations, tools-by-default
**Next Action**: Branch in progress, uncommitted changes staged

## Latest Work (2026-03-08)

### Question Refinement
- Pre-consensus clarification step: analyze question → ask clarifying questions → enrich with answers → proceed to consensus
- `src/duh/consensus/refine.py` — `analyze_question()` + `enrich_question()`, uses MOST EXPENSIVE model (not cheapest)
- API: `POST /api/refine` → `RefineResponse{needs_refinement, questions[]}`, `POST /api/enrich` → `EnrichResponse{enriched_question}`
- CLI: `duh ask --refine "question"` — interactive `click.prompt()` loop, default `--no-refine`
- Frontend: consensus store `'refining'` status, `submitQuestion` → refine → clarify → enrich → `startConsensus`
- `RefinementPanel.tsx` — tabbed UI inside GlassPanel, checkmarks on answered tabs, Skip + Start Consensus buttons
- Graceful fallback: any failure → proceed to consensus with original question

### Native Provider Web Search
- Providers use server-side search instead of DDG proxy when `config.tools.web_search.native` is true
- `web_search: bool` param added to `ModelProvider.send()` protocol
- Anthropic: `web_search_20250305` server tool in tools[]
- Google: `GoogleSearch()` grounding (replaces function tools — can't coexist)
- Mistral: `{"type": "web_search"}` appended to tools
- OpenAI: `web_search_options={}` only for `_SEARCH_MODELS` set; others fall back to DDG
- Perplexity: no-op (always searches natively)
- `tool_augmented_send`: filters DDG `web_search` tool when native=True, passes flag to provider

### Citations — Persisted + Domain-Grouped
- `Citation` dataclass (url, title, snippet) on `ModelResponse.citations`
- Extraction per provider: Anthropic (`web_search_tool_result`), Google (grounding metadata), Perplexity (`response.citations`)
- **Persistence**: `citations_json` TEXT column on `Contribution` model, SQLite auto-migration via `ensure_schema()`
- `proposal_citations` tracked on `ConsensusContext` → archived to `RoundResult` → persisted via `_persist_consensus`
- Thread detail API returns `citations` on `ContributionResponse`
- **Domain-grouped Sources nav**: ConsensusNav (live) + ThreadNav (stored) group citations by hostname
  - Nested Disclosure: outer "Sources (17)" → inner "wikipedia.org (3)" → P/C/R role badges per citation
  - P (green) = propose, C (amber) = challenge, R (blue) = revise
- `CitationList` shared component for inline display below content

### Anthropic Streaming + max_tokens
- `AnthropicProvider.send()` now uses streaming internally via `_collect_stream()` — avoids 10-minute timeout
- `max_tokens` bumped from 16384 → 32768 across all 6 handler defaults (propose, challenge, revise, commit, voting, decomposition)
- Citations are part of the value — truncating them undermines trust

### Parallel Challenge Streaming
- `_stream_challenges()` in `ws.py` uses `asyncio.as_completed()` to send each challenge result to the frontend as it finishes
- Previously: all challengers ran in parallel but results were batched after all completed
- Now: first challenger to respond appears immediately in the UI

### Tools Enabled by Default
- `web_search` tool wired through CLI, REST, and WebSocket paths by default
- Provider tool format fix: `tool_augmented_send` builds generic `{name, description, parameters}` — each provider transforms to native format in `send()`

### Sidebar UX
- New-question button (Heroicons pencil-square) + collapsible sidebar toggle
- Shell manages `desktopSidebarOpen` (default true) + `mobileSidebarOpen` separately
- TopBar shows sidebar toggle when desktop sidebar collapsed or always on mobile

### Test Results
- 1641 Python tests + 194 Vitest tests (1835 total)
- Build clean, all tests pass

---

## Current State

- **Branch `question-refinement`** — in progress, not yet merged
- **1641 Python tests + 194 Vitest tests** (1835 total)
- All previous features intact (v0.1–v0.6)
- Prior work merged: z-index fix, GPT-5.4, .env docs, password reset

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred to post-1.0
- A2A protocol — deferred to post-1.0
