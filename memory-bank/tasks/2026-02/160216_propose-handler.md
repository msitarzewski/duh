# 160216_propose-handler

## Objective
Implement the PROPOSE handler — prompt building, model selection, and execution for the first phase of consensus.

## Outcome
- 382 tests passing (+19 new)
- Ruff clean, mypy strict clean (21 source files)
- Build: successful

## Files Modified
- `src/duh/consensus/handlers.py` — **NEW** — PROPOSE handler functions (131 lines)
- `src/duh/consensus/__init__.py` — Re-export handler functions
- `tests/unit/test_propose_handler.py` — **NEW** — 19 tests (330 lines)

## New File Justification
`handlers.py` contains IO-performing handler functions (model calls via ProviderManager). Distinct from `machine.py` (pure state logic, no IO). Tasks 14-16 will add CHALLENGE, REVISE, COMMIT handlers to this same file.

## API Surface

### `build_propose_prompt(ctx) -> list[PromptMessage]`
- Round 1: system (grounding + expert advisor) + question
- Round > 1: system + question + previous round's decision + challenges for improvement
- Grounding prefix includes current date for temporal awareness

### `select_proposer(provider_manager) -> str`
- Picks strongest model by output cost per million tokens (proxy for capability)
- Falls back to first model if all costs are zero (local models)
- Raises `InsufficientModelsError` if no models registered

### `handle_propose(ctx, provider_manager, model_ref, *, temperature, max_tokens) -> ModelResponse`
- Validates context is in PROPOSE state
- Builds prompt via `build_propose_prompt`
- Calls model via ProviderManager routing
- Records usage/cost via `provider_manager.record_usage`
- Sets `ctx.proposal` and `ctx.proposal_model`
- Returns ModelResponse for caller inspection

## Design Decisions
- Prompts adapted from validated `phase0/prompts.py` (CONSENSUS_PROPOSER_SYSTEM = DIRECT_SYSTEM)
- Handler validates state but does NOT transition — caller (consensus engine) owns transitions
- Model selection is a separate function, not embedded in handler — caller decides whether to use it
- Round > 1 prompt includes previous decision + challenges, not full history (token-efficient)
- Context builder (task 18) will provide more sophisticated context assembly later

## Patterns Applied
- Handler reads/writes ConsensusContext, uses ProviderManager for IO
- `from __future__ import annotations` + TYPE_CHECKING for type-only imports
- Prompt template constants at module level, date grounding computed at call time
- Tests use shared `mock_provider` fixture from `tests/conftest.py`

## Integration Points
- State machine (`machine.py`) transitions to PROPOSE before handler runs
- ProviderManager (`providers/manager.py`) routes model calls and tracks cost
- MockProvider (`tests/fixtures/providers.py`) with CONSENSUS_BASIC responses for deterministic tests
- Next handler (task 14, CHALLENGE) will read `ctx.proposal` set by this handler
