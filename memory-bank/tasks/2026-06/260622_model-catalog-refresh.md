# 260622_model-catalog-refresh

## Objective
Refresh the model catalog to the current frontier, correct per-model
temperature behavior, and build a manual tool so the catalog stays accurate
without fabricating data. (PR #16 catalog portion, PR #19.)

## Outcome
- **Frontier models added**: Claude Opus 4.8/4.7, GPT-5.5, GPT-5.4 mini,
  Gemini 3.5 Flash. Dropped deprecated **o3** (per the feed's `status` field).
- **Context windows corrected**: Opus 4.6 + Sonnet 4.6 → 1M (GA); Sonnet 4.5
  stays 200k (its 1M is beta-gated — the live API reports the beta max, the
  feed reports the GA default).
- **OpenAI temperature**: added `gpt-5.5` to `NO_TEMPERATURE_MODELS` +
  `_REASONING_EFFORT_MODELS`. Confirmed gpt-5.2/gpt-5.4 are *correctly* no-temp
  because `reasoning_effort: high` forces temperature=default (the two sets are
  coupled — a reasoning-effort model must also be no-temperature).
- **Anthropic temperature (PR #19, production bug fix)**: Opus 4.8/4.7 deprecated
  `temperature` and returned a 400. Added `ANTHROPIC_NO_TEMPERATURE_MODELS`;
  `AnthropicProvider.send`/`stream` omit temperature for those. Older models
  (Opus 4.6, Sonnet, Haiku) still accept it.
- **Manual refresh tool** `scripts/refresh_catalog.py` (propose-only, never
  auto-applies): diffs catalog vs the truefoundry/models feed + live provider
  APIs, hashes a per-model field projection against `catalog_snapshot.json` to
  show changes since last run, discovers new frontier models, and **empirically
  probes** OpenAI *and* Anthropic temperature support against the live endpoints.

## Files Modified
- `src/duh/providers/catalog.py` — frontier models, `NO_TEMPERATURE_MODELS`,
  new `ANTHROPIC_NO_TEMPERATURE_MODELS`, dropped o3
- `src/duh/providers/openai.py` — `gpt-5.5` in `_REASONING_EFFORT_MODELS`
- `src/duh/providers/anthropic.py` — omit `temperature` for no-temp models in
  `send()` and `stream()`
- `tests/unit/test_providers_google.py`, `test_providers_openai.py`,
  `test_providers_anthropic.py` — catalog count + temperature-handling tests

## Files Created
- `scripts/refresh_catalog.py` — manual catalog refresh / drift detector
- `scripts/catalog_snapshot.json` — per-model projection hashes (baseline)

## Key Lessons (why this matters)
- **Empirical > feed for behavior.** The truefoundry feed was *right* on pricing
  (every anchor matched) but *wrong* on gpt-5.5 temperature. Behavioral fields
  (temperature, reasoning_effort) must be verified against the live endpoint;
  data fields (price/context/status) are diffed and human-confirmed.
- **The Anthropic bug was a process miss**: when Opus 4.8/4.7 were added, only
  OpenAI temperature was probed — the refresh tool now probes Anthropic too so
  it can't recur silently.
- GA-vs-beta context: live `/v1/models` reports the beta-gated max; the feed
  reports the GA default. Use the GA default for the catalog.

## Sourcing Rule
IDs from live provider APIs; pricing/context/status from the truefoundry feed,
cross-checked against known anchors; temperature/behavior probed live. Nothing
fabricated.

## Outcome Metrics
1675 Python tests, 204 Vitest, mypy clean (63 files), ruff clean. Anthropic
fix verified live (Opus 4.8 send/stream succeed).
