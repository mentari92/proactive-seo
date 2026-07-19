# 08 — Monitoring & Observability Specification

> **Status:** Canonical Reference  
> **Scope:** Enterprise-grade observability for the Proactive SEO Platform  
> **Stack:** Prometheus · Grafana · Loki · Tempo · OpenTelemetry · PagerDuty · Slack

---

## Table of Contents

1. [Logging Strategy](#1-logging-strategy)
2. [Metrics Collection](#2-metrics-collection)
3. [Alerting Rules](#3-alerting-rules)
4. [Dashboards](#4-dashboards)
5. [Distributed Tracing](#5-distributed-tracing)
6. [Health Checks](#6-health-checks)
7. [Incident Management](#7-incident-management)
8. [Performance Monitoring](#8-performance-monitoring)

---

## 1. Logging Strategy

### 1.1 Structured JSON Logging

Every service emits logs as structured JSON to `stdout`. No unstructured text, no printf-style formatting. The logging library (Python: `structlog`, Node: `pino`, Go: `zap`) enforces a fixed schema.

**Canonical log envelope:**

```json
{
  "timestamp": "2026-07-19T14:32:01.123Z",
  "level": "INFO",
  "service": "agent-orchestrator",
  "version": "2.4.1",
  "environment": "production",
  "correlation_id": "req-a1b2c3d4e5f6",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "message": "Agent execution completed",
  "agent_type": "content-writer",
  "agent_id": "cw-7891",
  "campaign_id": "cmp-456",
  "duration_ms": 3420,
  "status": "success",
  "tokens_used": 1847,
  "cost_usd": 0.0056,
  "extra": {}
}
```

**Required fields on every log line:**

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | UTC, millisecond precision |
| `level` | enum | DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `service` | string | Service name (matches container/deployment name) |
| `version` | string | Semantic version of the deployed image |
| `environment` | string | `production`, `staging`, `development` |
| `correlation_id` | string | Request-scoped ID, propagated across services |
| `trace_id` | string | OpenTelemetry trace ID (32-hex) |
| `span_id` | string | OpenTelemetry span ID (16-hex) |
| `message` | string | Human-readable event description |

**Forbidden in production logs:**

- PII (emails, names, IP addresses) — must be redacted or hashed
- Full request/response bodies — log payloads > 1 KB must be truncated
- Secrets, tokens, API keys — log pipeline filters drop these even if accidentally emitted
- Stack traces at INFO level — only ERROR and above

### 1.2 Log Levels

| Level | When to Use | Volume (prod) | Example |
|-------|-------------|---------------|---------|
| **DEBUG** | Internal state, variable dumps, loop iterations | OFF in production; enabled per-service via feature flag | `Keyword list parsed: 47 terms` |
| **INFO** | Normal operations, state transitions, completions | Baseline — expected high volume | `Campaign cmp-456 moved to ACTIVE` |
| **WARNING** | Degraded but functional, approaching thresholds, retries | Low — investigate if spikes | `Redis latency 120ms (threshold 100ms)` |
| **ERROR** | Operation failed, exception caught, retryable failure | Very low — requires triage | `LLM API call failed: 503 Service Unavailable` |
| **CRITICAL** | System-wide failure, data corruption risk, security breach | Near zero — triggers PagerDuty | `Database connection pool exhausted — all agents stalled` |

**Runtime level control:** Each service exposes `POST /admin/log-level` accepting `{"level": "DEBUG", "ttl_seconds": 300}` to temporarily elevate verbosity without redeployment. The level auto-reverts after TTL expires.

### 1.3 Correlation IDs

Every incoming HTTP request, message queue event, or scheduled trigger generates a `correlation_id` if one is not already present.

**Propagation rules:**

| Context | Header / Field | Format |
|---------|---------------|--------|
| HTTP request | `X-Correlation-ID` header | `req-{uuid4-no-dashes}` |
| Message queue (RabbitMQ/Redis Streams) | Message header `correlation_id` | Same format |
| Cron / scheduled job | `cron-{job_name}-{timestamp}` | Prefixed with `cron-` |
| Agent-to-agent | Forward from parent context | Original ID preserved |
| External webhook | Generate on receipt if missing | `wh-{uuid4-no-dashes}` |

**Middleware (all services):**

```python
# Python / FastAPI middleware
from starlette.middleware.base import BaseHTTPMiddleware
import uuid

class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        cid = request.headers.get("X-Correlation-ID") or f"req-{uuid.uuid4().hex}"
        structlog.contextvars.bind_contextvars(correlation_id=cid)
        request.state.correlation_id = cid
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response
```

**Search workflow:** Given a `correlation_id`, Loki query `{correlation_id="req-a1b2c3d4e5f6"} | json` returns every log line from every service involved in that request, ordered by timestamp.

### 1.4 Log Aggregation

**Primary stack: Loki + Promtail (Grafana ecosystem)**

```
┌─────────────────────────────────────────────────────┐
│  Application Containers                             │
│  (stdout → structured JSON)                         │
└──────────────┬──────────────────────────────────────┘
               │
               ▼
┌──────────────────────────┐
│  Promtail (DaemonSet)    │
│  • tail container logs   │
│  • add k8s labels        │
│  • pipeline stages       │
│    - regex extract        │
│    - json decode          │
│    - label mapping        │
│    - drop PII patterns   │
└──────────┬───────────────┘
           │ push
           ▼
┌──────────────────────────┐     ┌──────────────────────┐
│  Loki (clustered)        │────▶│  Grafana             │
│  • index: labels only    │     │  • Explore: logQL    │
│  • store: S3/GCS        │     │  • Dashboard links   │
│  • retention: 90d hot    │     │  • Alert rules       │
│  • compactor            │     └──────────────────────┘
└──────────────────────────┘
```

**Alternative: ELK Stack** (for teams already invested in Elasticsearch)

| Component | Role |
|-----------|------|
| Filebeat / Fluentd | Ship logs from containers |
| Elasticsearch | Index and store (full-text search) |
| Kibana | Query, visualize, dashboard |

**When to choose Loki vs ELK:**

| Factor | Loki | ELK |
|--------|------|-----|
| Cost | Low (index = labels only) | High (full-text index) |
| Query speed for text search | Slower (grep over chunks) | Faster (inverted index) |
| Operational complexity | Low | High (JVM tuning, sharding) |
| Label-based queries | Excellent | Good |
| Integration with Grafana | Native | Via datasource plugin |

**Recommendation:** Loki for this platform. Log volumes are high (millions of agent events/day), and most queries are label-based (`service=X`, `level=ERROR`, `campaign_id=Y`). Full-text search over agent messages is a secondary need.

### 1.5 Log Retention Policies

| Tier | Retention | Storage | Use Case |
|------|-----------|---------|----------|
| **Hot** | 7 days | SSD / fast object storage | Active debugging, real-time queries |
| **Warm** | 30 days | Standard object storage (S3 IA) | Recent investigations, incident review |
| **Cold** | 90 days | Glacier / Archive storage | Compliance, audit, post-mortem review |
| **Archive** | 1 year | Deep archive (compliance only) | Regulatory requirement (GDPR audit trail) |

**Per-level retention overrides:**

- `CRITICAL` logs: retained 1 year in hot+warm tiers
- `DEBUG` logs: never retained past hot tier (7 days), even in staging
- `audit.*` namespace: retained 2 years regardless of level

**Compaction:** Loki compactor runs hourly, merges chunks older than 24h into day-sized blocks. Deletion requests (GDPR right-to-erasure) are processed via compactor tombstones.

### 1.6 Log Search & Analysis

**LogQL query examples:**

```logql
# All errors in agent-orchestrator in the last hour
{service="agent-orchestrator", level="ERROR"} | json

# All logs for a specific campaign
{campaign_id="cmp-456"} | json | line_format "{{.message}}"

# Error rate by service (5m windows)
sum(rate({level="ERROR"} | json [5m])) by (service)

# Slow agent executions (>10s)
{service="agent-orchestrator"} | json | duration_ms > 10000

# LLM API failures with cost impact
{service="llm-gateway", level="ERROR"} | json
  | cost_usd > 0
  | line_format "{{.agent_type}} failed: {{.message}} (${{.cost_usd}})"
```

**Saved queries (Grafana):**

| Query Name | Use Case |
|------------|----------|
| `error-spike-by-service` | Triage: which service is throwing errors? |
| `campaign-lifecycle` | Follow a campaign from creation to completion |
| `llm-cost-breakdown` | Cost attribution by agent type and model |
| `slow-queries` | Database queries exceeding SLA |
| `rate-limit-hits` | External API rate limit events |

---

## 2. Metrics Collection

### 2.1 Application Metrics (Prometheus)

Every service exposes a `/metrics` endpoint in Prometheus exposition format.

**HTTP Request Metrics (RED method):**

```yaml
# Request rate
http_requests_total:
  type: counter
  labels: [service, method, path, status_code]
  description: "Total HTTP requests"

# Request latency
http_request_duration_seconds:
  type: histogram
  labels: [service, method, path]
  buckets: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]

# Error rate (derived)
# PromQL: sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (service)
#          /
#          sum(rate(http_requests_total[5m])) by (service)
```

**Agent Execution Metrics:**

```yaml
# Agent execution time
agent_execution_duration_seconds:
  type: histogram
  labels: [agent_type, campaign_id, status]
  buckets: [0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300]

# Agent success/failure
agent_execution_total:
  type: counter
  labels: [agent_type, status]  # status: success, failure, timeout, cancelled

# Agent queue depth
agent_queue_depth:
  type: gauge
  labels: [agent_type, priority]
  description: "Current number of tasks waiting in queue"

# Agent queue wait time
agent_queue_wait_seconds:
  type: histogram
  labels: [agent_type, priority]
  buckets: [0.1, 0.5, 1, 5, 10, 30, 60, 300]
```

**LLM API Metrics:**

```yaml
# LLM API call count
llm_api_calls_total:
  type: counter
  labels: [provider, model, agent_type, status]

# LLM tokens used
llm_tokens_total:
  type: counter
  labels: [provider, model, token_type]  # token_type: prompt, completion

# LLM latency
llm_api_duration_seconds:
  type: histogram
  labels: [provider, model]
  buckets: [0.5, 1, 2, 5, 10, 30, 60]

# LLM cost
llm_cost_usd_total:
  type: counter
  labels: [provider, model, agent_type]

# LLM rate limit events
llm_rate_limit_hits_total:
  type: counter
  labels: [provider, model]
```

**External API Metrics:**

```yaml
# External API calls
external_api_calls_total:
  type: counter
  labels: [api_name, endpoint, status_code]

# External API latency
external_api_duration_seconds:
  type: histogram
  labels: [api_name, endpoint]

# External API rate limits
external_api_rate_limit_remaining:
  type: gauge
  labels: [api_name]
  description: "Remaining API quota before rate limit"

# External API errors
external_api_errors_total:
  type: counter
  labels: [api_name, error_type]
```

**Queue & Processing Metrics:**

```yaml
# Message publish rate
queue_messages_published_total:
  type: counter
  labels: [queue_name, priority]

# Message consume rate
queue_messages_consumed_total:
  type: counter
  labels: [queue_name, status]  # status: ack, nack, dead_letter

# Processing time
queue_message_processing_seconds:
  type: histogram
  labels: [queue_name, consumer_group]
  buckets: [0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30]
```

### 2.2 Infrastructure Metrics

**Collected via:** node_exporter, kube-state-metrics, cAdvisor, custom exporters.

```yaml
# CPU
node_cpu_seconds_total:
  type: counter
  labels: [instance, mode]  # mode: user, system, idle, iowait

# Memory
node_memory_MemAvailable_bytes: gauge
node_memory_MemTotal_bytes: gauge

# Disk
node_filesystem_avail_bytes: gauge
  labels: [instance, mountpoint, fstype]
node_disk_io_time_seconds: counter

# Network
node_network_receive_bytes_total: counter
node_network_transmit_bytes_total: counter
```

**Database (PostgreSQL via postgres_exporter):**

```yaml
pg_stat_activity_count: gauge
  labels: [datname, state]
pg_stat_database_tup_fetched: counter
pg_stat_database_tup_inserted: counter
pg_stat_bgwriter_checkpoint_duration_seconds: histogram
pg_settings_max_connections: gauge

# Custom: query execution time
pg_query_duration_seconds:
  type: histogram
  labels: [query_name, database]
  buckets: [0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5]
```

**Redis (via redis_exporter):**

```yaml
redis_memory_used_bytes: gauge
redis_memory_max_bytes: gauge
redis_commands_processed_total: counter
redis_keyspace_hits_total: counter
redis_keyspace_misses_total: counter
redis_connected_clients: gauge
redis_evicted_keys_total: counter

# Derived: cache hit rate
# PromQL: redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)
```

**Container / Kubernetes:**

```yaml
container_cpu_usage_seconds_total: counter
container_memory_working_set_bytes: gauge
container_fs_usage_bytes: gauge
kube_pod_status_phase: gauge
kube_deployment_status_replicas_available: gauge
kube_deployment_status_replicas_unavailable: gauge
kube_job_status_succeeded: gauge
kube_job_status_failed: gauge
```

### 2.3 Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    cluster: seo-platform-prod
    environment: production

rule_files:
  - "/etc/prometheus/rules/*.yml"

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']

scrape_configs:
  - job_name: 'kubernetes-pods'
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: ${1}:${2}

  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']

  - job_name: 'postgres-exporter'
    static_configs:
      - targets: ['postgres-exporter:9187']

  - job_name: 'redis-exporter'
    static_configs:
      - targets: ['redis-exporter:9121']

  - job_name: 'kube-state-metrics'
    static_configs:
      - targets: ['kube-state-metrics:8080']
```

**Storage & Retention:**

| Setting | Value | Rationale |
|---------|-------|-----------|
| `--storage.tsdb.retention.time` | 30 days | Hot metrics for dashboards |
| `--storage.tsdb.retention.size` | 50GB | Disk-based cap |
| Long-term storage | Thanos / Mimir | 1-year retention on object storage |
| Downsampling | 5m after 7d, 1h after 30d | Reduce cardinality for historical queries |

---

## 3. Alerting Rules

### 3.1 Alert Routing Architecture

```
Prometheus ──▶ Alertmanager ──┬──▶ PagerDuty (CRITICAL)
                              ├──▶ Slack #seo-alerts (WARNING)
                              ├──▶ Email digest (WARNING, grouped)
                              └──▶ Grafana annotations (INFO)
```

### 3.2 Critical Alerts → PagerDuty / OpsGenie

These alerts page the on-call engineer immediately. Response SLA: 5 minutes.

```yaml
# /etc/prometheus/rules/critical-alerts.yml
groups:
  - name: critical-alerts
    interval: 30s
    rules:

      # Service Down
      - alert: ServiceDown
        expr: up{job=~"kubernetes-pods"} == 0
        for: 1m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Service {{ $labels.instance }} is DOWN"
          description: "{{ $labels.job }} on {{ $labels.instance }} has been unreachable for 1 minute."
          runbook: "https://wiki.internal/runbooks/service-down"

      # Database Connection Lost
      - alert: DatabaseConnectionLost
        expr: pg_up == 0
        for: 30s
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "PostgreSQL is unreachable"
          runbook: "https://wiki.internal/runbooks/db-connection-lost"

      # Database Connection Pool Exhausted
      - alert: DatabasePoolExhausted
        expr: pg_stat_activity_count{state="active"} / pg_settings_max_connections > 0.9
        for: 2m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Database connection pool > 90% utilized"
          description: "Active connections: {{ $value | humanize }}. Connection starvation imminent."

      # Memory Critical
      - alert: MemoryCritical
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.90
        for: 3m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Memory usage > 90% on {{ $labels.instance }}"
          runbook: "https://wiki.internal/runbooks/memory-critical"

      # Error Rate Critical
      - alert: ErrorRateCritical
        expr: |
          sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (service)
          /
          sum(rate(http_requests_total[5m])) by (service)
          > 0.05
        for: 3m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Error rate > 5% on {{ $labels.service }}"
          description: "Current error rate: {{ $value | humanizePercentage }}"

      # Agent Failure Rate
      - alert: AgentFailureRateHigh
        expr: |
          sum(rate(agent_execution_total{status="failure"}[10m])) by (agent_type)
          /
          sum(rate(agent_execution_total[10m])) by (agent_type)
          > 0.30
        for: 5m
        labels:
          severity: critical
          team: agents
        annotations:
          summary: "Agent failure rate > 30% for {{ $labels.agent_type }}"
          runbook: "https://wiki.internal/runbooks/agent-failures"

      # Disk Space Critical
      - alert: DiskSpaceCritical
        expr: (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"}) < 0.10
        for: 5m
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Disk space < 10% on {{ $labels.instance }}"

      # Redis Down
      - alert: RedisDown
        expr: redis_up == 0
        for: 30s
        labels:
          severity: critical
          team: platform
        annotations:
          summary: "Redis is unreachable"

      # Dead Letter Queue Growing
      - alert: DeadLetterQueueGrowing
        expr: increase(queue_messages_consumed_total{status="dead_letter"}[15m]) > 50
        for: 0m
        labels:
          severity: critical
          team: agents
        annotations:
          summary: "Dead letter queue received >50 messages in 15 minutes"
```

### 3.3 Warning Alerts → Slack / Email

These alerts post to `#seo-alerts` on Slack and send grouped email digests. Response SLA: 30 minutes.

```yaml
# /etc/prometheus/rules/warning-alerts.yml
groups:
  - name: warning-alerts
    interval: 60s
    rules:

      # Memory Warning
      - alert: MemoryWarning
        expr: (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes) > 0.70
        for: 5m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Memory usage > 70% on {{ $labels.instance }}"

      # Queue Depth Warning
      - alert: QueueDepthHigh
        expr: agent_queue_depth > 100
        for: 5m
        labels:
          severity: warning
          team: agents
        annotations:
          summary: "Queue depth > 100 for {{ $labels.agent_type }}"
          description: "Current depth: {{ $value }}. Agents may be falling behind."

      # Slow Queries
      - alert: SlowDatabaseQueries
        expr: |
          histogram_quantile(0.95, rate(pg_query_duration_seconds_bucket[5m])) > 5
        for: 3m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "P95 query latency > 5 seconds"
          description: "Query: {{ $labels.query_name }}, P95: {{ $value }}s"

      # API Rate Limit Approaching
      - alert: APIRateLimitApproaching
        expr: external_api_rate_limit_remaining < 100
        for: 1m
        labels:
          severity: warning
          team: integrations
        annotations:
          summary: "{{ $labels.api_name }} rate limit approaching"
          description: "Remaining quota: {{ $value }}"

      # LLM Cost Spike
      - alert: LLMCostSpike
        expr: |
          increase(llm_cost_usd_total[1h]) > 50
        for: 0m
        labels:
          severity: warning
          team: agents
        annotations:
          summary: "LLM cost > $50 in the last hour"
          description: "Current hourly spend: ${{ $value | printf \"%.2f\" }}"

      # Cache Hit Rate Low
      - alert: CacheHitRateLow
        expr: |
          redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total) < 0.80
        for: 10m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Redis cache hit rate < 80%"

      # Pod Restart Loop
      - alert: PodRestartLoop
        expr: increase(kube_pod_container_status_restarts_total[1h]) > 5
        for: 0m
        labels:
          severity: warning
          team: platform
        annotations:
          summary: "Pod {{ $labels.pod }} restarting frequently"
```

### 3.4 Info Alerts → Dashboard Annotations

These don't notify anyone. They annotate Grafana dashboards for correlation during investigations.

```yaml
# /etc/prometheus/rules/info-alerts.yml
groups:
  - name: info-events
    interval: 60s
    rules:

      - alert: AgentCompleted
        expr: increase(agent_execution_total{status="success"}[5m]) > 0
        labels:
          severity: info
          team: agents
        annotations:
          summary: "{{ $value }} agent executions completed in 5m ({{ $labels.agent_type }})"

      - alert: CampaignStatusChange
        expr: increase(campaign_status_changes_total[5m]) > 0
        labels:
          severity: info
          team: product
        annotations:
          summary: "Campaign status changes detected"

      - alert: AnomalyDetected
        expr: seo_anomaly_detected_total > 0
        labels:
          severity: info
          team: seo
        annotations:
          summary: "SEO anomaly detected: {{ $labels.anomaly_type }}"
```

### 3.5 Alertmanager Configuration

```yaml
# alertmanager.yml
global:
  resolve_timeout: 5m
  pagerduty_url: 'https://events.pagerduty.com/v2/enqueue'
  slack_api_url: 'https://hooks.slack.com/services/xxx/yyy/zzz'

route:
  receiver: default
  group_by: ['alertname', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  routes:
    - match:
        severity: critical
      receiver: pagerduty-critical
      group_wait: 10s
      repeat_interval: 15m
    - match:
        severity: warning
      receiver: slack-warnings
      group_wait: 1m
      repeat_interval: 1h
    - match:
        severity: info
      receiver: grafana-annotations
      group_wait: 5m

receivers:
  - name: default
    slack_configs:
      - channel: '#seo-alerts'
        title: '{{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.description }}{{ end }}'

  - name: pagerduty-critical
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        severity: critical
        description: '{{ .GroupLabels.alertname }}: {{ .CommonAnnotations.summary }}'

  - name: slack-warnings
    slack_configs:
      - channel: '#seo-alerts'
        title: '⚠️ {{ .GroupLabels.alertname }}'
        text: '{{ range .Alerts }}{{ .Annotations.summary }}\n{{ .Annotations.description }}{{ end }}'
        send_resolved: true

  - name: grafana-annotations
    webhook_configs:
      - url: 'http://grafana:3000/api/alerts/annotation'
        send_resolved: false

inhibit_rules:
  - source_match:
      severity: critical
    target_match:
      severity: warning
    equal: ['alertname', 'instance']
```

---

## 4. Dashboards

### 4.1 System Health Dashboard

**Grafana dashboard: `SEO Platform — System Health`**

```
┌──────────────────────────────────────────────────────────────────┐
│  Service Status Grid                        [all-green matrix]   │
│  ┌─────────┬─────────┬─────────┬─────────┬─────────┐           │
│  │ API     │ Agents  │ Workers │ DB      │ Redis   │           │
│  │ ● UP    │ ● UP    │ ● UP    │ ● UP    │ ● UP    │           │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘           │
├────────────────────────┬─────────────────────────────────────────┤
│  CPU Usage (per node)  │  Memory Usage (per node)               │
│  [time series, 6h]     │  [time series, 6h]                     │
│  thresholds: 70/85/95  │  thresholds: 70/85/95                  │
├────────────────────────┼─────────────────────────────────────────┤
│  Disk Usage (%)        │  Network I/O (bytes/s)                 │
│  [gauge per node]      │  [time series, tx+rx]                  │
├────────────────────────┼─────────────────────────────────────────┤
│  Error Rate by Service │  Request Latency (P50/P95/P99)         │
│  [stacked area, 1h]    │  [time series, 3 lines]                │
├────────────────────────┼─────────────────────────────────────────┤
│  DB Connections (active│  Redis Memory & Hit Rate               │
│  / idle / waiting)     │  [dual axis: mem gauge + hitrate line] │
│  [stacked area]        │                                        │
└────────────────────────┴─────────────────────────────────────────┘
```

**Key panels and queries:**

| Panel | PromQL |
|-------|--------|
| Service Status | `up` (stat panel, green/red) |
| Error Rate | `sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (service) / sum(rate(http_requests_total[5m])) by (service)` |
| P95 Latency | `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, service))` |
| DB Active Connections | `pg_stat_activity_count{state="active"}` |
| Redis Hit Rate | `redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)` |

### 4.2 Agent Performance Dashboard

**Grafana dashboard: `SEO Platform — Agent Performance`**

```
┌──────────────────────────────────────────────────────────────────┐
│  Active Agents: 12 │ Queue: 47 │ Avg Exec: 4.2s │ Cost/hr: $3.40│
├────────────────────────┬─────────────────────────────────────────┤
│  Execution Time by     │  Success Rate by Agent Type            │
│  Agent Type            │  [gauge per agent_type]                │
│  [histogram heatmap]   │                                        │
├────────────────────────┼─────────────────────────────────────────┤
│  Queue Depth Over Time │  Queue Wait Time (P50/P95)             │
│  [stacked area by      │  [time series by agent_type]           │
│   agent_type]          │                                        │
├────────────────────────┼─────────────────────────────────────────┤
│  LLM Token Usage       │  LLM Cost Breakdown                    │
│  [stacked area: prompt │  [pie chart by model + agent_type]     │
│   vs completion]       │                                        │
├────────────────────────┼─────────────────────────────────────────┤
│  LLM API Latency       │  Agent Failure Reasons                 │
│  [heatmap: model ×     │  [table: agent_type, error, count]     │
│   latency bucket]      │                                        │
└────────────────────────┴─────────────────────────────────────────┘
```

**Key panels and queries:**

| Panel | PromQL |
|-------|--------|
| Queue Depth | `agent_queue_depth` (stat + time series) |
| Success Rate | `sum(rate(agent_execution_total{status="success"}[1h])) by (agent_type) / sum(rate(agent_execution_total[1h])) by (agent_type)` |
| Avg Execution Time | `histogram_quantile(0.50, sum(rate(agent_execution_duration_seconds_bucket[1h])) by (le, agent_type))` |
| Hourly LLM Cost | `sum(increase(llm_cost_usd_total[1h])) by (model)` |
| Token Usage | `sum(increase(llm_tokens_total[1h])) by (token_type, model)` |

### 4.3 Business Metrics Dashboard

**Grafana dashboard: `SEO Platform — Business Metrics`**

```
┌──────────────────────────────────────────────────────────────────┐
│  Active Users: 342 │ Campaigns: 89 │ Links Acquired: 1,247      │
│  Content Published: 456 │ Avg Position Gain: +8.3               │
├────────────────────────┬─────────────────────────────────────────┤
│  Active Users (DAU/WAU)│  Campaigns Created (per day)           │
│  [time series]         │  [bar chart]                           │
├────────────────────────┼─────────────────────────────────────────┤
│  Links Acquired (per   │  Content Pieces Published (per day)    │
│  week, by type)        │  [bar chart by content_type]           │
│  [stacked bar]         │                                        │
├────────────────────────┼─────────────────────────────────────────┤
│  Keyword Ranking        │  Campaign ROI                          │
│  Distribution           │  [scatter: links vs position gain]     │
│  [histogram: position   │                                        │
│   buckets]              │                                        │
├────────────────────────┼─────────────────────────────────────────┤
│  Agent Cost per         │  Revenue Attribution                   │
│  Campaign               │  [sankey: agent → task → outcome]      │
│  [bar chart by          │                                        │
│   campaign_id]          │                                        │
└────────────────────────┴─────────────────────────────────────────┘
```

**Custom business metrics (application code):**

```yaml
# Business metrics emitted by application services
campaigns_created_total:
  type: counter
  labels: [user_id, plan_type]

campaigns_active:
  type: gauge
  labels: [plan_type]

links_acquired_total:
  type: counter
  labels: [campaign_id, link_type]  # link_type: guest_post, directory, niche_edit

content_published_total:
  type: counter
  labels: [campaign_id, content_type]  # content_type: blog, landing_page, product_desc

keyword_rank_changes_total:
  type: counter
  labels: [direction]  # direction: up, down, stable, new

active_users:
  type: gauge
  labels: [plan_type]

user_sessions_active:
  type: gauge
```

---

## 5. Distributed Tracing

### 5.1 OpenTelemetry Integration

**SDK initialization (Python example):**

```python
# tracing.py — called once at app startup
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor

def init_tracing(service_name: str):
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "deployment.environment": "production",
        "service.version": "2.4.1",
    })

    provider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(
        OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True)
    )
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)

    # Auto-instrument libraries
    FastAPIInstrumentor.instrument()
    HTTPXClientInstrumentor.instrument()
    SQLAlchemyInstrumentor.instrument()
    RedisInstrumentor.instrument()

    return trace.get_tracer(service_name)
```

**Node.js equivalent:**

```typescript
// tracing.ts
import { NodeSDK } from '@opentelemetry/sdk-node';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-grpc';
import { Resource } from '@opentelemetry/resources';
import { ATTR_SERVICE_NAME } from '@opentelemetry/semantic-conventions';
import { HttpInstrumentation } from '@opentelemetry/instrumentation-http';
import { ExpressInstrumentation } from '@opentelemetry/instrumentation-express';
import { PgInstrumentation } from '@opentelemetry/instrumentation-pg';
import { RedisInstrumentation } from '@opentelemetry/instrumentation-redis-4';

const sdk = new NodeSDK({
  resource: new Resource({
    [ATTR_SERVICE_NAME]: 'agent-orchestrator',
  }),
  traceExporter: new OTLPTraceExporter({ url: 'http://otel-collector:4317' }),
  instrumentations: [
    new HttpInstrumentation(),
    new ExpressInstrumentation(),
    new PgInstrumentation(),
    new RedisInstrumentation(),
  ],
});
sdk.start();
```

### 5.2 Trace Context Propagation

**W3C Trace Context** is the standard. All services propagate `traceparent` and `tracestate` headers.

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
              │   │                                │                │
              │   trace_id (32 hex)                 │                flags
              version                               span_id (16 hex)
```

**Propagation across async boundaries:**

| Context | Mechanism |
|---------|-----------|
| HTTP → HTTP | `traceparent` header (auto-instrumented) |
| HTTP → RabbitMQ | Message property `traceparent` (custom propagation) |
| RabbitMQ → Worker | Extract from message property |
| Agent → LLM API | `traceparent` header on outgoing HTTP |
| Agent → Agent (sub-agent) | `traceparent` in task payload |

**Custom propagation for message queues:**

```python
from opentelemetry import propagate
from opentelemetry.propagate import inject, extract

# Publishing a message
def publish_task(queue: str, task: dict):
    headers = {}
    inject(headers)  # injects traceparent into headers
    rabbitmq.publish(queue, body=task, headers=headers)

# Consuming a message
def on_message(message):
    ctx = extract(message.headers)
    with tracer.start_as_current_span("process_task", context=ctx):
        process(message.body)
```

### 5.3 Span Creation

**Auto-instrumented spans (no code needed):**

- `HTTP GET /api/v1/campaigns` — server span
- `HTTP GET https://api.openai.com/v1/chat/completions` — client span
- `SELECT * FROM campaigns WHERE id = $1` — database span
- `GET seo:campaign:cmp-456:keywords` — Redis span

**Manual spans (custom business logic):**

```python
from opentelemetry import trace

tracer = trace.get_tracer("agent-orchestrator")

async def execute_agent(agent_type: str, task: dict):
    with tracer.start_as_current_span(
        "agent.execute",
        attributes={
            "agent.type": agent_type,
            "agent.task_id": task["id"],
            "campaign.id": task["campaign_id"],
        }
    ) as span:
        try:
            # Sub-span: build prompt
            with tracer.start_as_current_span("agent.build_prompt"):
                prompt = build_prompt(agent_type, task)

            # Sub-span: call LLM
            with tracer.start_as_current_span(
                "agent.llm_call",
                attributes={
                    "llm.model": "gpt-4o",
                    "llm.tokens.prompt": len(prompt),
                }
            ):
                response = await llm_client.complete(prompt)

            # Sub-span: parse output
            with tracer.start_as_current_span("agent.parse_output"):
                result = parse_output(response)

            span.set_attribute("agent.tokens_used", response.usage.total_tokens)
            span.set_attribute("agent.cost_usd", response.cost)
            span.set_status(trace.StatusCode.OK)
            return result

        except Exception as e:
            span.set_status(trace.StatusCode.ERROR, str(e))
            span.record_exception(e)
            raise
```

### 5.4 Trace Visualization

**Stack: Grafana Tempo** (pairs with Loki and Prometheus in the Grafana ecosystem)

```
┌────────────────────┐
│  Application       │
│  (OTLP gRPC)       │
└─────────┬──────────┘
          │
          ▼
┌────────────────────┐     ┌──────────────────┐
│  OTel Collector    │────▶│  Grafana Tempo   │
│  • receive         │     │  • trace storage │
│  • batch           │     │  • search        │
│  • export          │     │  • TraceQL       │
│  • tail sampling   │     │  • S3 backend    │
└────────────────────┘     └────────┬─────────┘
                                    │
                                    ▼
                           ┌──────────────────┐
                           │  Grafana         │
                           │  • Explore: traces│
                           │  • Exemplar links│
                           │  • Trace → Logs  │
                           └──────────────────┘
```

**TraceQL query examples:**

```traceql
# All traces for a campaign
{ campaign.id = "cmp-456" }

# Slow agent executions
{ span.agent.type = "content-writer" && duration > 10s }

# Errors in LLM calls
{ span.llm.model = "gpt-4o" && status = error }

# Traces that hit both Redis and OpenAI
{ span.db.system = "redis" } >> { span.http.url = "https://api.openai.com/*" }
```

**Exemplar links:** Every Prometheus metric with an `exemplar` links directly to a trace in Tempo. Clicking a slow-request data point on the latency graph opens the exact trace.

### 5.5 OTel Collector Configuration

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 5s
    send_batch_size: 1024

  tail_sampling:
    decision_wait: 10s
    policies:
      # Always sample errors
      - name: errors
        type: status_code
        status_code: { status_codes: [ERROR] }
      # Always sample slow traces
      - name: slow-traces
        type: latency
        latency: { threshold_ms: 5000 }
      # Sample 10% of normal traces
      - name: normal
        type: probabilistic
        probabilistic: { sampling_percentage: 10 }

  attributes:
    actions:
      - key: environment
        value: production
        action: upsert

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true

  prometheus:
    endpoint: 0.0.0.0:8889

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch, tail_sampling, attributes]
      exporters: [otlp/tempo]
```

---

## 6. Health Checks

### 6.1 Liveness Probe — `GET /health`

Returns 200 if the process is alive and can handle requests. Used by Kubernetes to decide whether to restart the container.

```python
# health.py
from fastapi import APIRouter, Response
import asyncio

router = APIRouter()

@router.get("/health")
async def health(response: Response):
    """
    Liveness probe. Returns 200 if the process is running.
    Does NOT check dependencies — that's /ready.
    """
    return {"status": "ok", "service": "agent-orchestrator", "version": "2.4.1"}
```

**Kubernetes configuration:**

```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 15
  timeoutSeconds: 3
  failureThreshold: 3
```

### 6.2 Readiness Probe — `GET /ready`

Returns 200 if the service can accept work (dependencies are healthy). Used by Kubernetes to remove the pod from the Service load balancer when it's not ready.

```python
@router.get("/ready")
async def ready(response: Response):
    """
    Readiness probe. Checks all critical dependencies.
    Returns 503 if any dependency is unhealthy.
    """
    checks = {}
    all_ok = True

    # Database
    try:
        async with db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        all_ok = False

    # Redis
    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"
        all_ok = False

    # LLM API (head request, not a real call)
    try:
        resp = await http_client.head("https://api.openai.com/v1/models", timeout=2)
        checks["llm_api"] = "ok" if resp.status_code < 500 else f"status={resp.status_code}"
        if resp.status_code >= 500:
            all_ok = False
    except Exception as e:
        checks["llm_api"] = f"error: {str(e)}"
        all_ok = False

    # Message Queue
    try:
        await mq_channel.queue_declare(queue="health-check", passive=True)
        checks["message_queue"] = "ok"
    except Exception as e:
        checks["message_queue"] = f"error: {str(e)}"
        all_ok = False

    status_code = 200 if all_ok else 503
    response.status_code = status_code

    return {
        "status": "ready" if all_ok else "not_ready",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    }
```

**Kubernetes configuration:**

```yaml
readinessProbe:
  httpGet:
    path: /ready
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
```

### 6.3 Startup Probe — `GET /startup`

For slow-starting services (e.g., ones that load ML models or warm caches).

```yaml
startupProbe:
  httpGet:
    path: /health
    port: 8000
  failureThreshold: 30
  periodSeconds: 10
  # Gives up to 5 minutes to start
```

### 6.4 Dependency Check Matrix

| Dependency | Check Method | Timeout | Impact if Down | Graceful Degradation |
|-----------|-------------|---------|---------------|---------------------|
| PostgreSQL | `SELECT 1` | 2s | **Critical** — return 503 | Queue writes locally, retry |
| Redis | `PING` | 1s | **Critical** — return 503 | Serve from DB (slower) |
| LLM API | HEAD request | 3s | **Warning** — continue with degraded | Use cached responses, skip AI tasks |
| External SEO APIs | HEAD request | 3s | **Warning** — continue | Use stale data, mark as degraded |
| Message Queue | Queue declare (passive) | 2s | **Critical** — return 503 | Process inline (no queuing) |
| S3/Storage | HEAD bucket | 2s | **Warning** — continue | Write to local disk temporarily |

### 6.5 Graceful Degradation Patterns

```python
class DegradationManager:
    """Circuit breaker + fallback for each dependency."""

    def __init__(self):
        self.circuits: dict[str, CircuitBreaker] = {}

    def register(self, name: str, fallback=None, failure_threshold=5, recovery_timeout=30):
        self.circuits[name] = CircuitBreaker(
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            fallback=fallback,
        )

    async def call(self, name: str, func, *args, **kwargs):
        circuit = self.circuits[name]
        if circuit.is_open:
            if circuit.fallback:
                return await circuit.fallback(*args, **kwargs)
            raise DependencyUnavailable(name)
        try:
            result = await func(*args, **kwargs)
            circuit.record_success()
            return result
        except Exception as e:
            circuit.record_failure()
            if circuit.fallback:
                return await circuit.fallback(*args, **kwargs)
            raise

# Registration
degradation = DegradationManager()
degradation.register("llm_api", fallback=cached_llm_response, failure_threshold=3)
degradation.register("seo_api", fallback=stale_seo_data, failure_threshold=5)
degradation.register("search_console", fallback=skip_and_retry_later)
```

---

## 7. Incident Management

### 7.1 Severity Levels

| Severity | Definition | Response Time | Resolution Target | Examples |
|----------|-----------|---------------|-------------------|----------|
| **SEV-1** | Complete outage or data loss | 5 minutes | 1 hour | All services down, DB corruption |
| **SEV-2** | Major feature broken, no workaround | 15 minutes | 4 hours | Agent execution halted, LLM integration down |
| **SEV-3** | Feature degraded, workaround exists | 30 minutes | 24 hours | Slow queries, intermittent API failures |
| **SEV-4** | Minor issue, cosmetic | Next business day | 1 week | Dashboard glitch, non-critical log noise |

### 7.2 On-Call Rotation

**Tool:** PagerDuty schedules (or OpsGenie)

```
Primary on-call:   Weekly rotation, Monday 09:00 UTC → Monday 09:00 UTC
Secondary on-call: Weekly rotation, offset by 1 week
Weekend on-call:   Friday 17:00 → Monday 09:00 (same primary)

Team structure:
  Platform team:  2 engineers per rotation (infrastructure, DB, networking)
  Agent team:     1 engineer per rotation (agents, LLM, queues)
  SEO team:       1 engineer per rotation (business logic, data pipeline)

Handoff: 15-minute overlap meeting, recorded in #seo-ops Slack channel.
```

**Escalation policy:**

```
T+0 min:   Alert fires → PagerDuty notifies primary on-call (push + call)
T+5 min:   No ack → PagerDuty notifies secondary on-call
T+10 min:  No ack → PagerDuty notifies team lead
T+15 min:  No ack → PagerDuty notifies VP Engineering
T+30 min:  No ack → PagerDuty notifies CTO

Auto-escalation rules:
  SEV-1: starts at T+0, escalates every 5 minutes
  SEV-2: starts at T+0, escalates every 10 minutes
  SEV-3: Slack only, no auto-escalation
```

### 7.3 Runbooks

Every alert has a linked runbook. Runbooks live in Confluence/Notion and are linked in the alert annotation.

**Runbook template:**

```markdown
# Runbook: [Alert Name]

## Summary
What this alert means and why it fires.

## Impact
Who/what is affected and how severely.

## Diagnosis Steps
1. Check Grafana dashboard: [link]
2. Check Loki logs: `{service="X", level="ERROR"}` (last 1h)
3. Check recent deploys: `kubectl rollout history deployment/X`
4. Check infrastructure: node CPU, memory, disk

## Mitigation Steps
1. [Immediate action to restore service]
2. [If that fails, escalation action]
3. [If data integrity at risk, preservation action]

## Root Cause Patterns
- Common cause 1: [description + fix]
- Common cause 2: [description + fix]

## Related Alerts
- [Alert that often co-occurs]
- [Upstream/downstream alert]

## Post-Incident
- Create post-mortem if SEV-1 or SEV-2
- Update this runbook if new root cause discovered
```

**Runbook inventory:**

| Alert | Runbook | Link |
|-------|---------|------|
| ServiceDown | Restart pod, check node health, review recent deploys | `runbooks/service-down.md` |
| DatabaseConnectionLost | Check PgBouncer, check disk, failover to replica | `runbooks/db-connection.md` |
| MemoryCritical | Identify memory hog (top), restart pod, scale up | `runbooks/memory-critical.md` |
| ErrorRateCritical | Check logs for error pattern, rollback if regression | `runbooks/error-rate.md` |
| AgentFailureRateHigh | Check LLM API status, check queue backlog, restart workers | `runbooks/agent-failures.md` |
| APIRateLimitApproaching | Reduce scrape frequency, activate cache, notify team | `runbooks/rate-limit.md` |

### 7.4 Post-Mortem Process

**Trigger:** Any SEV-1 or SEV-2 incident. SEV-3 if recurring (>2 in a week).

**Timeline:**

| Step | Deadline | Owner |
|------|----------|-------|
| Incident channel created | T+0 (automatic) | PagerDuty |
| Incident commander assigned | T+5 min | Primary on-call |
| Customer communication (if needed) | T+30 min | Support lead |
| Post-mortem draft | T+48 hours | Incident commander |
| Post-mortem review meeting | T+72 hours | Team |
| Action items assigned | During review | Team |
| Action items completed | +2 weeks | Assignees |

**Post-mortem template:**

```markdown
# Post-Mortem: [Title]

## Metadata
- **Date:** YYYY-MM-DD
- **Duration:** X hours Y minutes
- **Severity:** SEV-N
- **Incident Commander:** @name
- **Author:** @name

## Summary
One paragraph describing what happened.

## Impact
- Users affected: N
- Revenue impact: $X
- Data loss: Yes/No
- Duration of impact: X hours

## Timeline (UTC)
| Time | Event |
|------|-------|
| 14:32 | Alert fired: ServiceDown |
| 14:35 | IC acknowledged, began diagnosis |
| 14:42 | Root cause identified: bad deploy |
| 14:45 | Rollback initiated |
| 14:52 | Service restored |

## Root Cause
Detailed technical explanation.

## Contributing Factors
- Factor 1: Insufficient pre-deploy testing
- Factor 2: Missing canary deployment

## What Went Well
- Fast alert detection
- Clear runbook enabled quick mitigation

## What Went Wrong
- Rollback took 7 minutes (should be <2)
- No automated rollback on error rate spike

## Action Items
| ID | Action | Owner | Priority | Due |
|----|--------|-------|----------|-----|
| 1 | Add canary deployment stage | @alice | High | +2 weeks |
| 2 | Auto-rollback on error >5% | @bob | High | +2 weeks |
| 3 | Add load test to CI | @charlie | Medium | +1 month |
```

---

## 8. Performance Monitoring

### 8.1 Real User Monitoring (RUM)

**Tool:** Grafana Faro (web SDK) or Sentry Performance.

**What we track:**

```javascript
// Initialize Faro RUM SDK
import { initializeFaro } from '@grafana/faro-web-sdk';

initializeFaro({
  url: 'https://faro.example.com/collect',
  app: {
    name: 'seo-platform-frontend',
    version: '2.4.1',
    environment: 'production',
  },
  instrumentations: [
    // Auto-captures: page loads, navigation, XHR, errors
  ],
});
```

**RUM metrics collected:**

| Metric | Source | Target |
|--------|--------|--------|
| Page load time | Navigation Timing API | < 2s (P95) |
| Time to First Byte (TTFB) | Navigation Timing API | < 200ms (P95) |
| First Contentful Paint (FCP) | Paint Timing API | < 1.5s (P95) |
| Largest Contentful Paint (LCP) | LCP API | < 2.5s (P95) |
| First Input Delay (FID) | Event Timing API | < 100ms (P95) |
| Cumulative Layout Shift (CLS) | Layout Instability API | < 0.1 (P95) |
| Interaction to Next Paint (INP) | Event Timing API | < 200ms (P95) |
| JavaScript errors | Error event listener | < 0.1% of sessions |
| API call latency (client-side) | XHR/Fetch interceptor | < 500ms (P95) |

### 8.2 Core Web Vitals Tracking

**Collected via RUM SDK and surfaced in Grafana:**

```
┌────────────────────────────────────────────────────────────┐
│  Core Web Vitals — SEO Platform Dashboard                  │
│                                                            │
│  LCP:  1.8s  [████████░░] Good (< 2.5s)                  │
│  FID:   45ms [██████░░░░] Good (< 100ms)                  │
│  CLS:  0.05  [████████░░] Good (< 0.1)                    │
│  INP:  120ms [███████░░░] Good (< 200ms)                  │
│  TTFB:  180ms[███████░░░] Good (< 200ms)                  │
│  FCP:  1.2s  [████████░░] Good (< 1.5s)                  │
│                                                            │
│  Page Breakdown:                                           │
│  ┌─────────────┬──────┬──────┬──────┬──────┐             │
│  │ Page        │ LCP  │ FID  │ CLS  │ INP  │             │
│  ├─────────────┼──────┼──────┼──────┼──────┤             │
│  │ /dashboard  │ 1.2s │ 32ms │ 0.02 │ 95ms │             │
│  │ /campaigns  │ 1.8s │ 45ms │ 0.05 │ 120ms│             │
│  │ /keywords   │ 2.1s │ 67ms │ 0.08 │ 180ms│             │
│  │ /reports    │ 2.4s │ 89ms │ 0.12 │ 210ms│ ⚠️          │
│  └─────────────┴──────┴──────┴──────┴──────┘             │
└────────────────────────────────────────────────────────────┘
```

**Alert on CWV regression:**

```yaml
- alert: CoreWebVitalsRegression
  expr: histogram_quantile(0.75, sum(rate(web_vitals_lcp_bucket[1d])) by (le)) > 2.5
  for: 0m
  labels:
    severity: warning
    team: frontend
  annotations:
    summary: "LCP P75 has regressed above 2.5s threshold"
```

### 8.3 API Performance Profiling

**Middleware that measures every request:**

```python
@app.middleware("http")
async def performance_middleware(request: Request, call_next):
    start = time.perf_counter()

    # Track connection pool wait time
    db_wait_start = time.perf_counter()
    # ... actual request processing ...
    response = await call_next(request)

    duration = time.perf_counter() - start

    # Record metrics
    REQUEST_DURATION.labels(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
    ).observe(duration)

    # Slow request logging
    if duration > 2.0:
        logger.warning(
            "slow_request",
            method=request.method,
            path=request.url.path,
            duration_ms=round(duration * 1000, 2),
            status_code=response.status_code,
        )

    # Add timing header
    response.headers["X-Response-Time"] = f"{duration:.3f}s"
    return response
```

**API performance targets:**

| Endpoint Category | P50 | P95 | P99 |
|-------------------|-----|-----|-----|
| GET (read, cached) | < 20ms | < 50ms | < 100ms |
| GET (read, DB) | < 50ms | < 200ms | < 500ms |
| POST (write) | < 100ms | < 500ms | < 1s |
| POST (agent trigger) | < 200ms | < 1s | < 2s |
| WebSocket message | < 10ms | < 30ms | < 50ms |

### 8.4 Database Query Optimization

**Slow query logging (PostgreSQL):**

```sql
-- postgresql.conf
log_min_duration_statement = 200    -- Log queries > 200ms
log_statement = 'none'              -- Don't log all statements
log_line_prefix = '%t [%p] %u@%d '
```

**Application-level query tracking:**

```python
from sqlalchemy import event

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault("query_start", []).append(time.perf_counter())

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    duration = time.perf_counter() - conn.info["query_start"].pop()

    QUERY_DURATION.labels(
        query_name=_extract_query_name(statement),
        database=conn.engine.url.database,
    ).observe(duration)

    if duration > 1.0:
        logger.warning(
            "slow_query",
            query=statement[:500],
            duration_ms=round(duration * 1000, 2),
            parameters=str(parameters)[:200],
        )
```

**Query performance dashboard (Grafana):**

| Panel | Metric |
|-------|--------|
| Query duration P50/P95/P99 | `histogram_quantile(0.95, rate(pg_query_duration_seconds_bucket[5m]))` |
| Queries per second | `rate(pg_stat_database_tup_fetched[5m])` |
| Slow query count (>200ms) | `sum(pg_slow_queries_total) by (query_name)` |
| Connection pool utilization | `pg_stat_activity_count / pg_settings_max_connections` |
| Cache hit ratio | `pg_stat_database_blks_hit / (pg_stat_database_blks_hit + pg_stat_database_blks_read)` |
| Table bloat | Custom metric from `pgstattuple` |

**Automated index recommendations:**

```python
# Weekly job: analyze slow queries and suggest indexes
async def suggest_indexes():
    """Query pg_stat_statements for slow queries without index support."""
    query = """
        SELECT
            queryid,
            query,
            calls,
            mean_exec_time,
            total_exec_time,
            rows
        FROM pg_stat_statements
        WHERE mean_exec_time > 100  -- > 100ms average
          AND calls > 10            -- called more than 10 times
        ORDER BY total_exec_time DESC
        LIMIT 20
    """
    slow_queries = await db.fetch(query)
    for q in slow_queries:
        explain = await db.fetch(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {q['query']}")
        if "Seq Scan" in str(explain):
            # Alert: potential missing index
            logger.warning("missing_index_suggestion", query=q['query'], explain=explain)
```

### 8.5 Cache Hit Rate Monitoring

**Redis cache metrics:**

```yaml
# Prometheus metrics from redis_exporter
redis_keyspace_hits_total: counter
redis_keyspace_misses_total: counter
redis_memory_used_bytes: gauge
redis_memory_max_bytes: gauge
redis_evicted_keys_total: counter
redis_connected_clients: gauge
redis_commands_processed_total: counter
redis_command_duration_seconds: histogram
```

**Derived cache metrics (PromQL):**

```promql
# Cache hit rate (global)
redis_keyspace_hits_total / (redis_keyspace_hits_total + redis_keyspace_misses_total)

# Cache hit rate by key pattern (custom exporter)
cache_hit_rate_by_pattern{pattern="seo:keyword:*"}

# Memory utilization
redis_memory_used_bytes / redis_memory_max_bytes

# Eviction rate (indicates memory pressure)
rate(redis_evicted_keys_total[5m])

# Cache latency
histogram_quantile(0.99, rate(redis_command_duration_seconds_bucket[5m]))
```

**Cache performance targets:**

| Metric | Target | Alert if |
|--------|--------|----------|
| Hit rate (global) | > 90% | < 80% for 10 min |
| Hit rate (keyword data) | > 95% | < 90% for 10 min |
| Hit rate (session data) | > 99% | < 95% for 5 min |
| P99 latency | < 1ms | > 5ms for 5 min |
| Memory utilization | < 70% | > 85% |
| Eviction rate | ~0 | > 100/min for 5 min |

**Cache dashboard:**

```
┌──────────────────────────────────────────────────────────┐
│  Cache Performance — Redis                               │
│                                                          │
│  Hit Rate: 94.2% [███████████████████░░] Target: 90%    │
│  Memory:   62%   [████████████░░░░░░░░░] Max: 8 GB      │
│  Evictions: 0/s                                         │
│  P99 Latency: 0.3ms                                     │
│                                                          │
│  Hit Rate by Pattern (24h):                             │
│  ┌────────────────────┬────────┐                        │
│  │ Pattern            │ Hit %  │                        │
│  ├────────────────────┼────────┤                        │
│  │ seo:keyword:*      │ 97.2%  │                        │
│  │ seo:campaign:*     │ 95.1%  │                        │
│  │ seo:session:*      │ 99.8%  │                        │
│  │ seo:api-cache:*    │ 88.4%  │ ⚠️                     │
│  │ seo:rate-limit:*   │ 99.9%  │                        │
│  └────────────────────┴────────┘                        │
└──────────────────────────────────────────────────────────┘
```

---

## Appendix A: Observability Stack Summary

| Layer | Tool | Purpose |
|-------|------|---------|
| **Metrics** | Prometheus + Thanos | Time-series metrics, long-term storage |
| **Dashboards** | Grafana | Visualization, alerting, exploration |
| **Logs** | Loki + Promtail | Structured log aggregation |
| **Traces** | Grafana Tempo | Distributed trace storage & query |
| **RUM** | Grafana Faro | Real user monitoring, Core Web Vitals |
| **Alerting** | Alertmanager + PagerDuty + Slack | Multi-channel alert routing |
| **Collection** | OpenTelemetry Collector | Unified telemetry pipeline |
| **Profiling** | Pyroscope / Parca | Continuous profiling (CPU, memory) |

## Appendix B: Alert Fatigue Prevention

| Strategy | Implementation |
|----------|---------------|
| Alert review | Monthly review of all alerts — delete or tune noisy ones |
| SLO-based alerting | Alert on error budgets, not raw metrics |
| Multi-window burn rate | Fast burn (1h) AND slow burn (6d) must both fire |
| Inhibition rules | Suppress WARNING when CRITICAL is active for same issue |
| Grouping | Alertmanager groups related alerts, reduces noise |
| Silence for maintenance | Scheduled silences during planned windows |
| Minimum alert interval | `repeat_interval: 4h` for warnings, `15m` for critical |

## Appendix C: SLO Definitions

| Service | SLI | SLO | Error Budget (30d) |
|---------|-----|-----|--------------------|
| API Gateway | Successful requests / total requests | 99.9% | 43.2 min downtime |
| Agent Orchestrator | Successful executions / total executions | 99.5% | 3.6 hours |
| LLM Gateway | Successful API calls / total API calls | 99.0% | 7.2 hours |
| Data Pipeline | On-time deliveries / scheduled deliveries | 99.5% | 3.6 hours |
| Dashboard | Page load < 3s / total page loads | 99.0% | 7.2 hours |
