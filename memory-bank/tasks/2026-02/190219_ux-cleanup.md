# 190219_ux-cleanup

## Objective
UX polish and bug fixes: thread detail collapse defaults, consensus engine improvements (token limits, cross-provider challengers, truncation detection), export menu glass styling, PDF export crash fix.

## Outcome
- All thread sections collapsed by default except decision (with dissent)
- Consensus `max_tokens` bumped 4096 -> 16384 for propose/challenge/revise
- Token budget communicated to LLMs in system prompts to prevent truncation
- Truncation detection: `finish_reason` checked after each phase, `truncated` flag sent via WebSocket, amber warning shown in PhaseCard UI
- Challenger selection prefers cross-provider diversity (one per provider first, then fill)
- Export dropdown menus use glass styling (`glass-bg` + `backdrop-blur`)
- PDF export crash fixed: missing bold-italic (`BI`) TTF font variant
- All 1586 Python + 166 Vitest tests pass

## Files Modified

### Backend
- `src/duh/consensus/handlers.py` — `max_tokens` 4096->16384; `_token_budget_note()` helper appended to all system prompts; `select_challengers()` rewritten for cross-provider diversity (prefers one model per different provider, then fills same-provider, then self-ensemble)
- `src/duh/api/routes/ws.py` — Captures `ModelResponse` from propose/challenge/revise handlers; sends `truncated` boolean in `phase_complete` and `challenge` WebSocket events
- `src/duh/cli/app.py` — Added `self.add_font("DuhSans", "BI", path)` to fix bold-italic crash in PDF export

### Frontend
- `web/src/components/threads/ThreadDetail.tsx` — All rounds `defaultOpen={false}`; dissent in decision block `defaultOpen={false}`
- `web/src/components/consensus/DissentBanner.tsx` — Added `defaultOpen` prop (defaults `true` for backward compat)
- `web/src/components/consensus/PhaseCard.tsx` — Added `truncated` prop; renders amber "Output truncated" warning when content hit token limit; `challenges` type updated to include `truncated` field
- `web/src/components/consensus/ConsensusPanel.tsx` — Passes `truncated` flag from round data to PROPOSE and REVISE PhaseCards
- `web/src/components/consensus/ConsensusComplete.tsx` — Export dropdown uses glass styling
- `web/src/components/shared/ExportMenu.tsx` — Export dropdown uses glass styling
- `web/src/stores/consensus.ts` — Added `truncated: string[]` to `RoundData`; `ChallengeEntry` gains `truncated` field; `handleEvent` tracks truncation per phase
- `web/src/api/types.ts` — Added `truncated?: boolean` to `WSPhaseComplete` and `WSChallenge`

## Patterns Applied
- `systemPatterns.md#Disclosure` — reused for DissentBanner defaultOpen prop
- Cross-provider challenger selection follows existing `select_challengers` pattern but adds provider diversity layer
- Token budget note follows existing `_grounding_prefix()` pattern for system prompt composition

## Architectural Decisions
- **Token budget in system prompt**: LLMs don't know their `max_tokens` limit. Adding budget instruction in system prompt lets models self-regulate output length. Not a guarantee (models can't count tokens precisely), but dramatically reduces truncation.
- **Cross-provider challengers**: Prefers models from different providers for genuine intellectual diversity. Same-provider models may share training data biases, reducing challenge quality.
- **16384 max_tokens**: 4x increase from 4096. Balances thorough responses against cost (output tokens dominate cost for expensive models).

## Artifacts
- Branch: `ux-cleanup`
