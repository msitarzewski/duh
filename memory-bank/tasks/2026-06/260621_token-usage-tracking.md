# 260621_token-usage-tracking

## Objective
Surface per-run token usage (input/output tokens + cost) end-to-end — from the
provider manager through all three persistence paths, the REST/WS/thread-detail
APIs, and the web UI — and verify the `npm/like-duh` CLI wrapper works.

## Outcome
- ProviderManager now accumulates `total_input_tokens` / `total_output_tokens`
  alongside `total_cost`, reset together in `reset_cost()`
- Token usage exposed on `AskResponse`, the WS `complete` event, and
  `ThreadDetailResponse`
- **Thread-level `usage_json` total** persisted across all three persistence
  paths (REST `_persist_result`, WS `_persist_consensus`, CLI `persist_consensus`)
  — fixes stored thread usage always reading 0 (RoundResult carries no
  per-contribution token counts, so the per-contribution sum was always 0)
- Thread detail prefers stored `usage_json` over the per-contribution sum,
  falling back gracefully for threads saved before the column existed
- Frontend `CostTicker` renders `↑input ↓output` token counts; wired through
  `ConsensusPanel`, `ConsensusComplete`, and `ThreadDetail` header
- `npm/like-duh` wrapper verified end-to-end (resolves Python `duh` CLI via
  DUH_PATH → PATH → uvx → pipx)
- 1657 Python + 204 Vitest tests passing, mypy clean (62 files), ruff clean,
  frontend build clean

## Files Modified
- `src/duh/providers/manager.py` — `_total_input_tokens` / `_total_output_tokens`
  accumulators, `total_input_tokens` / `total_output_tokens` properties,
  accumulation in `record_usage`, reset in `reset_cost`
- `src/duh/api/routes/ask.py` — `UsageResponse` model, `usage` on `AskResponse`,
  `usage` param on `_persist_result` writing `thread.usage_json`
- `src/duh/api/routes/threads.py` — `UsageSummary` model, `usage` on
  `ThreadDetailResponse`, `_build_thread_detail` prefers stored `usage_json`
- `src/duh/api/routes/ws.py` — `usage` in complete event + `_persist_consensus`
  writes `thread.usage_json`
- `src/duh/cli/app.py` — `persist_consensus` accepts + writes `usage`
- `src/duh/memory/models.py` — `usage_json` TEXT column on Thread
- `src/duh/memory/migrations.py` — `ensure_schema` ALTERs threads to add
  `usage_json`
- `web/src/api/types.ts` — `Usage` interface; optional `usage` on AskResponse,
  WSComplete, ThreadDetail
- `web/src/stores/consensus.ts` — `usage` state, init, reset, complete handler
- `web/src/components/consensus/CostTicker.tsx` — optional token render
- `web/src/components/consensus/ConsensusPanel.tsx` — passes usage through
- `web/src/components/consensus/ConsensusComplete.tsx` — `usage` prop
- `web/src/components/threads/ThreadDetail.tsx` — usage in header

## Files Created
- `npm/like-duh/` — npm wrapper (package.json, bin/like-duh.mjs,
  lib/{constants,resolver,installer}.mjs, README.md)

## Tests Added
- `tests/unit/test_provider_manager.py` — token accumulation + reset-clears-tokens
- `tests/unit/test_api_threads.py` — usage aggregation + prefers-stored-usage_json
- `tests/unit/test_api_ws.py` — usage in complete event
- `tests/unit/test_api_ask.py` — `TestPersistResult` (usage_json written / null)
- `web/src/__tests__/stores.test.ts` — complete-event usage via captured onEvent
- `web/src/__tests__/consensus-components.test.tsx` — CostTicker usage render

## Patterns Applied
- `usage_json` mirrors the `followups_json` thread-column + ensure_schema pattern
- SQLite auto-migration via `ensure_schema()` ALTER (separate from Alembic)
- Run-level total chosen over per-contribution counts because RoundResult does
  not carry token counts per contribution

## Integration Points
- `ProviderManager.record_usage` accumulates; all three persistence paths read
  `pm.total_input_tokens` / `pm.total_output_tokens` / cost at COMPLETE
- `_build_thread_detail` reads `thread.usage_json` for GET /api/threads/{id}
- Frontend `CostTicker` consumes optional `usage` from store + thread detail

## Verification
- Live API query (thread 37592e86): response, GET thread detail, and raw DB
  `usage_json` all showed matching input/output/cost — confirms the fix writes
  and reads back correctly

## Known Follow-up (Not Addressed)
- No durable/incremental persistence: a mid-run crash still loses the whole
  consensus (single write at COMPLETE). Design proposal offered; not requested.
