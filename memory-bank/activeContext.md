# Active Context

**Last Updated**: 2026-03-07
**Current Phase**: Post v0.6.0 — z-index fix + GPT-5.4 + .env improvements
**Next Action**: PR ready for review

## Latest Work (2026-03-07)

### Z-index stacking context fix
- **Problem**: Nested stacking contexts (`z-10` on main content, `z-20` on TopBar header) trapped dropdowns inside containers. Account menu's `fixed inset-0 z-40` backdrop was meaningless outside its container.
- **Fix**: Removed unnecessary z-index values creating stacking contexts, added `isolate` to Shell root, defined z-index tokens in CSS (`--z-background`, `--z-dropdown`, `--z-overlay`, `--z-modal`), replaced backdrop hack with `useRef` + `mousedown` click-outside pattern (matching ExportMenu).
- Files: `duh-theme.css`, `Shell.tsx`, `TopBar.tsx`, `GridOverlay.tsx`, `ParticleField.tsx`, `ExportMenu.tsx`, `ConsensusComplete.tsx`, `ThreadDetail.tsx`

### GPT-5.4 added to model catalog
- `gpt-5.4`: 1M context, 128K output, $2.50/$15.00 per MTok, no temperature (uses reasoning.effort)
- Added to `NO_TEMPERATURE_MODELS` set
- File: `src/duh/providers/catalog.py`

### .env improvements
- Added provider API key placeholders to `.env.example` (ANTHROPIC, OPENAI, GOOGLE, PERPLEXITY, MISTRAL)
- Updated README quick start with all provider env vars + `.env` reference
- Note: Google key env var is `GOOGLE_API_KEY` (not `GEMINI_API_KEY`)

### Test Results
- 1603 Python tests + 185 Vitest tests (1788 total)
- Build clean, all tests pass

---

## Current State

- **Branch `ux-cleanup`** — z-index fix, GPT-5.4, .env docs
- **1603 Python tests + 185 Vitest tests** (1788 total)
- All previous features intact (v0.1–v0.6)

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred to post-1.0
- A2A protocol — deferred to post-1.0
