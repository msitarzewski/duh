# Web UI Reference

duh ships with a browser-based interface for running consensus queries, browsing past threads, and visualizing your decision history in 3D. The web UI is a React application embedded in the FastAPI server -- `duh serve` serves both the API and the frontend from the same origin.

## Architecture

The web UI is a single-page application (SPA) built with:

| Layer | Technology |
|-------|-----------|
| Framework | React 19 + TypeScript |
| Build tool | Vite 6 |
| Styling | Tailwind CSS 4 |
| State management | Zustand |
| 3D visualization | Three.js via React Three Fiber + Drei |
| Routing | React Router 7 |

**How it's served**: FastAPI mounts the `web/dist/` directory as static files with an SPA fallback. Every request that doesn't match `/api/*`, `/ws/*`, or a static asset returns `index.html`, so client-side routing works without server configuration. See `src/duh/api/app.py:95-136` for the mount logic.

**API communication**: The frontend calls the same REST API documented in the [REST API Reference](api-reference.md). In production, API requests go to the same origin. In development, Vite proxies `/api` and `/ws` to the backend at `localhost:8080`.

## Pages

### Consensus (/)

The main page. Type a question, pick a protocol and round count, and watch the consensus unfold in real time.

**How it works**: When you submit a question, the frontend opens a WebSocket connection to `/ws/ask` and streams phase events as they arrive. Each round renders as a series of phase cards:

1. **PROPOSE** -- The strongest model's initial answer
2. **CHALLENGE** -- Other models' disagreements
3. **REVISE** -- The proposer's revised answer
4. **COMMIT** -- Confidence score and any dissent

The question input lets you choose:

- **Protocol**: `consensus`, `voting`, or `auto`
- **Rounds**: 1--5 (slider)

A live cost ticker shows cumulative spend during streaming. When consensus completes, a summary card shows the final decision, confidence percentage, dissent (if any), and total cost.

### Threads (/threads)

Browse and search all past consensus sessions.

- **Thread list** -- Shows question, status, and creation date for each thread
- **Search** -- Filter threads by keyword
- **Status filter** -- Filter by `active`, `complete`, or `failed`
- **Thread detail** (/threads/:id) -- Drill into a specific thread to see the full debate history: every round's proposal, challenges, revision, and decision

### Decision Space (/space)

A 3D point cloud visualization of your decision history. Each point represents a past decision, positioned by its taxonomy (category, genus) and colored by confidence or outcome.

**Desktop (3D)**: An interactive Three.js scene with:

- Orbitable camera (drag to rotate, scroll to zoom)
- Grid floor for spatial reference
- Clickable points that reveal decision details
- Filter panel for category, genus, outcome, and confidence range
- Timeline slider to animate decisions over time

**Mobile (2D fallback)**: On screens narrower than 768px, the 3D scene is replaced with a 2D scatter chart. The Three.js bundle (873KB) is never loaded on mobile.

The 3D scene is code-split via `React.lazy()` -- the Three.js chunk is only downloaded when you visit the Decision Space page.

### Preferences (/preferences)

Persistent UI settings stored in `localStorage`:

| Setting | Description |
|---------|-------------|
| Default rounds | Number of consensus rounds (1--5) |
| Protocol | Default protocol for new queries |
| Cost threshold | USD limit before warning |
| Sound effects | Toggle phase transition sounds |

### Share (/share/:id)

A standalone page (no sidebar) for viewing shared consensus results via a public share token. Accessible without authentication.

## Design system

The UI uses a glassmorphism design language with a sci-fi aesthetic:

- **Glass panels** -- Semi-transparent backgrounds with backdrop blur (`GlassPanel` component with `default`, `raised`, and `interactive` variants)
- **Glow effects** -- Subtle cyan glow on active elements (`GlowButton` component)
- **Grid overlay** -- Faint grid pattern in the background for depth
- **Particle field** -- Animated floating particles behind content
- **Monospace typography** -- Model names, metrics, and labels use monospace fonts

Colors, spacing, and transitions are driven by CSS custom properties (e.g., `--color-primary`, `--color-bg`, `--color-border`, `--glass-blur`, `--radius-md`, `--transition-fast`), making the theme easy to customize.

### Animations

Phase transitions and UI interactions are animated with CSS keyframes:

| Animation | Usage |
|-----------|-------|
| `fade-in-up` | Page and card entry |
| `slide-in-left/right` | Sidebar and panel transitions |
| `pulse-glow` | Active phase indicators |
| `shimmer` | Loading skeleton placeholders |
| `scale-in` | Modal and overlay entry |
| `cursor-blink` | Streaming text cursor |
| `scan-line` | Background ambient effect |

### Responsive layout

- **Desktop** (>= 1024px): Persistent sidebar + content area
- **Mobile** (< 1024px): Collapsible sidebar overlay triggered by a menu button in the top bar
- Decision Space automatically switches between 3D and 2D based on viewport width

## API client

The frontend uses a typed API client at `web/src/api/client.ts` that wraps `fetch()` calls to the REST API. Every endpoint has full TypeScript types defined in `web/src/api/types.ts`.

The WebSocket client (`web/src/api/websocket.ts`) handles consensus streaming. It auto-detects `ws:` vs `wss:` based on the page protocol and connects to `/ws/ask` on the current host.

State management uses four Zustand stores:

| Store | Purpose |
|-------|---------|
| `consensus` | WebSocket connection, phase tracking, round data, final result |
| `threads` | Thread list, search, pagination |
| `decision-space` | Decision data, filters, timeline position |
| `preferences` | User settings (persisted to localStorage) |

## Component structure

```
web/src/
  api/              # REST client, WebSocket client, TypeScript types
  components/
    consensus/      # ConsensusPanel, PhaseCard, ConfidenceMeter, CostTicker, ...
    decision-space/ # DecisionCloud, Scene3D, ScatterFallback, FilterPanel, TimelineSlider
    layout/         # Shell, Sidebar, TopBar
    preferences/    # PreferencesPanel
    shared/         # GlassPanel, GlowButton, Badge, Skeleton, ErrorBoundary, ...
    threads/        # ThreadBrowser, ThreadCard, ThreadDetail, TurnCard, ...
  hooks/            # Custom React hooks (useMediaQuery, etc.)
  pages/            # Route-level page components
  stores/           # Zustand state stores
  theme/            # CSS custom properties and animation keyframes
```

## Related

- [Web UI Quickstart](web-quickstart.md) -- Getting started with the web UI
- [REST API Reference](api-reference.md) -- HTTP and WebSocket endpoint documentation
- [Docker](guides/docker.md) -- Running the web UI in a container
- [duh serve](cli/serve.md) -- CLI reference for the server command
