# Observability baseline (EP01-05)

FantApperò ships a vendor-neutral observability baseline so an API request and an async job can be reconstructed end-to-end.

## Goals

| Concern | Behavior |
| --- | --- |
| **Correlation** | `X-Correlation-ID` / `X-Request-ID` created or propagated on every HTTP request; echoed on responses; passed to Celery as task headers (`correlation_id`, `request_id`) |
| **Structured logs** | One JSON object per log line (UTC `timestamp`, `level`, `logger`, `message`, IDs) |
| **Metrics** | In-process counters/histograms for HTTP requests, errors, latency, jobs, failures, queue depth |
| **Error tracking** | `ErrorTracker` Protocol + feature flag; null implementation when disabled |
| **Probes** | `/live` = process up; `/ready` (and `/health`) = dependencies available |

## Correlation flow

```
Client
  │  X-Correlation-ID (optional)
  ▼
API CorrelationMiddleware  → bind contextvars → JSON logs / metrics
  │  celery_task_headers()
  ▼
Celery task headers
  │  task_prerun signal
  ▼
Worker contextvars (correlation_id, request_id, job_id=task_id)
```

Helpers:

- `observability.propagation.celery_task_headers()` — use when enqueueing work from the API
- `observability.ensure_correlation_id()` — generate or reuse the current ID

## HTTP probes

| Path | Meaning | Dependency checks | Compose |
| --- | --- | --- | --- |
| `GET /live` | Liveness — process alive | None | Optional |
| `GET /ready` | Readiness — can serve traffic | Postgres/Redis when configured | Preferred |
| `GET /health` | Alias of readiness | Same as `/ready` | Current healthcheck |

When `DATABASE_URL` / `REDIS_URL` are unset (unit tests), dependency checks are `skipped` and readiness returns 200. When set and unreachable, readiness returns **503**.

## Metrics (in-process)

Stable names in `observability.metrics`:

| Name | Type | Labels |
| --- | --- | --- |
| `http_requests_total` | counter | `method`, `path`, `status` |
| `http_request_errors_total` | counter | `method`, `path`, `error_type` |
| `http_request_duration_seconds` | histogram | `method`, `path`, `status` |
| `jobs_total` | counter | `task`, `state` |
| `jobs_failed_total` | counter | `task` |
| `job_duration_seconds` | histogram | `task` |
| `queue_depth` | gauge | `queue` |
| `provider_requests_total` | counter | `provider`, `endpoint`, `status` |
| `provider_request_errors_total` | counter | `provider`, `endpoint`, `error_type` |
| `provider_request_duration_seconds` | histogram | `provider`, `endpoint` |
| `provider_retries_total` | counter | `provider`, `endpoint` |
| `provider_rate_limit_remaining` | gauge | `provider` |
| `provider_snapshots_stored_total` | counter | `provider`, `endpoint`, `result` |
| `provider_snapshots_deduped_total` | counter | `provider`, `endpoint` |
| `catalog_sync_runs_total` | counter | `provider`, `status` |
| `catalog_sync_entities_total` | counter | `provider`, `entity`, `result` |
| `catalog_sync_duration_seconds` | histogram | `provider` |
| `sports_scheduler_runs_total` | counter | `provider`, `window`, `status` |
| `sports_scheduler_duration_seconds` | histogram | `provider`, `window` |
| `sports_scheduler_quota_mode` | gauge | `provider` |
| `sports_scheduler_lock_skipped_total` | counter | `provider`, `lock` |

Export to Prometheus/OTel can wrap `MetricsRegistry.snapshot()` later without changing call sites.

Adapter SPD (EP04-01): [`api_football_adapter.md`](./api_football_adapter.md).  
Catalogo competizioni/stagioni/club (EP04-02): [`sports_catalog_sync.md`](./sports_catalog_sync.md).  
Scheduler pre/live/post (EP04-06): [`sports_scheduler.md`](./sports_scheduler.md).  
Pannello qualità dati (EP04-07): [`sports_data_quality.md`](./sports_data_quality.md).

## Error tracking feature flag

| Variable | Default | Meaning |
| --- | --- | --- |
| `ERROR_TRACKING_ENABLED` | `false` | When `false`, `NullErrorTracker` (no-op) |
| `ERROR_TRACKING_DSN` | unset | Reserved for a future vendor SDK; **never log this value** |

When enabled without a vendor SDK, `LoggingErrorTracker` records redacted exceptions as structured logs. Swap the implementation behind `ErrorTracker` when a provider is chosen.

## Log data policy (secrets + PII)

**Do not log** secrets or personal data in clear text.

| Category | Examples | Handling |
| --- | --- | --- |
| Secrets | passwords, tokens, API keys, DSNs, `Authorization` | `config.settings.redaction` + log formatter |
| PII | email, phone, fiscal code, IBAN, birth date, street address, names | `observability.redact_logs` masks known field names as `***REDACTED***` |
| Safe context | correlation/request/job IDs, route path, HTTP status, exception **type**, durations | Allowed |

Rules of thumb:

1. Prefer IDs and enums over raw user content in log `extra` fields.
2. Never put `ERROR_TRACKING_DSN`, provider keys, or connection passwords in messages.
3. Error payloads may include technical context (`error_type`, path, task name) after redaction.
4. Client-facing error bodies must not echo secrets (reuse redaction helpers).

## Configuration

Shared on API and worker (`BaseAppSettings`):

| Variable | Required | Secret | Description |
| --- | --- | --- | --- |
| `LOG_LEVEL` | No (`INFO`) | No | Applied at process startup |
| `ERROR_TRACKING_ENABLED` | No (`false`) | No | Feature flag for `ErrorTracker` |
| `ERROR_TRACKING_DSN` | No | **Yes** | Vendor DSN (optional) |

See also [configuration_and_secrets.md](configuration_and_secrets.md).

## Code layout

```
backend/src/observability/
  context.py          # contextvars
  propagation.py      # HTTP ↔ Celery ID helpers
  logging.py          # JSON formatter + configure_logging
  redact_logs.py      # secrets + PII for logs
  metrics.py          # in-process registry
  error_tracking.py   # Protocol + null/logging impl + flag
  middleware.py       # FastAPI/ASGI correlation + HTTP metrics
  celery_signals.py   # task_prerun / postrun / failure
  health.py           # live / ready helpers
```

Wiring: `app.main` (middleware, probes, startup) and `app.worker` (signals, logging).

## Verification

```bash
cd backend && python -m pytest tests/unit/observability tests/unit/test_health.py -q
```

Coverage includes correlation propagation, JSON log + redaction, metrics on success/error/failed job, and live vs ready when a dependency is down.
