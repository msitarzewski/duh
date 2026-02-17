# Authentication

Manage users, API keys, JWT tokens, and role-based access control.

## Overview

duh supports two authentication methods:

1. **JWT Bearer tokens** -- for users who log in with email and password
2. **API keys** -- for programmatic access via the `X-API-Key` header

Both methods are checked by the API middleware. If no API keys exist in the database and no JWT is provided, the API runs in open mode (no authentication required).

## User management

### Register a user (API)

```bash
curl -X POST http://localhost:8080/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "strong-password-here",
    "display_name": "Alice"
  }'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "a1b2c3d4-...",
  "role": "contributor"
}
```

New users are assigned the `contributor` role by default. Registration can be disabled in config after your initial users are created.

!!! warning "Disable registration in production"
    After creating your admin user, set `registration_enabled = false` in `config.toml` to prevent unauthorized signups.

### Create a user (CLI)

The CLI lets you create users with a specific role, including admin:

```bash
duh user-create \
  --email admin@example.com \
  --password 'strong-password' \
  --name "Admin User" \
  --role admin
```

Available roles: `admin`, `contributor`, `viewer`.

### List users (CLI)

```bash
duh user-list
```

Output:

```
  a1b2c3d4  admin@example.com  Admin User  role=admin  active
  e5f6a7b8  alice@example.com  Alice       role=contributor  active
```

### Log in

```bash
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "alice@example.com",
    "password": "strong-password-here"
  }'
```

Response:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user_id": "a1b2c3d4-...",
  "role": "contributor"
}
```

### Get current user

```bash
curl http://localhost:8080/api/auth/me \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

Response:

```json
{
  "id": "a1b2c3d4-...",
  "email": "alice@example.com",
  "display_name": "Alice",
  "role": "contributor",
  "is_active": true
}
```

## JWT tokens

### Using tokens

Include the token in the `Authorization` header:

```bash
curl http://localhost:8080/api/threads \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

### Token details

- **Algorithm**: HS256
- **Payload**: `sub` (user ID), `exp` (expiry), `iat` (issued at)
- **Default expiry**: 24 hours (configurable)

Tokens are validated on every request by the API key middleware. An expired or invalid token returns HTTP 401.

### Token expiry configuration

```toml
[auth]
token_expiry_hours = 24
```

Set a shorter expiry for higher security. Users will need to call `/api/auth/login` again after the token expires.

## API keys

API keys provide a simpler authentication method for scripts and integrations. They are passed via the `X-API-Key` header.

### Using API keys

```bash
curl http://localhost:8080/api/threads \
  -H "X-API-Key: duh_abc123..."
```

### How API keys work

- Keys are stored as SHA-256 hashes in the database (the raw key is never stored)
- Keys can be revoked by setting a `revoked_at` timestamp
- Keys can optionally be linked to a user via `user_id`

!!! note "API key CLI"
    API key management is available through the database. A dedicated `duh key create` CLI command is planned for a future release.

### Exempt paths

The following paths do not require authentication:

| Path | Purpose |
|------|---------|
| `/api/health` | Basic health check |
| `/api/health/detailed` | Detailed health check |
| `/api/metrics` | Prometheus metrics |
| `/api/auth/register` | User registration |
| `/api/auth/login` | User login |
| `/docs` | OpenAPI documentation |
| `/openapi.json` | OpenAPI spec |
| `/redoc` | ReDoc documentation |
| `/api/share/*` | Shared content |

All other `/api/` and `/ws/` paths require either a JWT token or API key.

## Roles and RBAC

duh uses a hierarchical role system: **admin > contributor > viewer**.

### Role permissions

| Capability | Viewer | Contributor | Admin |
|-----------|--------|-------------|-------|
| Read threads and decisions | Yes | Yes | Yes |
| Create consensus queries | No | Yes | Yes |
| Create threads | No | Yes | Yes |
| Manage users | No | No | Yes |
| Full API access | No | No | Yes |

### How RBAC works

Endpoints use the `require_role` dependency to enforce minimum role levels:

- `require_viewer` -- any authenticated user
- `require_contributor` -- contributors and admins
- `require_admin` -- admins only

A user with a higher role automatically passes lower role checks. For example, an admin can access all contributor endpoints.

### Example: role-protected requests

**As a viewer** (read-only access):

```bash
# List threads -- works for viewers
curl http://localhost:8080/api/threads \
  -H "Authorization: Bearer $VIEWER_TOKEN"

# Create a query -- fails with 403
curl -X POST http://localhost:8080/api/ask \
  -H "Authorization: Bearer $VIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "test"}'
# {"detail": "Requires contributor role"}
```

**As a contributor** (create and view):

```bash
# Create a consensus query -- works for contributors
curl -X POST http://localhost:8080/api/ask \
  -H "Authorization: Bearer $CONTRIBUTOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the trade-offs of microservices?"}'
```

**As an admin** (full access):

```bash
# List users -- admin only
curl http://localhost:8080/api/auth/me \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Configuration

All authentication settings live in the `[auth]` section of `config.toml`:

```toml
[auth]
jwt_secret = ""                # REQUIRED in production -- set via env or config
token_expiry_hours = 24        # how long JWT tokens remain valid
registration_enabled = true    # set to false after creating your admin user
```

### Environment variable override

Set `DUH_JWT_SECRET` as an environment variable instead of putting it in the config file:

```bash
export DUH_JWT_SECRET=$(openssl rand -hex 32)
```

!!! warning "Never commit your JWT secret"
    Use environment variables or a secrets manager for the JWT secret. Never check it into version control.

## Rate limiting

Rate limits apply per identity. The middleware identifies callers in this priority order:

1. **User ID** (from JWT token)
2. **API key ID** (from `X-API-Key` header)
3. **IP address** (fallback)

Configure rate limits in `config.toml`:

```toml
[api]
rate_limit = 60          # requests per minute
rate_limit_window = 60   # window in seconds
```

When the limit is exceeded, the API returns HTTP 429 with a `Retry-After` header.

Every response includes rate limit headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 57
X-RateLimit-Key: user:a1b2c3d4-...
```

## Security recommendations

1. **Generate a strong JWT secret**: `openssl rand -hex 32`
2. **Disable registration** after creating your first admin user
3. **Use HTTPS** -- never expose the API over plain HTTP
4. **Rotate API keys** periodically and revoke unused ones
5. **Set short token expiry** for high-security environments
6. **Restrict CORS origins** to your actual domain

## Next steps

- [Production Deployment](production-deployment.md) -- Full deployment guide with PostgreSQL, Docker, nginx
- [Monitoring](monitoring.md) -- Health checks, metrics, alerting
