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
