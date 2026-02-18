# Monitoring

Monitor duh with Prometheus metrics, health checks, and alerting.

## Health checks

### Basic health

```bash
curl http://localhost:8080/api/health
```

```json
{"status": "ok"}
```

This endpoint returns immediately and does not check dependencies. Use it for load balancer liveness probes.

### Detailed health

```bash
curl http://localhost:8080/api/health/detailed
```

```json
{
  "status": "ok",
  "version": "0.5.0",
  "uptime_seconds": 3621.4,
  "components": {
    "database": {"status": "ok"},
    "providers": {
      "anthropic": {"status": "ok"},
      "openai": {"status": "ok"},
      "google": {"status": "unhealthy"}
    }
  }
}
```

The `status` field is `"ok"` when all components are healthy, or `"degraded"` when the database is unreachable or all providers are unhealthy. Individual provider failures do not degrade the overall status unless every provider is down.

!!! tip "Use detailed health for readiness probes"
    Point your Kubernetes readiness probe or Docker healthcheck at `/api/health/detailed` to catch database connectivity issues.

Both health endpoints are exempt from API key authentication, so they work without credentials.

## Prometheus metrics

Metrics are available in Prometheus text format at:

```bash
curl http://localhost:8080/api/metrics
```

This endpoint is also exempt from API key authentication.

### Available metrics

#### Counters

| Metric | Labels | Description |
|--------|--------|-------------|
| `duh_requests_total` | `method`, `path`, `status` | Total HTTP requests |
| `duh_consensus_runs_total` | -- | Total consensus runs completed |
| `duh_tokens_total` | `provider`, `direction` | Total tokens consumed (`direction` is `input` or `output`) |
| `duh_errors_total` | `type` | Total errors by error type |

#### Histograms

| Metric | Buckets | Description |
|--------|---------|-------------|
| `duh_request_duration_seconds` | 5ms -- 10s | HTTP request duration |
| `duh_consensus_duration_seconds` | 5ms -- 10s | Consensus run duration |

Default histogram buckets: `0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0`

#### Gauges

| Metric | Description |
|--------|-------------|
| `duh_active_connections` | Current active connections |
| `duh_provider_health` | Provider health status (1 = healthy, 0 = unhealthy) |

### Prometheus scrape config

Add duh as a target in `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "duh"
    scrape_interval: 15s
    metrics_path: /api/metrics
    static_configs:
      - targets: ["localhost:8080"]
```

## Grafana dashboard

### Key queries

Use these PromQL queries to build a Grafana dashboard:

**Request rate** (requests per second):

```promql
rate(duh_requests_total[5m])
```

**Error rate** (percentage):

```promql
100 * rate(duh_errors_total[5m]) / rate(duh_requests_total[5m])
```

**Request latency (p95)**:

```promql
histogram_quantile(0.95, rate(duh_request_duration_seconds_bucket[5m]))
```

**Consensus duration (p50 and p95)**:

```promql
histogram_quantile(0.50, rate(duh_consensus_duration_seconds_bucket[5m]))
histogram_quantile(0.95, rate(duh_consensus_duration_seconds_bucket[5m]))
```

**Token consumption by provider**:

```promql
rate(duh_tokens_total[1h])
```

**Active connections**:

```promql
duh_active_connections
```

### Suggested dashboard panels

| Panel | Query | Visualization |
|-------|-------|---------------|
| Request Rate | `rate(duh_requests_total[5m])` | Time series |
| Error Rate (%) | `100 * rate(duh_errors_total[5m]) / rate(duh_requests_total[5m])` | Time series with threshold |
| Latency p95 | `histogram_quantile(0.95, rate(duh_request_duration_seconds_bucket[5m]))` | Time series |
| Consensus Duration | `histogram_quantile(0.95, rate(duh_consensus_duration_seconds_bucket[5m]))` | Time series |
| Tokens by Provider | `sum by (provider) (rate(duh_tokens_total[1h]))` | Stacked bar |
| Active Connections | `duh_active_connections` | Stat |
| Health Status | Custom based on `/api/health/detailed` | Status map |

## Alerting

### Suggested alert rules

Add these rules to your Prometheus alerting config or Grafana alert manager.

**High error rate** -- fires when errors exceed 1% of requests:

```yaml
groups:
  - name: duh
    rules:
      - alert: DuhHighErrorRate
        expr: >
          rate(duh_errors_total[5m])
          / rate(duh_requests_total[5m])
          > 0.01
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "duh error rate above 1%"
          description: "Error rate is {{ $value | humanizePercentage }} over the last 5 minutes."

      - alert: DuhHighLatency
        expr: >
          histogram_quantile(0.95, rate(duh_request_duration_seconds_bucket[5m]))
          > 5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "duh p95 latency above 5 seconds"

      - alert: DuhAllProvidersDown
        expr: duh_provider_health == 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "All duh providers are unhealthy"
          description: "No LLM providers are responding. Consensus queries will fail."

      - alert: DuhHealthDegraded
        expr: >
          probe_success{job="duh-health"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "duh health check failing"
```

!!! note "Provider latency"
    Consensus runs call multiple LLM providers sequentially. A p95 latency of 5--15 seconds is normal. Set your latency alert threshold accordingly.

## Log configuration

Configure logging in `config.toml`:

```toml
[logging]
level = "INFO"       # DEBUG, INFO, WARNING, ERROR, CRITICAL
file = ""            # empty = stdout, or a file path like "/var/log/duh/duh.log"
structured = false   # set to true for JSON log output
```

### Recommended production settings

```toml
[logging]
level = "INFO"
file = "/var/log/duh/duh.log"
structured = true
```

Structured (JSON) logging makes it easier to parse logs with tools like Loki, Elasticsearch, or CloudWatch.

### Log rotation

If logging to a file, set up logrotate:

```
/var/log/duh/duh.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
}
```

## Rate limit monitoring

duh includes rate limit headers on every response:

| Header | Description |
|--------|-------------|
| `X-RateLimit-Limit` | Configured requests per window |
| `X-RateLimit-Remaining` | Requests remaining in current window |
| `X-RateLimit-Key` | Identity being rate-limited (`user:<id>`, `api_key:<id>`, or `ip:<addr>`) |

When the limit is exceeded, duh returns HTTP 429 with a `Retry-After` header.

Rate limits are configured in `config.toml`:

```toml
[api]
rate_limit = 60          # requests per minute per key
rate_limit_window = 60   # window in seconds
```

## Next steps

- [Production Deployment](production-deployment.md) -- Full deployment guide
- [Authentication](authentication.md) -- User management and RBAC
