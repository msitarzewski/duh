# 160216_summary-generator

## Objective
Implement the summary generator — turn and thread summaries via cheapest available model, with regeneration (upsert) behavior.

## Outcome
- 507 tests passing (+16 new)
- Ruff clean, mypy strict clean (24 source files)
- Build: successful

## Files Modified
- `src/duh/memory/summary.py` — **NEW** — summary generator module (158 lines)
- `src/duh/memory/__init__.py` — Re-export 3 new functions
- `tests/fixtures/providers.py` — Added `input_cost`/`output_cost` params to MockProvider
- `tests/unit/test_summary_generator.py` — **NEW** — 16 tests (319 lines)

## New File Justification
`summary.py`: Summary generation is a memory concern (creating summaries for storage), not a consensus phase handler. Different prompt pattern (summarize vs debate), different model selection strategy (cheapest vs strongest). Separate module keeps concerns clean.

## API Surface

### `select_summarizer(provider_manager) -> str`
- Selects cheapest model by input cost (summaries are cost-sensitive)
- Raises InsufficientModelsError if no models registered

### `build_turn_summary_prompt(question, proposal, challenges, revision, decision) -> list[PromptMessage]`
- System: concise summarizer instructions (2-4 sentences)
- User: all turn data (question, proposal, challenges, revision, decision)

### `build_thread_summary_prompt(question, decisions) -> list[PromptMessage]`
- System: concise summarizer instructions
- User: question + all decisions across rounds

### `generate_turn_summary(pm, question, proposal, challenges, revision, decision, *, model_ref=None, max_tokens=512) -> ModelResponse`
- Defaults to cheapest model, explicit override supported
- Low temperature (0.3) for factual summarization
- Records cost via provider_manager

### `generate_thread_summary(pm, question, decisions, *, model_ref=None, max_tokens=512) -> ModelResponse`
- Same pattern as turn summary

## Design Decisions
- Cheapest model by input cost — summaries process lots of input, produce short output
- Low temperature (0.3) — summaries should be factual, not creative
- Regeneration via repository upsert (save_turn_summary/save_thread_summary)
- MockProvider extended with input_cost/output_cost for cost-sensitive tests

## Patterns Applied
- Same model call pattern as handlers: get_provider → send → record_usage
- TYPE_CHECKING block for ModelResponse and ProviderManager
- Prompt templates as module-level constants

## Integration Points
- Called after consensus completes (by consensus engine, task 20)
- Output persisted via `MemoryRepository.save_turn_summary` / `save_thread_summary` (task 11)
- Summaries consumed by `build_context` (task 18) for future model prompts
- MockProvider cost params enable cost-sensitive selection tests
