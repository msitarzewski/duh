# 260622_unified-consensus-report

## Objective
Make the live consensus view and the stored-thread (history) view render the
decision identically, surface the executive summary in history, and move the
Copy/Export actions to the top. (PR #20, PR #21.)

## Problem
Two divergent displays. The live view (`ConsensusComplete`) led with the
executive overview; the history view (`ThreadDetail`) led with the raw decision
and **couldn't show the overview at all** — the thread-detail API never returned
it. Copy/Export sat at the bottom with an upward, translucent dropdown that
overlapped the report text.

## Outcome
- **PR #20**: Copy/Export moved to the **top** of the report; dropdown opens
  downward, uses an opaque surface (`--color-surface-solid`), and closes on
  outside-click — matching the shared `ExportMenu`.
- **Backend**: `ThreadDetailResponse` now returns `overview`, sourced from the
  thread's stored summary (already eager-loaded by `get_thread`). This was the
  root cause of history missing the executive summary.
- **New shared `ConsensusReport` component** (`web/src/components/consensus/`):
  meters, Copy/Export at top, executive overview leading with the full decision
  in a "Full Decision" disclosure, and dissent.
- **Both views delegate to it** — `ConsensusComplete` and `ThreadDetail` render
  through the one component. Export stays per-view via an `exportSlot` (live
  passes a store-based dropdown since there's no `ThreadDetail` object mid-run;
  history passes the shared `ExportMenu`).

## Files
- `src/duh/api/routes/threads.py` — `overview` on `ThreadDetailResponse` + populate
- `web/src/api/types.ts` — `overview` on `ThreadDetail`
- Created: `web/src/components/consensus/ConsensusReport.tsx`
- `web/src/components/consensus/ConsensusComplete.tsx`,
  `web/src/components/threads/ThreadDetail.tsx` — use the shared component
- `tests/unit/test_api_threads.py` — overview present / null tests

## Markdown parity (verified)
Both views already rendered the decision through the same shared `<Markdown>`
component (react-markdown + remark-gfm + rehype-highlight + `duh-prose`).
Confirmed `.duh-prose` sets no own `font-size`, so the `text-sm`-placement
difference resolves to identical output. Same engine end to end.

## Validation
Verified against the real dev DB: a stored thread's overview now surfaces via
`_build_thread_detail`. 1677 Python tests, 204 Vitest, mypy + ruff clean, build clean.
