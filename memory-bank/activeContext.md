# Active Context

**Last Updated**: 2026-02-17
**Current Phase**: v0.4 COMPLETE — "It Has a Face"
**Next Action**: Commit v0.4 changes, merge to main, begin v0.5 planning.

---

## Current State

- **v0.4 COMPLETE + post-v0.4 polish.** React frontend with 3D Decision Space, real-time WebSocket streaming, thread browser, preferences. Markdown rendering + light/dark mode added post-v0.4.
- **5 providers shipping**: Anthropic (3 models), OpenAI (3 models), Google (4 models), Mistral (4 models) — 14 total.
- **1318 Python tests + 117 Vitest tests** (1435 total), ruff clean, mypy strict clean.
- **50 Python source files + 66 frontend source files** (116 total).
- REST API, WebSocket streaming, MCP server, Python client library, web UI all built.
- CLI commands: `duh ask`, `duh recall`, `duh threads`, `duh show`, `duh models`, `duh cost`, `duh serve`, `duh mcp`, `duh batch`, `duh export`, `duh feedback`.
- MkDocs docs site: https://msitarzewski.github.io/duh/
- GitHub repo: https://github.com/msitarzewski/duh
- Branch: `v0.3.0` (v0.4 changes uncommitted on top)

## v0.4 Summary

### Frontend (web/)
- React 19 + Vite 6 + Tailwind 4 + TypeScript
- Three.js 3D Decision Space (R3F + drei, lazy-loaded, 873KB chunk)
- Zustand stores (consensus, threads, decision-space, preferences)
- Glassmorphism design system with 22 CSS custom properties (dark/light mode via `prefers-color-scheme`)
- Markdown rendering: react-markdown + remark-gfm + rehype-highlight + mermaid (lazy-loaded)
- Pages: Consensus, Threads, Thread Detail, Decision Space, Preferences, Share
- WebSocket-driven real-time consensus streaming
- Mobile-responsive with 2D SVG scatter fallback for Decision Space
- Page transitions, micro-interactions, ConfidenceMeter animation
- 117 Vitest tests (5 test files)

### Backend additions
- `GET /api/decisions/space` — filtered decision data for 3D visualization
- `GET /api/share/{token}` — public share link (no auth)
- FastAPI static file serving with SPA fallback for web UI
- `duh serve` logs "Web UI: http://host:port" when dist/ exists

### Documentation
- `docs/web-ui.md` — full web UI reference
- `docs/web-quickstart.md` — getting started guide
- Updated mkdocs.yml nav and docs/index.md

### Docker
- Multi-stage build with Node.js 22 frontend stage
- Default CMD: `serve --host 0.0.0.0 --port 8080`
- EXPOSE 8080

## v0.4 Architecture (Decided)

- **React embedded in FastAPI** — Vite builds to `web/dist/`, FastAPI mounts as static files with SPA fallback
- **Three.js code-split** — Scene3D lazy-loaded via React.lazy (873KB chunk)
- **Mermaid code-split** — lazy `import('mermaid')` only when ```mermaid blocks exist (498KB chunk)
- **Main bundle** — 617KB (includes react-markdown + highlight.js + remark-gfm)
- **Zustand for state** — 4 stores (consensus, threads, decision-space, preferences), preferences persisted via localStorage
- **CSS-only animations** — no framer-motion or JS animation libraries
- **Light/dark mode** — `prefers-color-scheme` media query + `.theme-dark`/`.theme-light` manual override classes
- **Theme system** — 22 CSS custom properties in `duh-theme.css`, `.duh-prose` typography in `animations.css`
- **WebSocket events** — phase-level streaming (propose_start, propose_content, challenge_start, etc.)
- **API proxy in dev** — Vite proxies /api and /ws to :8080 for development

## Open Questions (Still Unresolved)

- Licensing (MIT vs Apache 2.0)
- Output licensing for multi-provider synthesized content
- Vector search solution for SQLite (sqlite-vss vs ChromaDB vs FAISS) — v1.0 decision
- Client library packaging: monorepo `client/` dir vs separate repo?
- MCP server transport: stdio vs SSE vs streamable HTTP?
- Hosted demo economics (try.duh.dev) — deferred
- Playwright E2E tests — deferred to v0.5
