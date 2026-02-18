# Production Deployment

Run duh with PostgreSQL, HTTPS, backups, and proper security for a team or organization.

## Prerequisites

- Linux server (Ubuntu 22.04+ or similar)
- [Docker](https://docs.docker.com/get-docker/) with Compose v2
- A domain name (for HTTPS)
- API keys for at least one provider

## PostgreSQL setup

### Create the database

```bash
sudo -u postgres psql
```

```sql
CREATE USER duh WITH PASSWORD 'your-secure-password';
CREATE DATABASE duh OWNER duh;
GRANT ALL PRIVILEGES ON DATABASE duh TO duh;
\q
```

### Connection string

duh uses SQLAlchemy with asyncpg. Set the database URL in your config or environment:

```
postgresql+asyncpg://duh:your-secure-password@localhost:5432/duh
```

!!! warning "Use asyncpg driver"
    The connection string **must** include `+asyncpg`. Plain `postgresql://` will not work with duh's async database layer.

### Connection pool configuration

Add pool settings to `config.toml` for production workloads:

```toml
[database]
url = "postgresql+asyncpg://duh:your-secure-password@localhost:5432/duh"
pool_size = 5
max_overflow = 10
pool_timeout = 30
pool_recycle = 3600
```

| Setting | Default | Description |
|---------|---------|-------------|
| `pool_size` | `5` | Number of persistent connections in the pool |
| `max_overflow` | `10` | Extra connections allowed beyond `pool_size` under load |
| `pool_timeout` | `30` | Seconds to wait for a connection before raising an error |
| `pool_recycle` | `3600` | Seconds before a connection is recycled (prevents stale connections) |

duh also enables `pool_pre_ping` automatically for PostgreSQL, which verifies connections are alive before use.

## Environment variables

Set these on the host or in a `.env` file:

```bash
# LLM provider keys (set at least one)
export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export GOOGLE_API_KEY=AI...
export MISTRAL_API_KEY=...
export PERPLEXITY_API_KEY=pplx-...

# Authentication
export DUH_JWT_SECRET=$(openssl rand -hex 32)

# Database
export DUH_DATABASE_URL=postgresql+asyncpg://duh:your-secure-password@db:5432/duh
```

!!! tip "Generate a strong JWT secret"
    Use `openssl rand -hex 32` to generate a 64-character hex string. The secret must be at least 32 characters for production use.

## Docker production config

Create a `docker-compose.prod.yml`:

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    volumes:
      - pgdata:/var/lib/postgresql/data
    environment:
      POSTGRES_USER: duh
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: duh
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U duh"]
      interval: 10s
      timeout: 5s
      retries: 5

  duh:
    build: .
    restart: unless-stopped
    ports:
      - "127.0.0.1:8080:8080"
    depends_on:
      db:
        condition: service_healthy
    environment:
      - DUH_DATABASE_URL=postgresql+asyncpg://duh:${POSTGRES_PASSWORD}@db:5432/duh
      - DUH_JWT_SECRET=${DUH_JWT_SECRET}
      - ANTHROPIC_API_KEY
      - OPENAI_API_KEY
      - GOOGLE_API_KEY
      - MISTRAL_API_KEY
      - PERPLEXITY_API_KEY
    volumes:
      - ./config.toml:/app/config.toml:ro
    command: ["serve", "--host", "0.0.0.0", "--port", "8080"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  pgdata:
```

Create a `.env` file alongside the compose file:

```bash
POSTGRES_PASSWORD=your-secure-password
DUH_JWT_SECRET=your-64-char-hex-secret
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Start the stack:

```bash
docker compose -f docker-compose.prod.yml up -d
```

!!! warning "Don't commit .env"
    Add `.env` to `.gitignore`. Never put secrets in `docker-compose.yml` directly.

## Running migrations

After the database is running, apply schema migrations with Alembic:

```bash
# Inside the container
docker compose -f docker-compose.prod.yml exec duh alembic upgrade head

# Or from the host (if duh is installed locally)
DUH_DATABASE_URL=postgresql+asyncpg://duh:password@localhost:5432/duh alembic upgrade head
```

Run migrations every time you upgrade duh to a new version.

## Reverse proxy

Use nginx to terminate HTTPS in front of duh. Install nginx and create a site config:

```nginx
server {
    listen 443 ssl http2;
    server_name duh.example.com;

    ssl_certificate /etc/letsencrypt/live/duh.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/duh.example.com/privkey.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Strict-Transport-Security "max-age=63072000" always;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /ws/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name duh.example.com;
    return 301 https://$host$request_uri;
}
```

Get a free certificate with [certbot](https://certbot.eff.org/):

```bash
sudo certbot --nginx -d duh.example.com
```

## Backup strategy

### Manual backups

```bash
# JSON backup (works with both SQLite and PostgreSQL)
duh backup /backups/duh-$(date +%Y%m%d).json --format json

# SQLite-only: file copy
duh backup /backups/duh-$(date +%Y%m%d).db
```

### Restore from backup

```bash
# Restore (replaces existing data)
duh restore /backups/duh-20260217.json

# Merge into existing data (skip conflicts)
duh restore /backups/duh-20260217.json --merge
```

### Scheduled backups with cron

Add a daily backup job:

```bash
crontab -e
```

```cron
# Daily duh backup at 2:00 AM, keep last 30 days
0 2 * * * /usr/local/bin/duh backup /backups/duh-$(date +\%Y\%m\%d).json --format json 2>&1 | logger -t duh-backup
0 3 * * * find /backups -name "duh-*.json" -mtime +30 -delete
```

For Docker deployments, run the backup inside the container:

```bash
0 2 * * * docker compose -f /opt/duh/docker-compose.prod.yml exec -T duh duh backup /data/backup-$(date +\%Y\%m\%d).json --format json
```

!!! tip "Test your restores"
    A backup you have never restored is a backup that does not work. Periodically test `duh restore` against a staging database.

## Security checklist

Before going live, verify each item:

- [ ] **JWT secret**: At least 32 characters, generated with `openssl rand -hex 32`
- [ ] **Disable registration**: After creating your admin user, set `registration_enabled = false` in `config.toml`:

    ```toml
    [auth]
    jwt_secret = "your-secret-here"
    token_expiry_hours = 24
    registration_enabled = false
    ```

- [ ] **API key management**: Create API keys for programmatic access and distribute them securely. Revoke keys that are no longer needed.
- [ ] **Rate limiting**: Configure rate limits in `config.toml` to prevent abuse:

    ```toml
    [api]
    rate_limit = 60          # requests per minute per key
    rate_limit_window = 60   # window in seconds
    ```

- [ ] **HTTPS only**: Never expose the API over plain HTTP. Use nginx or a load balancer for TLS termination.
- [ ] **Firewall**: Only expose ports 80 and 443 publicly. Bind duh to `127.0.0.1:8080` so it is only reachable through the reverse proxy.
- [ ] **Database credentials**: Use a dedicated database user with a strong password. Do not use the PostgreSQL superuser.
- [ ] **Environment variables**: Never hardcode secrets in config files that are committed to version control.
- [ ] **CORS origins**: Restrict `cors_origins` to your actual domain:

    ```toml
    [api]
    cors_origins = ["https://duh.example.com"]
    ```

## Create your first admin user

After deployment, create an admin user via the CLI:

```bash
duh user-create --email admin@example.com --password 'strong-password' --name Admin --role admin
```

Then disable registration:

```toml
[auth]
registration_enabled = false
```

Restart the service for the config change to take effect.

## Next steps

- [Authentication](authentication.md) -- User management, JWT tokens, RBAC
- [Monitoring](monitoring.md) -- Prometheus metrics, health checks, alerting
- [Docker](docker.md) -- Development Docker setup
