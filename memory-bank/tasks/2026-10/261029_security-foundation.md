# 261029_security-foundation

## Objective
Apply the approved first modernization batch: close API and filesystem access defects, preserve fatal execution failures, correct provider request contracts, and make the container executable without startup dependency installation.

## Outcome
- Review: user approved on 2026-10-29; applied to `codex/security-foundation` in the working repository.
- Full reviewed validation: 1,714 Python tests passed; 12 load tests deliberately excluded; 204 frontend tests passed.
- Public mypy passed for 64 source files; Ruff passed; changed Python formatting passed; frontend production build passed.
- Docker image built on the advertised Python 3.11 runtime and passed CLI, frontend, health, traversal, and unknown-API smoke checks with external networking disabled.
- Post-application checks in the working repository: 90 focused tests passed; all 50 approved non-Memory-Bank files match the reviewed sandbox byte for byte.
- Coverage was not remeasured. Existing test warnings remain; no live provider requests were made.
- Source and documentation are included in the authorized feature-branch commit; no PR, merge, package publication, or deployment performed.

## Files Modified and Integration Points
- `src/duh/api/app.py:41`: explicit engine/frontend/diagnostic/auth-middleware composition; CORS wraps auth failures and preflight; resolved SPA paths stay inside the distribution directory; lifespan disposes the database on failure.
- `src/duh/api/auth.py:139` and `src/duh/api/routes/ws.py:27`: one authentication policy for HTTP and bounded WebSocket first messages, validating active users or API keys before provider work.
- `src/duh/api/auth.py:482`: configured reset origin, escaped email HTML, password-version binding, and an atomic conditional update for single-use reset tokens; password input enforces the bcrypt UTF-8 byte limit while retaining legacy verification behavior.
- `src/duh/api/routes/threads.py:139`: only a separately stored slug on an explicitly public thread can be shared; UUIDs alone grant no public access.
- `src/duh/api/routes/ask.py`: round overrides use a request-local configuration copy.
- `src/duh/providers/base.py:24` and `src/duh/providers/base.py:43`: finite provider deadlines and sibling cancellation on fatal errors. Consensus, voting, scheduler, and optional utility callers use explicit recoverable exceptions.
- `src/duh/providers/anthropic.py`, `openai.py`, `google.py`, `mistral.py`, `perplexity.py`, `catalog.py`: translate closed output schemas, extract OpenAI URL citations, remove unsupported Mistral native search, and retain generic search fallback where native search is unavailable.
- `src/duh/cli/app.py:235` and `src/duh/config/schema.py`: file reads are registered only with a configured sandbox; provider timeouts are configurable.
- `src/duh/tools/augmented_send.py`: capability-aware search fallback and a bounded tool loop.
- `src/duh/mail.py`: SMTP operations have a finite timeout.
- `Dockerfile`, `.dockerignore`: stable environment paths, non-editable project installation, required container configuration included, and pinned uv tooling.
- `npm/like-duh/`: automatic installation and execution of the unrelated registry package are removed; executable resolution uses explicit paths or an existing CLI.
- Existing unit/integration tests and `tests/conftest.py` were extended for regression coverage, credential isolation, and network blocking.

## Patterns Applied
- Existing adapter/protocol and state-machine architecture retained: `memory-bank/techContext.md#key-technical-patterns`.
- Existing app factory extended; no second API server or authentication implementation introduced.
- Configuration and resource boundaries are documented in `memory-bank/decisions.md#2026-10-29-explicit-api-composition-and-bounded-provider-execution`.

## Compatibility and Remaining Work

Follow-up: shared orchestration and run-scoped accounting were implemented and approved in [261029_shared-engine.md](./261029_shared-engine.md). The original remaining-work list below records this security batch's boundary; current rollout status is tracked by the follow-up task.
- Anthropic structured output now requires an explicit JSON schema; an unconstrained `response_format="json"` fails explicitly. All in-repository utility callers were migrated.
- Local unauthenticated engine mode remains available only when neither users nor API keys exist. Hosts omitting engine routes may use their own router dependencies.
- Set `DUH_PUBLIC_BASE_URL` for externally delivered reset links; default remains the local API URL.
- Shared request cost accounting, one event-driven engine, unified schema migration history, Responses API migration, dependency upgrades, public sharing management, and package naming/publication remain later batches.

## Artifacts
- Branch: `codex/security-foundation`; inspect with `git diff main`.
- Review: approved in conversation on 2026-10-29.
- Commit: authorized by the user; source and completion documentation included together. Push/PR/release only when requested.

## Documentation Refresh (2026-10-29)

Updated the session entry point, current validation summaries, technical context, and privacy policy. Entries describe this repository's public behavior only. Source code, validation results, release status, and remaining implementation scope are unchanged.
