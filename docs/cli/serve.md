# duh serve

Start the REST API server.

## Synopsis

```
duh serve [OPTIONS]
```

## Description

Starts a FastAPI server exposing the duh consensus engine as a REST API. The server provides all consensus operations over HTTP and WebSocket, with API key authentication and rate limiting.

See [REST API Reference](../api-reference.md) for full endpoint documentation.

## Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--host` | str | From config (`127.0.0.1`) | Host to bind to. Use `0.0.0.0` to listen on all interfaces. |
| `--port` | int | From config (`8080`) | Port to bind to. |
| `--reload` | flag | `false` | Enable auto-reload for development. Restarts the server when source files change. |

## Examples

Start with defaults:

```bash
duh serve
```

Listen on all interfaces:

```bash
duh serve --host 0.0.0.0
```

Custom port with auto-reload:

```bash
duh serve --port 9000 --reload
```

With a specific config:

```bash
duh --config ./production.toml serve
```

## Configuration

Server settings are in the `[api]` section of your config file:

```toml
[api]
host = "127.0.0.1"
port = 8080
cors_origins = ["http://localhost:3000"]
rate_limit = 60         # requests per minute per API key
rate_limit_window = 60  # window in seconds
```

See [Config Reference](../reference/config-reference.md#api) for all options.

## Interactive docs

When running, the server provides interactive API documentation:

- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`

## Related

- [REST API Reference](../api-reference.md) -- All endpoints
- [Python Client](../python-client.md) -- Client library for the API
- [Config Reference](../reference/config-reference.md#api) -- Server configuration
