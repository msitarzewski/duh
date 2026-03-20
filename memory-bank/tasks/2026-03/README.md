# Tasks — March 2026

## 2026-03-07: Password Reset + .env Support + TopBar Fix
- Password reset flow: forgot password form, SMTP email with JWT reset link, set new password page
- `.env` file support via `python-dotenv` for mail config and JWT secret
- `MailConfig` added to config schema with env var overrides
- TopBar user menu dropdown z-index fix (was clipped by main overflow)
- Stable JWT secret in `.env` for session persistence across server restarts
- Files: `mail.py`, `auth.py`, `schema.py`, `loader.py`, `LoginPage.tsx`, `ResetPasswordPage.tsx`, `TopBar.tsx`
- See: [070307_password-reset.md](./070307_password-reset.md)

## 2026-03-08: Question Refinement + Native Web Search + Citations (PR #13 + #14)
- Pre-consensus question refinement: analyze → clarify → enrich → consensus
- Native provider web search (Anthropic/Google/Mistral/OpenAI/Perplexity)
- Citations: extraction per provider, persistence, domain-grouped Sources nav with P/C/R badges
- Tools enabled by default (web_search wired through CLI, REST, WS)
- Sidebar UX: new-question button + collapsible toggle
- Anthropic streaming + parallel challenge streaming + max_tokens 32768
- README rewrite: repositioned as AI infrastructure, CLI citation display
- `_run_consensus` 7-tuple return (added citations)
- 1641 Python + 194 Vitest tests (1835 total)
- Files: refine.py, handlers.py, machine.py, ws.py, ask.py, threads.py, app.py, all providers, ConsensusNav.tsx, ThreadNav.tsx, CitationList.tsx, RefinementPanel.tsx, consensus.ts, types.ts

## 2026-03-09: Follow-ups + Revision Citations + CLI Persistence + Provider Updates
- **Follow-up questions**: `generate_followups()` — cheapest model, JSON mode, 3 questions post-consensus
  - `followups` on ConsensusContext, `followups_json` on Thread model + migration
  - `_run_consensus` 8-tuple return (added followups), all callers updated
  - Frontend: clickable follow-ups in ConsensusNav + ThreadNav Disclosure, triggers new consensus
- **Revision citations**: `handle_revise()` accepts tool_registry + web_search, extracts citations
  - `revision_citations` on ConsensusContext + RoundResult, persisted to DB
  - `handle_propose()` extracts proposal_citations directly in handler
  - WS sends revision citations in REVISE phase, ConsensusPanel passes to phase card
- **CLI persistence**: `persist_consensus()` saves full round history to DB from CLI
  - `_ask_async` creates DB factory, disposes engine in finally
- **CLI options**: top-level `--rounds`/`--challengers` cascade to subcommands
  - `_parse_challengers()`: int count or comma-separated model refs
- **Calibration filters**: category + since/until date inputs on CalibrationDashboard
- **OpenAI**: `reasoning_effort: "high"` for GPT-5.x (no tools), gpt-5.2 in NO_TEMPERATURE_MODELS
- **Perplexity**: retry for APIConnectionError (2 attempts, 1s delay)
- **Alembic**: `DUH_DATABASE_URL` env var overrides alembic.ini
- Tests: TestShowCitations (8), TestShowFinalDecisionOverview (2), calibration date tests (4), all 8-tuple updates
- Files: handlers.py, machine.py, app.py, ws.py, ask.py, threads.py, models.py, migrations.py, mcp/server.py, openai.py, perplexity.py, catalog.py, alembic/env.py, CalibrationDashboard.tsx, ConsensusNav.tsx, ConsensusPanel.tsx, ThreadNav.tsx, calibration.ts, consensus.ts, types.ts, + 7 test files

## 2026-03-20: Thread View Parity + PDF Overhaul + Server/UI Fixes
- **Thread detail view**: `TurnCard` replaced with `PhaseCard` rendering — PROPOSE/CHALLENGE/REVISE match live consensus view
  - `turnToPhaseData()` helper transforms `Turn.contributions` by role
  - `ThreadNav` upgraded to phase-level navigation (PROPOSE, challenger models, REVISE)
  - Header renamed "ROUNDS" → "PROGRESS", feedback moved to top
- **PDF export overhaul**: branded cover page ("duh." + "consensus engine"), curly-quoted question
  - Styled TOC on dedicated page: dark header bar, dot leaders, clickable cyan page numbers
  - Colored section header bars (Decision=green, Dissent=amber, Consensus Process=gray, Sources=gray-blue)
  - Phase-grouped contributions with PROPOSE/CHALLENGE/REVISE accent colors + provider model refs
  - Labeled confidence/rigor progress bars
  - Consolidated Sources section: numbered clickable URLs with hostname display
  - Page break between Decision/Dissent and Consensus Process
- **Server fix**: `_create_db()` runs `create_all` for fresh file-based SQLite before `ensure_schema()`
- **ensure_schema**: handles missing tables gracefully (`_get_columns` returns `None`)
- **ExportMenu**: opaque dropdown (`--color-surface-solid`), hover uses `--color-surface-hover`
- **Thread header**: `relative z-10` + opaque background for dropdown visibility
- Tests: 1652 Python + 199 Vitest passing
- Files: `app.py`, `migrations.py`, `ThreadDetail.tsx`, `ThreadNav.tsx`, `ExportMenu.tsx`, `thread-nav.test.tsx`, `README.md`

## 2026-03-07: Z-index Fix + GPT-5.4 + .env Docs
- Fixed z-index stacking contexts trapping dropdowns (Shell z-10, TopBar z-20 removed)
- Added CSS z-index tokens (`--z-background`, `--z-dropdown`, `--z-overlay`, `--z-modal`)
- Added `isolate` to Shell root, replaced backdrop hack with click-outside pattern in TopBar
- Added GPT-5.4 to model catalog (1M context, $2.50/$15.00, no-temperature)
- Updated `.env.example` with provider API key placeholders
- Updated README quick start with all provider env vars
- Files: `duh-theme.css`, `Shell.tsx`, `TopBar.tsx`, `GridOverlay.tsx`, `ParticleField.tsx`, `ExportMenu.tsx`, `ConsensusComplete.tsx`, `ThreadDetail.tsx`, `catalog.py`, `.env.example`, `README.md`
- 1603 Python + 185 Vitest tests passing
