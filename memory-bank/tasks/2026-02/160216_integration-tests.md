# 160216_integration-tests

## Objective
Implement consensus engine integration tests — full loop with mock providers covering all scenarios from the roadmap.

## Outcome
- 521 tests passing (+14 new)
- Ruff clean, mypy strict clean (24 source files)
- Build: successful

## Files Modified
- `tests/integration/test_consensus_loop.py` — **NEW** — 14 tests across 10 classes (452 lines)

## New File Justification
Test file only. First test in the `tests/integration/` directory (previously empty). Integration tests wire together all consensus components in realistic sequences.

## Test Scenarios

1. **Single-round full loop**: IDLE -> PROPOSE -> CHALLENGE -> REVISE -> COMMIT -> COMPLETE
2. **Decision equals revision**: Verifies handle_commit sets decision = revision
3. **Multi-round convergence**: Same challenges across rounds triggers convergence -> COMPLETE
4. **Multi-round divergence**: Different challenges -> no convergence -> continues to round 3
5. **Max rounds exhausted**: COMPLETE allowed after max_rounds even without convergence
6. **One challenger fails graceful**: Partial failure doesn't abort the round
7. **All challengers fail**: ConsensusError raised when all challengers fail
8. **Cost increments across phases**: propose + challenge + revise all accumulate cost
9. **Cost tracks by provider**: provider_manager.cost_by_provider correctly attributed
10. **Same-model ensemble**: Single model acts as proposer + challengers (self-debate)
11. **Sycophantic challenges lower confidence**: CONSENSUS_AGREEMENT -> confidence < 1.0, dissent None
12. **Cross-round context**: Round 2 propose prompt references round 1 decision/challenges
13. **Wrong transition rejected**: Skipping CHALLENGE raises ConsensusError
14. **Fail mid-loop**: fail() transitions to FAILED with error preserved

## Patterns Applied
- Helper `_run_single_round` encapsulates one full round for reuse across tests
- MockProvider response swapping (`provider._responses = ...`) for multi-round divergence
- MockProvider with non-zero costs for cost accumulation tests
- CONSENSUS_AGREEMENT fixture for sycophancy integration test

## Integration Points
- Wires together: ConsensusStateMachine (task 12), all 4 handlers (tasks 13-16), convergence (task 17)
- Uses: ProviderManager (task 9), MockProvider (task 5), all canned response sets
- Validates: state transitions, context mutation, cost tracking, error handling
