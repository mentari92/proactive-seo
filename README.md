# ProActive SEO

Enterprise-grade SEO automation platform — **87% task automation** with agentic AI. This repository
contains the executable platform and the source blueprints from which its contracts are generated.

## Quick start

Prerequisites: Python 3.12, uv, Node.js 20, pnpm 9, Docker, and Docker Compose.

```bash
cp .env.example .env
uv sync --extra dev
pnpm install
docker compose --profile core up --build
```

The local dashboard is served at `http://localhost:3000`, the aggregate API at
`http://localhost:8000`, and development OpenAPI documentation at `http://localhost:8000/docs`.
Provider credentials are optional: development and CI use deterministic fakes and live actions are
disabled by default.

## Documentation

Complete blueprint in [`docs/`](docs/):

| # | Document | Content |
|---|----------|---------|
| 0 | [Master PRD](docs/00-master-prd.md) | Entry point, 18 sections |
| 1 | [Architecture](docs/01-architecture.md) | 15 microservices, K8s, CI/CD |
| 2 | [Database](docs/02-database.md) | 37 PostgreSQL tables, RLS |
| 3 | [API Specification](docs/03-api-specification.md) | 97 REST endpoints |
| 4 | [Agent System](docs/04-agent-system.md) | 8 agents + execution layer |
| 5 | [Security](docs/05-security.md) | Auth, encryption, GDPR, SOC2 |
| 6 | [Integrations](docs/06-integrations.md) | 13 API integrations |
| 7 | [Frontend](docs/07-frontend.md) | 50+ pages, design system |
| 8 | [Monitoring](docs/08-monitoring.md) | Prometheus, Grafana, alerting |

## Project structure

```
proactive-seo/
├── apps/web/                # Next.js 15.5 product application
├── packages/proactive_core/ # Shared API, auth, DB, agents, events, providers
├── services/                # 14 independently deployable FastAPI services
├── contracts/               # Canonical API, table, enum, agent, and provider manifests
├── alembic/                 # PostgreSQL migrations and corrected tenant RLS
├── infrastructure/          # Helm/Kubernetes, ArgoCD, and AWS/Cloudflare Terraform
├── observability/           # Prometheus, Grafana, Loki, Tempo, OTel, Alertmanager
├── tests/                   # Unit, contract, integration, security, and agent tests
└── docs/                    # Product blueprints, implementation guide, and runbooks
```

## Key Features

- 87% SEO task automation via 8 AI agents
- Execution layer: Gmail, Exa AI, Tavily, DataForSEO
- Multi-engine: Google, Bing, Yandex, Naver
- AEO/GEO optimization
- Link building automation (HARO, broken link, guest post)
- Enterprise security (OAuth, MFA, RBAC, encryption)
- 50+ frontend pages

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 App Router + Tailwind + shadcn/ui |
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 + Redis |
| Queue | Celery + Redis |
| LLM | OpenAI Responses API with GPT-5.6 role routing + GPT-5.3-Codex |
| Infra | Docker Compose + AWS EKS/RDS/ElastiCache/S3 + Cloudflare |
| Monitoring | Prometheus + Grafana + Loki + Tempo/OpenTelemetry |

## Verification

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy packages/proactive_core/proactive_core
uv run pytest --cov=proactive_core --cov-fail-under=70
uv run python scripts/verify_contracts.py
uvx pip-audit --local
pnpm audit --prod --audit-level moderate
pnpm lint
pnpm --dir apps/web typecheck
pnpm --dir apps/web test
pnpm --dir apps/web build
pnpm --dir apps/web test:e2e
docker compose --profile full config --quiet
helm lint infrastructure/kubernetes/chart
terraform -chdir=infrastructure/terraform fmt -check
terraform -chdir=infrastructure/terraform validate
```

See [Implementation Guide](docs/09-implementation.md), [Security Policy](SECURITY.md), and the
[operations runbook](docs/runbooks/operations.md) before enabling credentials or live actions. The
[acceptance ledger](docs/10-acceptance.md) maps every build phase to its executable evidence and
separates local checks from credential- or environment-gated release checks.
