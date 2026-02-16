# Running with Docker

Run duh in a container with persistent storage and no local Python installation required.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (with Compose v2)
- API keys for at least one provider

## Quick start

Build and run:

```bash
docker compose run duh ask "What are the trade-offs of microservices vs monolith?"
```

That's it. Docker Compose builds the image, creates a persistent volume for the database, and passes your API keys from the host environment.

## Setup

### 1. Set API keys

Export your keys in the host shell:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
```

Docker Compose forwards these to the container via the `environment` section in `docker-compose.yml`.

!!! warning "Don't put API keys in docker-compose.yml"
    The compose file references environment variables by name (without values). Your keys stay in your shell environment, not in version-controlled files.

### 2. Build the image

```bash
docker compose build
```

The Dockerfile uses a multi-stage build:

1. **Builder stage** -- Installs dependencies with `uv sync --no-dev --frozen`
2. **Runtime stage** -- Copies the virtual environment and source code into a slim Python 3.11 image

The runtime image runs as a non-root `duh` user (UID 1000).

### 3. Run commands

```bash
# Ask a question
docker compose run duh ask "your question"

# Search past decisions
docker compose run duh recall "topic"

# List threads
docker compose run duh threads

# Show a specific thread
docker compose run duh show a1b2c3d4

# List models
docker compose run duh models

# Check costs
docker compose run duh cost
```

## Persistent storage

The database is stored in a Docker volume (`duh-data`) mounted at `/data` inside the container. The Docker-specific config file (`docker/config.toml`) sets:

```toml
[database]
url = "sqlite+aiosqlite:////data/duh.db"
```

Your data persists across container restarts and rebuilds.

### Inspect the volume

```bash
docker volume inspect duh_duh-data
```

### Back up the database

```bash
docker compose run duh cat /data/duh.db > backup.db
```

### Delete all data

```bash
docker volume rm duh_duh-data
```

## Custom config

Mount a custom config file:

```bash
docker compose run -v ./my-config.toml:/app/config.toml duh ask "question"
```

Or modify `docker-compose.yml` to add the mount permanently:

```yaml
services:
  duh:
    build: .
    volumes:
      - duh-data:/data
      - ./my-config.toml:/app/config.toml
    environment:
      - ANTHROPIC_API_KEY
      - OPENAI_API_KEY
```

## Docker Compose reference

The included `docker-compose.yml`:

```yaml
services:
  duh:
    build: .
    volumes:
      - duh-data:/data
    environment:
      - ANTHROPIC_API_KEY
      - OPENAI_API_KEY

volumes:
  duh-data:
```

## Next steps

- [Configuration](../getting-started/configuration.md) -- Full config options
- [Local Models](local-models.md) -- Connect to Ollama running on the host
