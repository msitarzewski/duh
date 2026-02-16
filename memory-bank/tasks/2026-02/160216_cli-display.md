# 160216_cli-display

## Objective
Implement Task 23: CLI display — Rich Live panels for consensus visualization with tests for panel rendering with mock event data.

## Outcome
- 681 tests passing (+32 new)
- ruff clean
- mypy strict clean (25 source files)

## Files Created
- `src/duh/cli/display.py` — ConsensusDisplay class with Rich panels, spinners, formatters
- `tests/unit/test_cli_display.py` — 32 tests covering all display methods

## Files Modified
- `src/duh/cli/app.py` — Integrated display into `_run_consensus` (progress) and `ask` (final output)
- `tests/unit/test_cli.py` — Updated 2 assertions for Rich panel format ("Dissent:" → "Dissent")

## Display Components

### ConsensusDisplay class (`src/duh/cli/display.py`)
- Accepts optional `Console` for dependency injection in tests
- `start()` / `elapsed` — timing lifecycle
- `round_header(round_num, max_rounds)` — Rich rule separator
- `phase_status(phase, detail)` — returns `Status` spinner context manager
- `show_propose(model_ref, content)` — green-bordered panel, truncated to 500 chars
- `show_challenges(challenges)` — yellow-bordered panel, flags sycophantic, triggers warning
- `show_revise(model_ref, content)` — blue-bordered panel, truncated to 500 chars
- `show_commit(confidence, dissent)` — checkmark line with confidence %
- `show_sycophancy_warning(count, total)` — yellow warning with count
- `round_footer(round, max, models, cost)` — dim stats line
- `show_final_decision(decision, confidence, cost, dissent)` — full untruncated decision panel + optional dissent panel

### Integration into app.py
- `_run_consensus()` accepts optional `display: ConsensusDisplay | None = None`
- Progress display fires at each phase transition when display is provided
- `_ask_async()` creates display with `start()`, passes to `_run_consensus`
- `ask` command creates display for final output (Rich panels instead of click.echo)
- Existing code paths work unchanged (display=None → no visual output)

## Architecture Decisions
- Display is optional parameter, not required — preserves backward compatibility
- Two display instances: one for progress (inside async), one for final output (in sync ask)
- Spinners use `Console.status()` which runs refresh thread — compatible with async/await
- Content truncated to 500 chars in round panels; final decision is untruncated
- Tests use `Console(file=StringIO(), width=80, no_color=True)` for deterministic output capture

## Testing Strategy
- 32 tests organized by display method (TestTruncate, TestLifecycle, TestRoundHeader, etc.)
- `_make_display()` helper creates display with captured StringIO buffer
- Tests verify text content presence in rendered output
- PhaseStatus tests verify context manager interface (don't test spinner animation)
- Full-round integration test verifies all phases render in sequence

## Patterns Applied
- Extends `src/duh/cli/app.py` (existing CLI module)
- New file justified: 165 lines of Rich rendering logic, separate concern from CLI commands
- DI pattern: Console injected for testability
- TYPE_CHECKING import for ConsensusDisplay in app.py
