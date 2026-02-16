# 160216_sycophancy-tests

## Objective
Implement Task 21: Sycophancy test suite — known-flaw proposals paired with expected challenge behaviors, verifying challenge prompts produce genuine disagreement.

## Outcome
- 619 tests passing (+98 new)
- ruff clean
- mypy strict clean (24 source files)
- No source code changes — test-only task

## Files Modified
- `tests/fixtures/responses.py` — Added 3 known-flaw response sets (KNOWN_FLAW_GENUINE, KNOWN_FLAW_SYCOPHANTIC, KNOWN_FLAW_MIXED)
- `tests/sycophancy/conftest.py` — Shared fixtures (known-flaw providers, helper functions)
- `tests/sycophancy/test_detection.py` — Exhaustive sycophancy marker detection tests
- `tests/sycophancy/test_known_flaws.py` — Known-flaw proposals + expected challenge behaviors
- `tests/sycophancy/test_confidence_impact.py` — Confidence scoring and dissent extraction math

## Test Coverage (98 new tests)

### test_detection.py (65 tests)
- All 14 `_SYCOPHANCY_MARKERS` tested individually at 3 positions (start, mid-sentence, uppercase) = 42 parametrized
- Boundary window: marker at char 199, char 201, straddling boundary, exactly 200, empty, short
- Case handling: lowercase, uppercase, mixed, title case
- False-positive resistance: 8 genuine openers not flagged, 2 edge cases
- Whitespace: leading spaces, newlines, tabs stripped before detection

### test_known_flaws.py (17 tests)
- **Genuine** (4): eval() security flaw proposal + genuine challengers → not sycophantic, contain disagreement, high confidence (1.0), dissent preserved
- **Sycophantic** (5): MD5 password proposal + sycophantic challengers → flagged, contain praise, low confidence (0.5), no dissent, dangerous revision inherits flaw
- **Mixed** (3): rsync deploy proposal + one genuine + one sycophantic → correct split detection, intermediate confidence (0.75), dissent only from genuine
- **Prompt structure** (5): challenge prompt contains forced disagreement, praise prohibition, disagreement openers, deference warning, 2-problem requirement

### test_confidence_impact.py (16 tests)
- Confidence computation: all-genuine (1.0), all-sycophantic (0.5), mixed (0.75), empty (0.5), single genuine/sycophantic, 3-challenger ratios, always in [0.5, 1.0], monotonic with genuine ratio
- Dissent extraction: all-genuine produces dissent, all-sycophantic produces none, mixed filters correctly, empty returns None, format includes model_ref, entries separated by double newlines

## Known-Flaw Response Fixtures
1. **KNOWN_FLAW_GENUINE**: eval() for JSON parsing (security flaw) + challengers identify RCE vulnerability and performance falsehood
2. **KNOWN_FLAW_SYCOPHANTIC**: MD5 for passwords (security flaw) + challengers praise the approach sycophantically
3. **KNOWN_FLAW_MIXED**: rsync deploy to production (ops flaw) + one genuine challenger (reproducibility), one sycophantic

## Patterns Applied
- Extends `tests/fixtures/responses.py` pattern (canned response dicts keyed by model_id)
- Reuses `MockProvider` from `tests/fixtures/providers.py`
- Mirrors helper patterns from `tests/unit/test_challenge_handler.py` (_make_ctx, _challenge_ctx)
- Parametrized tests for exhaustive marker coverage per `_SYCOPHANCY_MARKERS` tuple
