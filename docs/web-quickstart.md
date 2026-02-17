# Web UI Quickstart

Get the duh web interface running in a few minutes.

## Prerequisites

- Python 3.11+
- Node.js 22+ (for development and building)
- At least one provider API key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.)

## Quick start (pre-built)

If the frontend has already been built (i.e., `web/dist/` exists), just start the server:

```bash
duh serve
```

Open [http://localhost:8080](http://localhost:8080) in your browser. The web UI loads at the root URL. The API is available under `/api/*`.

!!! tip "No separate frontend server needed"
    `duh serve` serves both the API and the web UI from the same origin. There's no CORS to configure and no second process to manage.

## Building the frontend

If `web/dist/` doesn't exist yet, build it first:

```bash
cd web
npm ci
npm run build
```

This compiles the React app into `web/dist/`. Then start the server:

```bash
duh serve
```

## Development setup

For active frontend development with hot reload:

**Terminal 1** -- Start the API server:

```bash
duh serve --reload
```

**Terminal 2** -- Start the Vite dev server:

```bash
cd web
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The Vite dev server proxies `/api` and `/ws` requests to the backend at `localhost:8080`, so the frontend and backend work together seamlessly.

!!! note "Port 3000 vs 8080"
    During development, use port **3000** (Vite) for hot reload. In production, use port **8080** (FastAPI) which serves the built frontend directly.

## Docker deployment

The Docker image builds the frontend automatically and serves it alongside the API:

```bash
docker compose up -d
```

The Dockerfile uses a multi-stage build:

1. **Node.js stage** -- Installs dependencies and runs `npm run build`
2. **Python builder stage** -- Installs Python dependencies with `uv`
3. **Runtime stage** -- Copies `web/dist/` and the Python environment into a slim image

The container exposes port 8080 and starts `duh serve --host 0.0.0.0 --port 8080` by default.

See [Docker guide](guides/docker.md) for persistent storage and custom configuration.

## Authentication

In **development mode** (no API keys configured in the database), authentication is skipped and the web UI works without an API key.

For **production**, the web UI sends the API key via the `X-API-Key` header on all requests. API keys are managed through the duh configuration. See [REST API Reference](api-reference.md#authentication) for details.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | -- | Anthropic provider API key |
| `OPENAI_API_KEY` | -- | OpenAI provider API key |
| `GOOGLE_API_KEY` | -- | Google (Gemini) provider API key |
| `MISTRAL_API_KEY` | -- | Mistral provider API key |
| `DUH_CONFIG` | -- | Path to a config file (overrides default locations) |

Server host and port are configured via CLI flags or the `[api]` config section. See [Configuration](getting-started/configuration.md) and [duh serve](cli/serve.md).

## Using the web UI

### Run a consensus query

1. Open the web UI at the root URL
2. Type your question in the input field
3. Optionally adjust the protocol (consensus / voting / auto) and round count
4. Press Enter or click the submit button
5. Watch the consensus phases stream in real time -- PROPOSE, CHALLENGE, REVISE, COMMIT
6. When complete, the final decision appears with confidence and cost

### Browse past threads

Click **Threads** in the sidebar to see all past consensus sessions. Click any thread to view its full debate history.

### Explore the Decision Space

Click **Decision Space** in the sidebar. On desktop, you'll see a 3D point cloud where each point is a past decision. Drag to orbit, scroll to zoom, and click points for details. Use the filter panel to narrow by category, genus, outcome, or confidence range.

On mobile, the view switches to a 2D scatter chart automatically.

### Adjust preferences

Click **Preferences** in the sidebar to set default rounds, protocol, cost threshold, and toggle sound effects. Settings persist in your browser's local storage.

## Next steps

- [Web UI Reference](web-ui.md) -- Full architecture and component documentation
- [REST API Reference](api-reference.md) -- HTTP and WebSocket endpoints
- [Configuration](getting-started/configuration.md) -- Server and provider settings
