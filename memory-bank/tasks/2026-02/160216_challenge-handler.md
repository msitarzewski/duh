# 160216_challenge-handler

## Objective
Implement the CHALLENGE handler — parallel fan-out, forced disagreement prompts, sycophancy detection.

## Outcome
- 411 tests passing (+29 new)
- Ruff clean, mypy strict clean (21 source files)
- Build: successful

## Files Modified
- `src/duh/consensus/handlers.py` — Extended with CHALLENGE functions (+140 lines)
- `src/duh/consensus/machine.py` — Added `sycophantic: bool = False` to ChallengeResult
- `src/duh/consensus/__init__.py` — Re-export new functions
- `tests/unit/test_challenge_handler.py` — **NEW** — 29 tests (372 lines)

## New File Justification
Test file only. Handler code extends existing `handlers.py`.

## API Surface

### `build_challenge_prompt(ctx) -> list[PromptMessage]`
- System: grounding + forced disagreement framing (adapted from phase0 CONSENSUS_CHALLENGER_SYSTEM)
- User: question + proposal with "do NOT defer" instruction

### `select_challengers(provider_manager, proposer_model, *, count=2) -> list[str]`
- Prefers models different from proposer (cross-model > self-critique)
- Sorts by output cost descending (strongest challengers)
- Fills with proposer model for same-model ensemble when needed
- Raises InsufficientModelsError if no models registered

### `detect_sycophancy(text) -> bool`
- Scans opening ~200 chars for 14 praise/agreement markers
- Case-insensitive
- Returns True if challenge is sycophantic (deferred instead of challenged)

### `handle_challenge(ctx, provider_manager, challenger_models, *, temperature, max_tokens) -> list[ModelResponse]`
- Validates CHALLENGE state and proposal presence
- Fans out to all challengers in parallel via `asyncio.gather(return_exceptions=True)`
- Individual failures tolerated — only raises if ALL fail
- Flags sycophantic responses on ChallengeResult
- Sets `ctx.challenges`

### ChallengeResult (modified)
- Added `sycophantic: bool = False` — backwards compatible default

## Design Decisions
- Parallel fan-out via asyncio.gather for latency optimization
- return_exceptions=True for graceful degradation — one failure doesn't kill the phase
- Sycophancy detection is keyword-based heuristic (v0.2+ can use LLM-based)
- Challenger prompt adapted from validated phase0/prompts.py CONSENSUS_CHALLENGER_SYSTEM
- Handler validates state but does NOT transition — caller owns transitions

## Patterns Applied
- asyncio.gather with return_exceptions for parallel execution with fault tolerance
- Sycophancy markers as module-level tuple constant
- Same helper pattern as PROPOSE: _call_challenger extracts single-model call logic

## Integration Points
- Reads `ctx.proposal` set by handle_propose (task 13)
- Sets `ctx.challenges` consumed by handle_revise (task 15)
- Sycophancy test suite (task 21) will test detect_sycophancy with known-flaw proposals
- Convergence detection (task 17) compares challenges across rounds
