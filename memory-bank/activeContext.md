# Active Context

**Last Updated**: 2026-02-20
**Current Phase**: v0.6.0 "It's Honest" — sign-out bug fix in progress
**Next Action**: User needs to rebuild (`cd web && npm run build`) and test sign-out. If it works, PR ready.

## v0.6.0 "It's Honest" — Complete (minus sign-out bug)

All 9 tasks (T1-T9) implemented:
- T1: Auth store (Zustand) — `web/src/stores/auth.ts`
- T2: API client auth integration — Bearer token injection, 401 handling, WS token handshake
- T3: Login page — `web/src/pages/LoginPage.tsx`
- T4: Route protection — `web/src/components/shared/ProtectedRoute.tsx`, TopBar user menu
- T5: Dev mode detection — `GET /api/auth/status` endpoint, guest fallback
- T6: Batch feedback — inline Pass/Partial/Fail buttons on ThreadCard
- T7: Frontend tests — 11 auth store + 8 auth component tests
- T8: Documentation — web-ui auth, authentication guide, epistemic-confidence concept doc
- T9: Version bump to 0.6.0

### Sign-Out Bug (IN PROGRESS)

**Problem**: Clicking "Sign Out" in TopBar user menu dropdown does nothing — menu closes but user stays authenticated.

**Root cause**: The outside-click handler used `document.addEventListener('mousedown', ...)` which was intercepting ALL mouse events inside the dropdown (including on the Sign Out button), closing the menu before the click handler could fire. User confirmed: "I can't right click to inspect — the interface disappears."

**Fix applied** (`web/src/components/layout/TopBar.tsx`):
- Removed the broken `mousedown` document listener entirely
- Replaced with invisible backdrop pattern (`fixed inset-0 z-40` div behind dropdown)
- Dropdown at `z-50` — clicks on menu items hit menu, clicks elsewhere hit backdrop
- Sign Out uses plain `onClick` → `logout()` + `window.location.href = '/login'` (hard redirect)
- Removed `useNavigate` dependency — hard redirect avoids React lifecycle race conditions
- Removed `useRef` for menuRef — no longer needed

**Status**: Code written and built (`npm run build` ran successfully). User needs to restart server or hard-refresh (Cmd+Shift+R) to test. Previous attempts failed because browser was serving cached old JS bundle.

**If sign-out still fails after rebuild**: The `handleLogout` function is simple (`logout()` clears localStorage + Zustand, then `window.location.href` does hard redirect). If it still doesn't work, add `console.log('handleLogout called')` at the top of the function to verify it fires.

### Other fix applied this session
- Auto-generated JWT secret in `src/duh/config/loader.py:141-149` — generates `secrets.token_hex(32)` when no JWT secret configured, checks `DUH_JWT_SECRET` env var first. Note: tokens won't survive server restarts with auto-generated secret.

### Test Results
- 1586 Python tests + 185 Vitest tests (1771 total)
- Build clean, all tests pass

---

## Current State

- **Branch `ux-cleanup`** — v0.6.0 features complete, sign-out fix pending user verification
- **1586 Python tests + 185 Vitest tests** (1771 total)
- All previous features intact (v0.1–v0.5 + export + epistemic confidence + consensus nav)

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred to post-1.0
- A2A protocol — deferred to post-1.0
