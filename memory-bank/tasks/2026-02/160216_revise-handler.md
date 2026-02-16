# 160216_revise-handler

## Objective
Implement the REVISE handler — synthesis prompt building, addressing challenges, context update.

## Outcome
- 432 tests passing (+21 new)
- Ruff clean, mypy strict clean (21 source files)
- Build: successful

## Files Modified
- `src/duh/consensus/handlers.py` — Extended with REVISE functions (+75 lines)
- `src/duh/consensus/__init__.py` — Re-export new functions
- `tests/unit/test_revise_handler.py` — **NEW** — 21 tests (283 lines)

## New File Justification
Test file only. Handler code extends existing `handlers.py`.

## API Surface

### `build_revise_prompt(ctx) -> list[PromptMessage]`
- System: grounding + reviser instructions (address challenges, maintain correct points, push back on wrong challenges)
- User: question + original proposal + all challenges with model_ref attribution

### `handle_revise(ctx, provider_manager, model_ref=None, *, temperature, max_tokens) -> ModelResponse`
- Validates REVISE state, proposal presence, challenges presence
- Defaults to `ctx.proposal_model` when no model_ref given (proposer revises own work)
- Builds prompt, calls model, records usage
- Sets `ctx.revision` and `ctx.revision_model`
- Raises ConsensusError if state/data invalid or no model available

## Design Decisions
- Proposer revises own work by default — consistent with consensus protocol where the original author incorporates feedback
- All challenges included in prompt with model_ref attribution so reviser knows source
- Prompt adapted from validated phase0/prompts.py CONSENSUS_REVISER_SYSTEM
- Handler validates state but does NOT transition — caller owns transitions

## Patterns Applied
- Same pattern as handle_propose: validate state, build prompt, call model, record cost, update context
- Optional model_ref with fallback to proposal_model

## Integration Points
- Reads `ctx.proposal` from handle_propose (task 13) and `ctx.challenges` from handle_challenge (task 14)
- Sets `ctx.revision` consumed by handle_commit (task 16)
- Prompt includes all challenge content for comprehensive revision
