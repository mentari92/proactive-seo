# Canonical Contract Reconciliation

This file records executable resolutions where the blueprint documents disagree. The current
implementation prompt has highest precedence, followed by public blueprint contracts, current
provider documentation, and finally draft code examples.

| Concern | Canonical resolution |
|---|---|
| Frontend runtime | The patched Next.js 15.5 line is the nearest secure App Router release; Next.js 14 has unresolved high-severity advisories and is not shipped. |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Celery; Node/Nest examples are historical. |
| Async transport | Redis is the Celery broker/result store and Redis Streams is the event bus. |
| Identity | Native OAuth 2.0/OIDC integration with platform-managed RS256 JWTs, MFA, RBAC, and Redis sessions. |
| Tokens | Access tokens expire after 15 minutes; rotating refresh-token families expire after seven days. |
| Search data | DataForSEO replaces SerpAPI and Ahrefs for SERP, keyword, and backlink data. |
| Outreach | Gmail is the only email execution provider; live sending is approval- and environment-gated. |
| Logs and search | Loki stores logs and PostgreSQL FTS handles product search; no OpenSearch/Elasticsearch. |
| IDs | PostgreSQL UUIDs are authoritative and external identifiers use a reversible typed prefix codec. |
| Campaign state | Campaigns use draft/active/paused/completed/archived. Contacts use draft/sent/replied/negotiating/live/rejected. |
| Database | The logical model is exactly 37 application tables. Initial high-volume tables are not partitioned so UUID PK/FK contracts remain valid. |
| RLS | Tenant policies quote schema/table identifiers separately; permissions isolate through their role's organization. |
| OpenAI | Responses API plus strict structured outputs. GPT-5.6 family is role-routed; GPT-4o is a disabled legacy alias. |
| Observability | Prometheus, Grafana, Loki, Tempo, OpenTelemetry, and Alertmanager are canonical. |
