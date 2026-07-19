# Operations Runbook

## Service unavailable

1. Confirm the alert scope and compare liveness, readiness, and startup probe failures.
2. Check recent ArgoCD synchronization and Kubernetes events before restarting workloads.
3. Inspect correlated traces, then JSON logs by `request_id`, `trace_id`, service, tenant, and agent run.
4. If the failure follows a release, stop rollout and revert to the previous immutable image.
5. If PostgreSQL or Redis is unavailable, pause workers before recovery to avoid retry amplification.

## Provider degradation

Circuit breakers open after repeated transient failures. Keep queued work idempotent and allow jittered
retry. Disable only the affected adapter, expose partial failure in the UI, and preserve last-known
data. Do not switch to an unapproved SEO data provider. Resume after a read-only health probe succeeds.

## Queue and DLQ backlog

Check budget exhaustion, provider latency, poison messages, and worker capacity. Replay a DLQ message
only after validating tenant context, idempotency key, expiry, and approval state. Never bulk replay
email or publication tasks.

## Database restore

Restore the latest automated snapshot into an isolated cluster, replay point-in-time logs to the
target, run schema and row-count verification, then test RLS with two tenants. Promote through a DNS
or connection-secret update only after the application smoke suite passes.

## Security incident

Revoke affected sessions and API keys, rotate provider credentials, preserve audit evidence, and block
malicious IPs at Cloudflare before the application. Treat refresh-token reuse and webhook replay as
security events. Follow legal notification requirements defined by the organization's incident policy.

## SLO gates

- API availability: 99.9% monthly.
- Read endpoint p95: below 500 ms excluding asynchronous provider completion.
- Agent command acknowledgement p95: below 750 ms.
- 5xx ratio: below 1%; rollback threshold is 5% for ten minutes.
- Critical queue age: below five minutes.

