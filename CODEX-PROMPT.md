# CODEX PROMPT: Build ProActive SEO

## Copy prompt di bawah ini ke Codex (GPT-5.6)

---

```
You are building ProActive SEO — an enterprise-grade SEO automation platform that automates 87% of SEO tasks using agentic AI.

## CONTEXT

Read these blueprint documents FIRST before writing any code:

1. docs/00-master-prd.md — Master PRD (entry point, read this first)
2. docs/01-architecture.md — System architecture (microservices, K8s, CI/CD)
3. docs/02-database.md — PostgreSQL schema (37 tables, full DDL)
4. docs/03-api-specification.md — REST API (97 endpoints)
5. docs/04-agent-system.md — 8 AI agents + execution layer
6. docs/05-security.md — Enterprise security (OAuth, MFA, RBAC, encryption)
7. docs/06-integrations.md — 13 API integrations (Gmail, DataForSEO, GSC, etc.)
8. docs/07-frontend.md — 50+ pages, design system, components
9. docs/08-monitoring.md — Prometheus, Grafana, alerting

## TECH STACK

Backend:
- Python 3.12 + FastAPI (async)
- PostgreSQL 16 (primary + read replicas)
- Redis 7 (cache + queue)
- Celery (task queue)
- SQLAlchemy 2.0 + Alembic (ORM + migrations)

Frontend:
- Next.js 14 (App Router)
- Tailwind CSS + shadcn/ui
- Zustand (state management)
- React Query (data fetching)
- Recharts (charts)
- SSE for real-time updates

Infrastructure:
- Docker + Docker Compose (development)
- Kubernetes (production)
- GitHub Actions + ArgoCD (CI/CD)
- Cloudflare (CDN + WAF)

External APIs:
- OpenAI GPT-4o + Codex (LLM)
- Gmail API (outreach execution)
- DataForSEO (SERP + backlink + keyword)
- Google Search Console API
- Google Analytics 4 API
- Bing Webmaster API
- Exa AI (web search)
- Tavily (research)
- PageSpeed Insights API

## KEY FEATURES

8 AI Agents:
1. Crawl Agent — Multi-engine crawling, broken link detection, index monitoring
2. Content Agent — On-page audit, dual scoring (Google + AI Readiness), AEO/GEO
3. Technical Agent — CWV, schema generation, self-healing (8 issue types)
4. Rank Agent — Multi-engine SERP tracking via DataForSEO
5. Backlink & Outreach Agent — HARO, broken link building, guest post, unlinked mention
6. Competitor Agent — Content monitoring, keyword stealing, backlink analysis
7. Decision Engine — Priority scoring, resource allocation, proactive triggers
8. Action Executor — Auto-fix, email sending, content publishing

Execution Layer:
- Gmail API — Send outreach emails, track replies, follow-up automation
- DataForSEO — SERP tracking, keyword data, backlink data, on-page audit
- Exa AI — Web search for broken links, guest posts, unlinked mentions
- Tavily — Research for content, journalist discovery
- GSC/Bing/Yandex/Naver — Search analytics, index status

Campaign Tracker:
- 4 campaign types: HARO, Broken Link, Guest Post, Unlinked Mention
- 6 status states: Draft → Sent → Replied → Negotiating → Live → Rejected
- Email sending via Gmail API
- Follow-up automation (3-day, 5-day, 7-day sequences)
- Link verification (check if backlink is live)

## BUILD ORDER

Phase 1: Foundation (Week 1)
1. Project structure (monorepo)
2. Docker Compose setup
3. PostgreSQL + Redis setup
4. Database migrations (Alembic)
5. FastAPI app skeleton
6. Authentication (OAuth 2.0 + JWT)
7. Basic CRUD (organizations, users, projects)

Phase 2: Core Agents (Week 2)
8. Celery worker setup
9. Crawler Agent (basic crawl + broken link detection)
10. Technical Agent (basic audit + schema generation)
11. Agent orchestration framework
12. Event bus (Redis pub/sub)

Phase 3: Content & Rank (Week 3)
13. Content Agent (audit + dual scoring)
14. Rank Agent (DataForSEO SERP tracking)
15. DataForSEO integration (SERP + Keywords + Backlinks)
16. GSC integration

Phase 4: Outreach (Week 4)
17. Backlink & Outreach Agent
18. HARO Response Generator
19. Broken Link Building
20. Guest Post Outreach
21. Gmail API integration (send + track)
22. Campaign Tracker

Phase 5: Frontend (Week 5-6)
23. Next.js project setup
24. Design system (shadcn/ui + Tailwind tokens)
25. Auth pages (login, register, forgot password)
26. Dashboard (overview, activity, notifications)
27. SEO Command Center (keywords, pages, issues)
28. Agent Control Center (status, logs, config)
29. Campaign Tracker UI (table + Kanban)
30. Content Hub (briefs, drafts, editor)
31. Settings (profile, org, integrations)

Phase 6: Integrations (Week 7)
32. GA4 integration
33. Bing Webmaster integration
34. Exa AI integration
35. Tavily integration
36. PageSpeed Insights integration

Phase 7: Polish (Week 8)
37. Monitoring (Prometheus + Grafana)
38. Logging (structured JSON + Loki)
39. Alerting (critical, warning, info)
40. Security hardening (WAF, rate limiting, audit logs)
41. Performance optimization
42. Documentation

## CODING STANDARDS

- Type hints on all Python functions
- Docstrings on all classes and public methods
- Pydantic models for all request/response schemas
- Error handling with proper HTTP status codes
- Logging with structured JSON format
- Tests for all agent logic (pytest)
- No emoji in code or comments
- Use DataForSEO instead of SerpAPI or Ahrefs

## IMPORTANT NOTES

- Read docs/00-master-prd.md FIRST for full context
- Follow the database schema in docs/02-database.md exactly
- Follow the API spec in docs/03-api-specification.md exactly
- Follow the agent workflows in docs/04-agent-system.md exactly
- Use claude-design principles for frontend (see docs/07-frontend.md)
- All outreach emails sent via Gmail API (see docs/06-integrations.md)
- DataForSEO replaces SerpAPI + Ahrefs (see docs/06-integrations.md)

Start building. Read the docs first, then begin with Phase 1.
```

---

## Cara Pakai

1. Buka Codex (OpenAI)
2. Paste prompt di atas
3. Codex akan baca semua 9 document di `docs/`
4. Codex akan mulai build dari Phase 1
5. Kamu review setiap phase

## Tips

- Kalau Codex stuck, kasih hint: "Baca docs/04-agent-system.md untuk workflow agent X"
- Kalau mau fokus ke satu fitur: "Skip ke Phase 4, build HARO Response Generator"
- Kalau ada error: "Fix error di backend/app/agents/crawler.py, refer ke docs/04-agent-system.md"
