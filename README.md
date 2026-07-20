# ProActive SEO

Enterprise-Grade SEO Automation Platform — **87% task automation** with autonomous AI agents.

---

## Overview

ProActive SEO is a comprehensive SEO automation platform that uses 8 autonomous AI agents to handle every aspect of search engine optimization — from technical audits and content creation to link building and rank tracking.

### Key Features

- **8 Autonomous AI Agents** — Crawler (Sentinel), Technical, Content (Forge), Rank (Scout), Outreach, Competitor, Decision Engine, Action Executor
- **Multi-Engine SERP Tracking** — Google, Bing, Yandex, Naver via DataForSEO integration
- **AI-Powered Content** — Dual-scoring (AEO + GEO), automated briefs and drafts
- **Outreach Automation** — Broken link building, guest posts, HARO responses via Gmail API
- **Real-Time Monitoring** — Prometheus metrics, Grafana dashboards, Loki logging, Tempo tracing, OpenTelemetry
- **Enterprise Security** — OAuth 2.0 + JWT, MFA (TOTP), RBAC, WAF, field-level encryption
- **Cloud-Native** — Docker Compose (dev), Kubernetes + Helm (prod), Terraform (AWS + Cloudflare)

---

## Architecture

```
                        +------------------+
                        |    Cloudflare    |
                        |    CDN + WAF     |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |   Next.js 15 SPA |
                        |   (apps/web/)    |
                        +--------+---------+
                                 |
                        +--------v---------+
                        |   FastAPI API    |
                        |  (aggregate/svc) |
                        +---+----+----+----+
                            |    |    |
               +------------+    |    +------------+
               |                 |                 |
      +--------v-------+ +------v-------+ +-------v--------+
      |   PostgreSQL   | |    Redis     | |    Celery      |
      |  (16, 37 tbls) | | (Cache/Queue)| |  (Workers)     |
      +----------------+ +--------------+ +-------+--------+
                                                   |
           +--------------------------------------+
           |       14 Independently Deployable Services        |
           |  auth | tenant | keyword | crawl | content | rank |
           | serp | analytics | notification | billing | report |
           |   link-analysis | ai | audit                       |
           +----------------------------------------------------+
                              |
           +------------------+------------------+
           |                  |                  |
     +-----v------+    +-----v------+    +------v-----+
     |  8 Agents  |    |   Events   |    |  External  |
     | (Crawl,    |    |   Bus      |    |  APIs      |
     |  Content,  |    | (Redis     |    | (DataForSEO|
     |  Technical,|    |  pub/sub)  |    |  GSC, Gmail|
     |  Rank,     |    |            |    |  Exa,      |
     |  Outreach, |    |            |    |  Tavily)   |
     |  Competitor|    |            |    |            |
     |  Decision, |    |            |    |            |
     |  Executor) |    |            |    |            |
     +------------+    +------------+    +------------+
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic |
| **Frontend** | Next.js 15 App Router, TypeScript, Tailwind CSS, shadcn/ui |
| **Database** | PostgreSQL 16 (37 tables, multi-tenant RLS) + Redis 7 |
| **Task Queue** | Celery + Redis broker |
| **LLM** | Codex |
| **Monitoring** | Prometheus, Grafana, Loki, Tempo, OpenTelemetry |
| **Security** | OAuth 2.0 + JWT, MFA (TOTP), RBAC, WAF, AES-256-GCM encryption |
| **Integrations** | DataForSEO, Google Search Console, GA4, Gmail API, Bing Webmaster, Exa AI, Tavily, PageSpeed Insights |
| **Infrastructure** | Docker Compose (dev), Kubernetes + Helm + ArgoCD (prod), Terraform (AWS + Cloudflare) |

---

## Quick Start

### Prerequisites

- Python 3.12
- Node.js 20
- pnpm 9
- Docker + Docker Compose

### Local Development

```bash
# Clone the repository
git clone https://github.com/mentari92/proactive-seo.git
cd proactive-seo

# Copy environment configuration
cp .env.example .env

# Install backend dependencies
uv sync --extra dev

# Install frontend dependencies
pnpm install

# Start core services (PostgreSQL, Redis, API, Frontend)
docker compose --profile core up --build
```

The local dashboard is served at `http://localhost:3000`, the aggregate API at
`http://localhost:8000`, and development OpenAPI documentation at `http://localhost:8000/docs`.

### Start All Services (Including Agents)

```bash
docker compose --profile full up --build
```

This starts all 27 services including all 14 microservices, Celery workers, observability stack, and monitoring.

---

## API Documentation

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Liveness probe |
| `GET /ready` | Readiness probe (checks DB, Redis, Celery) |
| `GET /metrics` | Prometheus metrics endpoint |
| `GET /docs` | Swagger UI (development mode only) |
| `GET /redoc` | ReDoc (development mode only) |
| `POST /api/v1/auth/register` | User registration |
| `POST /api/v1/auth/login` | User login (returns JWT) |
| `GET /api/v1/organizations` | List organizations |
| `GET /api/v1/projects` | List projects |
| `GET /api/v1/users` | List users |

Full API documentation is available at `/docs` when running in development mode. All 97 endpoints are defined in `contracts/api-v1.yaml`.

---

## Project Structure

```
proactive-seo/
├── apps/web/                # Next.js 15 product application (50+ pages)
│   ├── app/                 # App Router pages (dashboard, settings, auth)
│   ├── components/          # shadcn/ui components
│   └── lib/                 # API client, auth store, routing
├── packages/
│   └── proactive_core/      # Shared runtime package
│       ├── agents/          # 8 AI agents + source_agents/ (legacy business logic)
│       ├── api/             # FastAPI app factory, schemas, store
│       ├── db/              # SQLAlchemy models (37 tables), session
│       ├── integrations/    # External API clients (DataForSEO, Gmail, Exa, Tavily, etc.)
│       ├── events.py        # Redis pub/sub event bus
│       ├── celery_app.py    # Celery configuration and routing
│       ├── auth.py          # OAuth 2.0 + JWT authentication
│       └── security.py      # Encryption, WAF, rate limiter
├── services/                # 14 independently deployable FastAPI services
│   ├── auth-service/        # Authentication and authorization
│   ├── crawl-service/       # Web crawling agent
│   ├── content-service/     # Content analysis and generation
│   ├── rank-tracker-service/# SERP position tracking
│   ├── ai-service/          # LLM integration
│   └── ...                  # (9 more services)
├── contracts/               # Canonical API, table, enum, agent, and provider manifests
├── alembic/                 # PostgreSQL migrations (37 tables, RLS)
├── infrastructure/          # Deployment configuration
│   ├── kubernetes/          # Helm chart + ArgoCD for K8s deployment
│   └── terraform/           # AWS EKS/RDS/ElastiCache + Cloudflare Terraform
├── observability/           # Monitoring stack configuration
│   ├── prometheus/          # Prometheus config + alert rules
│   ├── grafana/             # Pre-built dashboards + provisioning
│   ├── loki/                # Log aggregation
│   ├── tempo/               # Distributed tracing
│   └── otel/                # OpenTelemetry collector
├── tests/                   # Test suites
│   ├── unit/                # Unit tests (agents, tasks, auth, etc.)
│   ├── integration/         # Integration tests (PostgreSQL, Redis)
│   └── contract/            # Contract tests (API manifests)
└── docs/                    # Product documentation (PRD, architecture, etc.)
```

---

## Agents

| Agent | Codex Name | Purpose | Trigger |
|-------|-----------|---------|---------|
| **Crawler** | Sentinel | Multi-engine crawl, broken link detection, index monitoring | Scheduled / on-demand |
| **Technical** | Technical | CWV monitoring, schema generation, self-healing (8 issue types) | Post-crawl |
| **Content** | Forge | Audit, dual scoring (Google + AI Readiness), AEO/GEO optimization | On-demand |
| **Rank** | Scout | SERP tracking, position alerts, competitor comparison | Scheduled daily |
| **Outreach** | Outreach | HARO responses, broken link building, guest posts, unlinked mentions | Campaign-based |
| **Competitor** | Competitor | Content monitoring, keyword stealing, backlink gap analysis | Scheduled weekly |
| **Decision** | Decision Engine | Priority scoring, resource allocation, proactive triggers | Event-driven |
| **Executor** | Action Executor | Auto-fix, email sending, content publishing, rollback management | On approval |

Each agent integrates with the shared provider layer for DataForSEO, Exa AI, Tavily, Gmail API, and Google Search Console.

---

## Monitoring

### Metrics (Prometheus)

All services expose `/metrics` in Prometheus exposition format:

- **HTTP** — Request rate, latency (P50/P95/P99), error rate
- **Agents** — Execution time, success rate, queue depth
- **LLM** — API calls, tokens used, cost per call
- **External APIs** — Call count, latency, rate limits
- **Business** — Campaigns created, links acquired, content published

### Dashboards (Grafana)

Pre-built dashboards in `observability/grafana/`:

- **ProActive Overview** — System health, agent performance, business metrics
- **Agent Performance** — Execution times, queue depth, costs
- **Business Metrics** — Active users, campaigns, links, content

### Logging & Tracing

- **Loki** — Structured JSON log aggregation with correlation IDs
- **Tempo** — Distributed tracing across all 14 microservices
- **OpenTelemetry** — Unified telemetry collection

### Alerting

Alert rules in `observability/prometheus/rules.yml`:

- **Critical** — Service down, DB connection lost, error rate > 5%
- **Warning** — Memory > 70%, queue depth > 100, slow queries
- **Info** — Agent completions, campaign changes, anomalies

---

## Security

### Authentication

- OAuth 2.0 Authorization Code Flow with PKCE
- JWT access tokens (RS256, 1-hour expiry)
- Refresh token rotation with replay detection
- MFA via TOTP (Google Authenticator compatible)

### Authorization

- Role-Based Access Control (RBAC)
- Multi-tenant row-level security (RLS) on PostgreSQL
- Organization-scoped data isolation

### API Security

- Redis-based rate limiting (per-user and per-IP, sliding window)
- Web Application Firewall (SQL injection, XSS, path traversal, command injection)
- Request size limits and header validation

### Data Security

- Field-level AES-256-GCM encryption (API keys, OAuth tokens)
- Envelope encryption with key rotation support
- Audit logging (append-only, 2-year retention)
- PII redaction in logs

---

## External Integrations

| Integration | Purpose | Config Key |
|------------|---------|------------|
| DataForSEO | SERP data, keywords, backlinks, on-page audit | `DATAFORSEO_LOGIN` / `DATAFORSEO_PASSWORD` |
| Google Search Console | Search analytics, index status | OAuth connection |
| Google Analytics 4 | Organic traffic analysis | OAuth connection |
| Gmail API | Outreach email sending, reply tracking | OAuth connection |
| Exa AI | Web search for broken links, guest posts | `EXA_API_KEY` |
| Tavily | Research for content, journalist discovery | `TAVILY_API_KEY` |
| PageSpeed Insights | Core Web Vitals, performance scores | `PAGESPEED_API_KEY` |
| Bing Webmaster | Search analytics, index status | `BING_API_KEY` |

---

## Verification

```bash
# Code quality
uv run ruff format --check .
uv run ruff check .
uv run mypy packages/proactive_core/proactive_core

# Tests (31 total: unit, integration, contract)
uv run pytest --cov=proactive_core --cov-fail-under=70

# Contracts
uv run python scripts/verify_contracts.py

# Security audit
uvx pip-audit --local
pnpm audit --prod --audit-level moderate

# Frontend
pnpm lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web test
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e

# Infrastructure
docker compose --profile full config --quiet
helm lint infrastructure/kubernetes/chart
terraform -chdir=infrastructure/terraform fmt -check
terraform -chdir=infrastructure/terraform validate
```

---

## Deployment

### Local (Development)

```bash
docker compose --profile full up --build
```

### Production (Kubernetes)

See `infrastructure/kubernetes/chart/` for Helm chart configuration and `infrastructure/terraform/` for AWS + Cloudflare provisioning.

Detailed deployment instructions are available in `docs/09-implementation.md`.

---

## License

Proprietary. All rights reserved.

---

*Built for [@mentari92](https://github.com/mentari92) — enterprise SEO automation orchestrated by 8 Codex AI agents with multi-engine SERP tracking, GEO/AEO optimization, and full-lifecycle outreach campaign management.*
