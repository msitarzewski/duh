# Active Context

**Last Updated**: 2026-02-18
**Current Phase**: Consensus UX — right-side nav, collapsible sections, decision-first layout
**Next Action**: PR open for review.

## What Just Shipped: Consensus Navigation & Collapsible Sections

### Core Changes
The consensus page and thread detail view now have proper navigation and information hierarchy for multi-round deliberations.

**Before**: Long vertical scroll of rounds with no way to navigate or collapse. Decision buried at the bottom after all rounds.
**After**:
- Sticky right-side nav panel shows progress through rounds/phases
- All sections are independently collapsible via a shared `Disclosure` primitive
- Decision surfaces to the **top** when consensus is complete (both live + stored threads)
- Individual challengers shown by model name in nav and each collapsible
- Dissent gets equal treatment: collapsible `DissentBanner` with model attribution parsed from `[model:name]:` prefix

### New Shared Component: `Disclosure`
Reusable chevron + toggle primitive (`web/src/components/shared/Disclosure.tsx`):
- Props: `header`, `defaultOpen`, `forceOpen`, `className`
- Used by: PhaseCard, TurnCard, ConsensusComplete, DissentBanner, ThreadDetail

### Files Changed (17 files)
**New files:**
- `web/src/components/shared/Disclosure.tsx` — Shared collapsible primitive
- `web/src/components/consensus/ConsensusNav.tsx` — Sticky nav for live consensus
- `web/src/components/threads/ThreadNav.tsx` — Sticky nav for thread detail
- `web/src/__tests__/consensus-nav.test.tsx` — 32 tests (Disclosure, PhaseCard, DissentBanner, TurnCard, ConsensusNav)
- `web/src/__tests__/thread-nav.test.tsx` — 8 tests (ThreadNav)

**Modified:**
- `PhaseCard.tsx` — Uses Disclosure for outer collapse + per-challenger Disclosure
- `TurnCard.tsx` — Uses Disclosure for outer collapse + per-contribution Disclosure
- `ConsensusComplete.tsx` — Collapsible via Disclosure, dissent moved inside panel
- `DissentBanner.tsx` — Uses Disclosure, parses `[model:name]:` prefix for ModelBadge
- `ConsensusPanel.tsx` — Decision at top when complete, scroll target IDs
- `ConsensusPage.tsx` — Flex-row layout with sticky ConsensusNav sidebar
- `ThreadDetail.tsx` — Decision surfaced to top, DissentBanner for dissent, scroll IDs
- `ThreadDetailPage.tsx` — Flex-row layout with sticky ThreadNav sidebar
- Barrel exports: `consensus/index.ts`, `threads/index.ts`, `shared/index.ts`

### Test Results
- 1586 Python tests + 166 Vitest tests (1752 total)
- Build clean, all tests pass

---

## Current State

- **Branch `consensus-nav-collapsible`** — ready for PR.
- **1586 Python tests + 166 Vitest tests** (1752 total).
- **~62 Python source files + 75 frontend source files** (~137 total).
- All previous features intact (v0.1–v0.5 + export + epistemic confidence).

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred to post-1.0
- A2A protocol — deferred to post-1.0
