# 260622_temperature-self-heal

## Objective
Add a cross-provider safety net so a model that newly rejects the `temperature`
parameter recovers automatically, instead of 400ing until the catalog is
updated by hand. (Closes the open follow-up — this class of bug had hit users
twice: gpt-5.5, then Opus 4.8.)

## Outcome
- New `src/duh/providers/temperature.py`: a process-local `_LEARNED_NO_TEMPERATURE`
  set plus helpers `omit_temperature(model_id, static_set)`,
  `record_no_temperature(model_id)`, and `is_temperature_error(exc)`.
- **OpenAI + Anthropic `send()`**: the temperature decision now uses
  `omit_temperature` (static catalog set OR runtime-learned). On a 400 whose
  message mentions `temperature`, the provider records the model and **retries
  once without temperature**. Future calls skip it from the start.
- Both `stream()` paths honor the learned set too (so a model learned via
  `send` skips temperature in `stream`). `stream()` has no consumers in the
  engine, so it relies on the shared learned set rather than its own retry.
- The static sets (`NO_TEMPERATURE_MODELS`, `ANTHROPIC_NO_TEMPERATURE_MODELS`)
  remain the fast path for known cases; this only adds self-correction for the
  unknown ones.

## Files
- Created: `src/duh/providers/temperature.py`
- Modified: `src/duh/providers/openai.py`, `src/duh/providers/anthropic.py`
- Tests: `test_providers_openai.py`, `test_providers_anthropic.py`
  (`TestTemperatureSelfHeal` — retry-without-temperature on a temperature 400,
  model recorded; non-temperature 400 is NOT retried)

## Validation
- 1681 Python tests, mypy clean (64 files), ruff clean.
- **Live**: with Opus 4.8 temporarily removed from the static set (simulating a
  brand-new model), `send()` hit a real Anthropic 400 on the first attempt,
  retried without temperature, succeeded, and recorded `claude-opus-4-8` in the
  learned set.

## Design Notes
- Retry only fires when temperature was actually sent AND the caught error is a
  provider `BadRequestError` AND its message mentions `temperature` — so
  unrelated 400s propagate normally.
- The learned set is process-local (resets on restart, repopulates on first use)
  — no persistence needed; the catalog static sets are the durable record.
