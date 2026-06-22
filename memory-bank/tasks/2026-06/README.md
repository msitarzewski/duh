# Tasks — June 2026

## 2026-06-21: Token Usage Tracking + npm Wrapper
- ProviderManager accumulates `total_input_tokens` / `total_output_tokens` (reset with cost)
- Token usage surfaced on `AskResponse`, WS `complete` event, `ThreadDetailResponse`
- **Thread-level `usage_json` total** persisted across all three persistence paths
  (REST `_persist_result`, WS `_persist_consensus`, CLI `persist_consensus`) — fixes
  stored thread usage always reading 0 (RoundResult carries no per-contribution tokens)
- Thread detail prefers stored `usage_json` over per-contribution sum, falls back gracefully
- `usage_json` TEXT column on Thread + `ensure_schema()` auto-migration (mirrors `followups_json`)
- Frontend `CostTicker` renders `↑input ↓output`; wired through ConsensusPanel, ConsensusComplete, ThreadDetail
- `npm/like-duh` CLI wrapper verified end-to-end (DUH_PATH → PATH → uvx → pipx resolution)
- 1657 Python + 204 Vitest tests passing, mypy clean, ruff clean, build clean
- Files: `manager.py`, `ask.py`, `threads.py`, `ws.py`, `app.py`, `models.py`, `migrations.py`,
  `types.ts`, `consensus.ts`, `CostTicker.tsx`, `ConsensusPanel.tsx`, `ConsensusComplete.tsx`,
  `ThreadDetail.tsx`, `npm/like-duh/`, + 6 test files
- See: [260621_token-usage-tracking.md](./260621_token-usage-tracking.md)

## 2026-06-22: Model Catalog Refresh + Refresh Tool + Temperature Fixes (PR #16 catalog, #19)
- Frontier models added (Opus 4.8/4.7, GPT-5.5, GPT-5.4 mini, Gemini 3.5 Flash); dropped deprecated o3
- Corrected GA context windows (Opus 4.6 + Sonnet 4.6 → 1M; Sonnet 4.5 stays 200k — beta-gated)
- **Temperature correctness**: `gpt-5.5` no-temp; new `ANTHROPIC_NO_TEMPERATURE_MODELS`
  (Opus 4.8/4.7) fixes a production 400 ("temperature is deprecated for this model")
- `scripts/refresh_catalog.py` (propose-only): diffs catalog vs truefoundry feed + live APIs,
  hashes a per-model projection (`catalog_snapshot.json`), discovers new models, and empirically
  probes OpenAI **and** Anthropic temperature
- Lesson: feed is reliable for pricing, **wrong** for behavior — probe temperature live
- See: [260622_model-catalog-refresh.md](./260622_model-catalog-refresh.md)

## 2026-06-22: Incremental Persistence + REST Unification (PR #16 persist, #17)
- New `memory/persist.py` `IncrementalPersister`: thread created `active` up front → each round
  committed as it finishes → finalized `complete`. A mid-run crash leaves a real partial thread.
- `ConsensusContext.snapshot_round()`; WS streams `thread_started` with the real id early
- REST `/api/ask` now persists the **full** debate via the shared path (was a lite decision-only
  path); `_run_consensus` gained an additive `on_thread_created` callback (8-tuple unchanged)
- Consolidated 3 duplicated persist paths into one module
- See: [260622_incremental-persistence.md](./260622_incremental-persistence.md)

## 2026-06-22: Cloudflare Workers AI + Zhipu GLM-5.2 (PR #18)
- `cloudflare` provider via Workers AI's OpenAI-compatible endpoint; `@cf/zai-org/glm-5.2` in catalog
- Generalized `OpenAIProvider` with an optional `provider_id` → serves any OpenAI-compatible host
  (Groq/Together/OpenRouter/AI Gateway) by config alone
- `.env`-driven: `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_WORKERS_AI_TOKEN`
- Validated live: text + JSON mode work; appears in `duh models`
- See: [260622_cloudflare-glm-provider.md](./260622_cloudflare-glm-provider.md)

## 2026-06-22: Unified Consensus Report + Overview in History (PR #20, #21)
- Copy/Export moved to top of report; dropdown opens downward, opaque, click-outside (#20)
- `ThreadDetailResponse` returns `overview` (history was missing the executive summary)
- New shared `ConsensusReport` component drives **both** live and history views identically
- Markdown parity verified (same shared `<Markdown>`; `.duh-prose` sets no own font-size)
- See: [260622_unified-consensus-report.md](./260622_unified-consensus-report.md)

## 2026-06-22: Temperature Self-Heal (cross-provider safety net)
- New `src/duh/providers/temperature.py`: runtime-learned no-temperature set + helpers
- OpenAI + Anthropic `send()` retry once without `temperature` on a temperature-related 400,
  record the model, and skip it thereafter; `stream()` honors the learned set
- Static catalog sets stay the fast path; this self-corrects unknown/new models
- Live-verified against a real Anthropic 400. Closes the prior open follow-up.
- See: [260622_temperature-self-heal.md](./260622_temperature-self-heal.md)

---
**End-of-session state (2026-06-22)**: 1681 Python + 204 Vitest tests passing, mypy clean
(64 files), ruff clean, build clean. All work merged to `main` via PRs #16–#22 (+ this fix).
