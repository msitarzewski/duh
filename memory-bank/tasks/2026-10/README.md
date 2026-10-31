# Tasks — October 2026

## Tasks Completed

### 2026-10-29: Security foundation — approved and applied
- Closed API authentication, reset, sharing, traversal, filesystem-tool, and execution-limit defects through existing components.
- Corrected provider schema/search behavior and container installation; removed unsafe registry fallbacks.
- Reviewed validation: 1,714 Python and 204 frontend tests passed, public mypy/Ruff and frontend/Docker builds passed.
- Post-application verification: 90 focused tests passed. Source and documentation are included in the authorized commit on `codex/security-foundation`; subsequently published with PR #25.
- Pattern: `memory-bank/techContext.md#security-foundation-2026-10-29`.
- See: [261029_security-foundation.md](./261029_security-foundation.md).

## Remaining Modernization
Migration convergence, provider/platform upgrades, package boundaries, frontend accessibility, and later delivery work remain outside the completed implementation batches.

## Rollout Completed

### 2026-10-29: Shared engine and run-scoped usage — approved and rolled out
- Completed orchestration behind one typed public API with CLI, REST, WebSocket, MCP, scheduler, and storage adapters; the legacy eight-tuple interface remains compatible.
- Isolated concurrent request budgets while retaining aggregate telemetry and child-task accounting. Refinement shares the owning request's manager and budget.
- Validation: 1,745 Python tests passed (1,733 core and 12 load tests), mypy for 65 source files, Ruff/formatting, and Python 3.11 Docker smoke passed.
- User-approved source `0a4dc9f` is merged in [PR #25](https://github.com/msitarzewski/duh/pull/25). CI passed; installed source hash and public exports match the immutable revision.
- See [261029_shared-engine.md](./261029_shared-engine.md).

## Memory Bank Refresh (2026-10-29)

Refreshed quick-start/current-context references and documented the privacy policy. Public entries retain source-level improvements and verified checks without downstream implementation or operational access details. No additional implementation, release, or deployment occurred.

## Work in Progress (2026-10-31)
[IN-PROGRESS] APPROVAL — implementation and required local/remote checks passed. Test isolation covers collection and the complete session. Completion review is pending; this batch has not changed production.

Validation: 1,735 core tests on Python 3.11–3.14 CI; 12 opt-in load tests locally; 204 frontend tests, source/test typecheck, frontend build, mypy, Ruff, and lock checks passed. See PR #27.
