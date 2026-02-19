# Active Context

**Last Updated**: 2026-02-19
**Current Phase**: UX cleanup and consensus engine hardening
**Next Action**: PR ready for review.

## What Just Shipped: UX Cleanup + Consensus Engine Improvements

### Thread Detail UX
- All round sections collapsed by default when thread loads — decision stays open
- Dissent inside decision block collapsed by default
- `DissentBanner` gained `defaultOpen` prop for caller control

### Consensus Engine Hardening
- **max_tokens bumped 4096 -> 16384** for propose/challenge/revise phases — prevents LLM output truncation on long responses
- **Token budget in system prompts** — LLMs now told their output budget so they can self-regulate length and end on complete thoughts
- **Truncation detection** — `finish_reason` checked after each handler call; `truncated` flag sent via WebSocket; amber warning shown in PhaseCard UI
- **Cross-provider challenger selection** — `select_challengers()` now prefers models from different providers (one per provider first, then fills). Prevents e.g. Opus proposing + two Sonnet variants challenging (same training biases)

### Visual Polish
- Export dropdown menus (both `ConsensusComplete` and `ExportMenu`) now use glass styling matching the design system (`glass-bg` + `backdrop-blur`)

### PDF Export Bug Fix
- `_setup_fonts()` was missing the bold-italic (`BI`) TTF font variant — caused crash when dissent content contained bold markdown rendered in italic context

### Test Results
- 1586 Python tests + 166 Vitest tests (1752 total)
- Build clean, all tests pass

---

## Current State

- **Branch `ux-cleanup`** — ready for PR.
- **1586 Python tests + 166 Vitest tests** (1752 total).
- All previous features intact (v0.1–v0.5 + export + epistemic confidence + consensus nav).

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred to post-1.0
- A2A protocol — deferred to post-1.0
