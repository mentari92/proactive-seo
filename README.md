# ProActive SEO

Enterprise-grade SEO automation platform — **87% task automation** with agentic AI.

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

## Project Structure (planned)

```
proactive-seo/
├── docs/                    ← Blueprint documentation
├── frontend/                ← Next.js 14 + Tailwind
├── backend/                 ← FastAPI microservices
├── agents/                  ← 8 AI agents
├── integrations/            ← External API connectors
├── infrastructure/          ← Docker, K8s, CI/CD
└── README.md
```

## Key Features

- 87% SEO task automation via 8 AI agents
- Execution layer: Gmail, Exa AI, Tavily, SerpAPI
- Multi-engine: Google, Bing, Yandex, Naver
- AEO/GEO optimization
- Link building automation (HARO, broken link, guest post)
- Enterprise security (OAuth, MFA, RBAC, encryption)
- 50+ frontend pages

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14 + Tailwind + shadcn/ui |
| Backend | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 + Redis |
| Queue | Celery + Redis |
| LLM | OpenAI GPT-4o + Codex |
| Infra | Docker + Kubernetes |
| Monitoring | Prometheus + Grafana |
