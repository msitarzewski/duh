# Active Context

**Last Updated**: 2026-02-18
**Current Phase**: Epistemic Confidence (Phase A) — on branch `epistemic-confidence-phase-a`
**Next Action**: Commit, push, create PR to merge to main.

## What Just Shipped: Epistemic Confidence Phase A

### Core Change
Confidence scoring is now **epistemic** — it reflects inherent uncertainty of the question domain, not just challenge quality.

**Before**: `confidence = _compute_confidence(challenges)` — measured rigor only (0.5–1.0 based on sycophancy ratio).
**After**: Two separate scores:
- **Rigor** (renamed from old confidence) — how genuine the challenges were (0.5–1.0)
- **Confidence** — `min(domain_cap(intent), rigor)` — rigor clamped by question type ceiling

### Domain Caps
| Intent | Cap | Rationale |
|--------|-----|-----------|
| factual | 0.95 | Verifiable answers, near-certain |
| technical | 0.90 | Strong consensus possible |
| creative | 0.85 | Subjective, multiple valid answers |
| judgment | 0.80 | Requires weighing trade-offs |
| strategic | 0.70 | Inherent future uncertainty |
| unknown/None | 0.85 | Default conservative cap |

### Files Changed (47 files, +997, -230)
**New files:**
- `src/duh/calibration.py` — ECE (Expected Calibration Error) computation
- `src/duh/memory/migrations.py` — SQLite schema migration (adds rigor column)
- `tests/unit/test_calibration.py` — 15 calibration tests
- `tests/unit/test_confidence_scoring.py` — 20 epistemic confidence tests
- `tests/unit/test_cli_calibration.py` — 4 CLI calibration tests
- `web/src/components/calibration/CalibrationDashboard.tsx` — Calibration viz
- `web/src/pages/CalibrationPage.tsx` — Calibration page
- `web/src/stores/calibration.ts` — Calibration Zustand store

**Modified across full stack:**
- `consensus/handlers.py` — Renamed `_compute_confidence` → `_compute_rigor`, added `_domain_cap()`, `DOMAIN_CAPS`, epistemic formula
- `consensus/machine.py` — Added `rigor` to ConsensusContext, RoundResult
- `consensus/scheduler.py` — Propagates rigor through subtask results
- `consensus/synthesis.py` — Averages rigor across subtask results
- `consensus/voting.py` — Added rigor to VoteResult, VotingAggregation
- `memory/models.py` — Added `rigor` column to Decision ORM
- `memory/repository.py` — Accepts `rigor` param in `save_decision()`
- `memory/context.py` — Shows rigor in context builder output
- `cli/app.py` — All output paths show rigor; new `duh calibration` command; PDF export enhanced
- `cli/display.py` — `show_commit()` and `show_final_decision()` show rigor
- `api/routes/crud.py` — `GET /api/calibration` endpoint; rigor in decision space
- `api/routes/ask.py`, `ws.py`, `threads.py` — Propagate rigor
- `mcp/server.py` — Propagates rigor
- Frontend: ConfidenceMeter, ConsensusComplete, ConsensusPanel, ThreadDetail, TurnCard, ExportMenu, Sidebar, DecisionCloud, stores updated

---

## Current State

- **Branch `epistemic-confidence-phase-a`** — all changes uncommitted, ready to commit.
- **1586 Python tests + 126 Vitest tests** (1712 total), ruff clean, mypy strict clean.
- **~62 Python source files + 70 frontend source files** (~132 total).
- All previous features intact (v0.1–v0.5 + export).

## Next Task: Model Selection Controls + Provider Updates

Deferred from before Phase A. See `progress.md` for details.

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred to post-1.0
- A2A protocol — deferred to post-1.0
