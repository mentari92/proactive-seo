# ProActive SEO — System Architecture

> Enterprise-Grade SEO Automation Platform  
> Version: 1.0.0 | Last Updated: 2026-07-19  
> SLA Target: 99.9% uptime | Scale: 10,000+ users, 1M+ pages, 100M+ keywords  
> Automation Target: 87% of routine SEO tasks handled without human intervention

---

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Microservices Architecture](#2-microservices-architecture)
3. [Technology Stack](#3-technology-stack)
4. [Infrastructure](#4-infrastructure)
5. [Scaling Strategy](#5-scaling-strategy)
6. [Disaster Recovery](#6-disaster-recovery)
7. [CI/CD Pipeline](#7-cicd-pipeline)
8. [Environment Configuration](#8-environment-configuration)
9. [Network Topology](#9-network-topology)
10. [Data Flow Diagrams](#10-data-flow-diagrams)
11. [Security Architecture](#11-security-architecture)
12. [Cache Invalidation Strategy](#12-cache-invalidation-strategy)
13. [Database Replication & Sharding](#13-database-replication--sharding)

---

## 1. High-Level Architecture

### 1.1 ASCII Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS & CONSUMERS                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────────────┐ │
│  │ Browser  │  │ Mobile   │  │ API      │  │ Webhooks │  │ Third-Party Integrations│ │
│  │ (SPA)    │  │ Apps     │  │ Clients  │  │ Inbound  │  │(GSC, GA4, DataForSEO)│ │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬────────────────┘ │
└───────┼──────────────┼──────────────┼──────────────┼───────────────┼─────────────────┘
        │              │              │              │               │
        ▼              ▼              ▼              ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           CLOUDFLARE CDN / WAF / DNS                                 │
│   ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  ┌────────────────────────┐ │
│   │ Edge Cache   │  │ DDoS Protect │  │ Rate Limiting │  │ SSL Termination (TLS)  │ │
│   └─────────────┘  └──────────────┘  └───────────────┘  └────────────────────────┘ │
└────────────────────────────────────┬────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                          KUBERNETES CLUSTER (Primary AZ)                             │
│                                                                                     │
│  ┌────────────────────────────────────────────────────────────────────────────────┐ │
│  │                        NGINX INGRESS CONTROLLER                                │ │
│  │                  (TLS termination, path routing, rate limits)                  │ │
│  └────────────────────────────────────┬───────────────────────────────────────────┘ │
│                                       │                                              │
│  ┌────────────────────────────────────▼───────────────────────────────────────────┐ │
│  │                     API GATEWAY (Kong / Traefik)                                │ │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐ │ │
│  │  │ Auth/JWT   │ │ Rate       │ │ Request    │ │ Logging    │ │ Circuit      │ │ │
│  │  │ Validation │ │ Limiting   │ │ Transform  │ │ & Tracing  │ │ Breaker      │ │ │
│  │  └────────────┘ └────────────┘ └────────────┘ └────────────┘ └──────────────┘ │ │
│  └────────────┬──────────┬──────────┬──────────┬──────────┬──────────┬────────────┘ │
│               │          │          │          │          │          │               │
│  ┌────────────▼──┐ ┌─────▼──────┐ ┌─▼────────┐ ┌────────▼┐ ┌──────▼───────┐       │
│  │  Frontend     │ │ Auth       │ │ Tenant   │ │ Keyword │ │ Content      │       │
│  │  SSR (Next.js)│ │ Service    │ │ Service  │ │ Service │ │ Service      │       │
│  │  Pods x3      │ │ (Keycloak) │ │ Pods x3  │ │ Pods x5 │ │ Pods x5      │       │
│  └───────────────┘ └────────────┘ └──────────┘ └─────────┘ └──────────────┘       │
│                                                                                     │
│  ┌───────────────┐ ┌────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐       │
│  │  Audit/       │ │ Crawl      │ │ Rank     │ │ SERP    │ │ Analytics    │       │
│  │  Compliance   │ │ Service    │ │ Tracker  │ │ Monitor │ │ Service      │       │
│  │  Pods x2      │ │ Pods x5    │ │ Pods x5  │ │ Pods x5 │ │ Pods x3      │       │
│  └───────────────┘ └────────────┘ └──────────┘ └─────────┘ └──────────────┘       │
│                                                                                     │
│  ┌───────────────┐ ┌────────────┐ ┌──────────┐ ┌─────────┐ ┌──────────────┐       │
│  │ Notification  │ │ Billing    │ │ Report   │ │ AI/ML   │ │ Link         │       │
│  │ Service       │ │ Service    │ │ Service  │ │ Service │ │ Analysis     │       │
│  │ Pods x2       │ │ Pods x2    │ │ Pods x3  │ │ Pods x5 │ │ Pods x3      │       │
│  └───────────────┘ └────────────┘ └──────────┘ └─────────┘ └──────────────┘       │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                    CELERY WORKER POOLS                                       │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────────────┐  │   │
│  │  │ Crawl Workers│ │ Keyword      │ │ Content Gen  │ │ Report Generator   │  │   │
│  │  │ x10 (CPU)    │ │ Workers x8   │ │ Workers x5   │ │ Workers x3         │  │   │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────────────┘  │   │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────────────────┐  │   │
│  │  │ SERP Workers │ │ Notification │ │ Scheduled Tasks (Celery Beat) x2     │  │   │
│  │  │ x8           │ │ Workers x3   │ │ (rank checks, crawl schedules,      │  │   │
│  │  └──────────────┘ └──────────────┘ │  report generation, alerts)         │  │   │
│  │                                     └──────────────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────────┘
        │                │                │                │                │
        ▼                ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                            DATA & MESSAGE LAYER                                      │
│                                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────────┐  │
│  │  PostgreSQL 16   │  │  Redis Cluster   │  │  RabbitMQ Cluster               │  │
│  │  ┌────────────┐  │  │  (7 nodes)       │  │  (3 nodes, mirrored queues)     │  │
│  │  │ Primary    │  │  │                  │  │  ┌──────────┐ ┌──────────────┐   │  │
│  │  │ (Writer)   │──┼──│  ┌───────────┐  │  │  │ Queues:  │ │ Exchanges:   │   │  │
│  │  └─────┬──────┘  │  │  │ Cache     │  │  │  │ crawl.*  │ │ seo.direct   │   │  │
│  │        │         │  │  │ (64GB)    │  │  │  │ keyword.*│ │ seo.topic    │   │  │
│  │  ┌─────▼──────┐  │  │  ├───────────┤  │  │  │ content.*│ │ seo.fanout   │   │  │
│  │  │ Read       │  │  │  │ Sessions  │  │  │  │ report.* │ │              │   │  │
│  │  │ Replica 1  │  │  │  │ (32GB)   │  │  │  │ notify.* │ │              │   │  │
│  │  ├────────────┤  │  │  ├───────────┤  │  │  └──────────┘ └──────────────┘   │  │
│  │  │ Read       │  │  │  │ Queue     │  │  │                                  │  │
│  │  │ Replica 2  │  │  │  │ Broker    │  │  │                                  │  │
│  │  ├────────────┤  │  │  │ (32GB)   │  │  │                                  │  │
│  │  │ Read       │  │  │  └───────────┘  │  │                                  │  │
│  │  │ Replica 3  │  │  │                  │  │                                  │  │
│  │  └────────────┘  │  │                  │  │                                  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────────────┘  │
│                                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────────────┐  │
│  │  Elasticsearch   │  │  S3 / MinIO      │  │  ClickHouse (Analytics OLAP)    │  │
│  │  Cluster (5 nodes│  │  Object Storage  │  │  (3-node cluster)               │  │
│  │  - logs, search) │  │  (crawl caches,  │  │  (100M+ keyword analytics,      │  │
│  │                  │  │   screenshots,   │  │   SERP history, performance     │  │
│  │                  │  │   exports, AI)   │  │   metrics aggregation)          │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                      OBSERVABILITY & MONITORING                                      │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  Prometheus    │  │  Grafana       │  │  Loki          │  │  Jaeger          │  │
│  │  (metrics)     │  │  (dashboards)  │  │  (logs)        │  │  (distributed    │  │
│  │                │  │                │  │                │  │   tracing)       │  │
│  └────────────────┘  └────────────────┘  └────────────────┘  └──────────────────┘  │
│  ┌────────────────┐  ┌──────────────────────────────────────────────────────────┐  │
│  │  PagerDuty     │  │  AlertManager (Prometheus → Slack/Email/PagerDuty)       │  │
│  │  (on-call)     │  │                                                          │  │
│  └────────────────┘  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Architecture Principles

| Principle | Implementation |
|-----------|---------------|
| **Multi-tenancy** | Shared infrastructure, schema-level tenant isolation via `tenant_id` on every table. Row-level security in PostgreSQL. |
| **Zero-downtime deploys** | Blue-green deployments via ArgoCD with rolling updates. Canary releases for high-risk changes. |
| **Event-driven** | Async processing via RabbitMQ. Domain events for cross-service communication. |
| **CQRS** | Write path → PostgreSQL. Read path → PostgreSQL read replicas + Elasticsearch + ClickHouse for analytics. |
| **12-Factor App** | Config via environment variables. Stateless services. Logs to stdout/stderr. |
| **Defense in depth** | WAF → Rate limiting → JWT validation → RBAC → Input validation → SQL parameterization → Audit logging. |

---

## 2. Microservices Architecture

### 2.1 Service Catalog

#### 2.1.1 Auth Service (`auth-service`)

```yaml
Purpose: Identity & access management for multi-tenant SaaS
Stack: Keycloak 24 + custom FastAPI wrapper
Port: 8001
Instances: 3 (HA)
Database: PostgreSQL (shared cluster, dedicated schema)

Capabilities:
  - OAuth 2.0 / OpenID Connect (authorization code + PKCE)
  - SAML 2.0 SSO for enterprise customers
  - Multi-factor authentication (TOTP, WebAuthn)
  - Tenant provisioning & user invitation flows
  - Role-Based Access Control (RBAC) with custom roles
  - API key management for programmatic access
  - Session management with Redis-backed tokens
  - Rate limiting per API key / user

Endpoints:
  POST   /auth/login              # Email/password + MFA
  POST   /auth/refresh            # Token refresh
  POST   /auth/logout             # Session invalidation
  GET    /auth/me                 # Current user profile
  POST   /auth/invite             # Invite user to tenant
  GET    /auth/tenants            # List user's tenants
  POST   /auth/switch-tenant      # Switch active tenant
  POST   /auth/api-keys           # Generate API key
  DELETE /auth/api-keys/{id}      # Revoke API key

Data Model:
  users: id, email, name, password_hash, mfa_enabled, mfa_secret, created_at
  tenants: id, name, plan, stripe_customer_id, settings_json, created_at
  user_tenants: user_id, tenant_id, role, invited_by, joined_at
  api_keys: id, user_id, tenant_id, key_hash, scopes, expires_at, last_used_at
  sessions: id, user_id, tenant_id, token_hash, ip, user_agent, expires_at
```

#### 2.1.2 Tenant Service (`tenant-service`)

```yaml
Purpose: Tenant lifecycle management, billing integration, resource quotas
Stack: FastAPI + Stripe SDK + PostgreSQL
Port: 8002
Instances: 3

Capabilities:
  - Tenant CRUD with plan-based feature flags
  - Stripe subscription management (create, upgrade, downgrade, cancel)
  - Usage metering (keywords tracked, pages crawled, API calls)
  - Resource quota enforcement (max keywords, max sites, max users)
  - Tenant settings & configuration management
  - Webhook handling for Stripe events
  - Custom domain provisioning (CNAME verification)

Endpoints:
  POST   /tenants                        # Create tenant (signup)
  GET    /tenants/{id}                   # Get tenant details
  PATCH  /tenants/{id}                   # Update tenant settings
  POST   /tenants/{id}/upgrade           # Upgrade plan
  GET    /tenants/{id}/usage             # Current usage metrics
  GET    /tenants/{id}/quota             # Resource quotas remaining
  POST   /tenants/{id}/domains           # Add custom domain
  DELETE /tenants/{id}/domains/{domain}  # Remove custom domain

Plans (quotas):
  Starter:     500 keywords,    10 sites,   50K pages,    5 users
  Professional: 5K keywords,    50 sites,   500K pages,   25 users
  Enterprise:  100K keywords,   500 sites,  5M pages,     unlimited users
  Custom:      negotiated
```

#### 2.1.3 Keyword Service (`keyword-service`)

```yaml
Purpose: Keyword research, tracking, grouping, and SERP position monitoring
Stack: FastAPI + PostgreSQL + ClickHouse + Redis
Port: 8003
Instances: 5 (high throughput)
Workers: 8 Celery workers (SERP fetching)

Capabilities:
  - Keyword research via seed expansion (Google Suggest, People Also Ask,
    Related Searches, competitor keyword gaps)
  - Keyword grouping & clustering (semantic similarity via embeddings)
  - Daily/weekly SERP position tracking (100M+ keywords)
  - SERP feature tracking (featured snippets, PAA, local pack, knowledge panel)
  - Competitor rank comparison
  - Keyword difficulty scoring (backlink profile analysis)
  - Search volume estimation (machine learning model)
  - Keyword tagging, notes, and custom attributes
  - Bulk import/export (CSV, XLSX, API)

Endpoints:
  POST   /keywords/research              # Keyword research (seed → expansion)
  POST   /keywords/track                 # Add keywords to tracking
  GET    /keywords/{id}                  # Keyword details
  GET    /keywords/{id}/history          # SERP position history
  POST   /keywords/bulk-import           # Bulk CSV import
  GET    /keywords/groups                # Keyword groups
  POST   /keywords/groups                # Create keyword group
  GET    /keywords/serp/{id}             # Full SERP snapshot
  GET    /keywords/competitors/{id}      # Competitor rankings
  POST   /keywords/clusters              # Auto-cluster keywords

Data Model (PostgreSQL):
  keywords: id, tenant_id, keyword, language, country, device, search_volume,
            difficulty, cpc, tags_json, group_id, created_at
  keyword_positions: id, keyword_id, date, position, url, serp_features_json,
                     previous_position, change
  keyword_groups: id, tenant_id, name, description, auto_rules_json

Data Model (ClickHouse — hot analytics):
  serp_snapshots: keyword_id, date, position_1..100 (JSON), features, fetched_at
  keyword_daily_metrics: tenant_id, keyword_id, date, impressions, clicks, ctr, avg_position
  -- Partitioned by month, TTL 2 years, aggregated materialized views for dashboards

Celery Tasks:
  fetch_serp_positions    # Runs on schedule per tenant (daily/weekly)
  expand_keywords         # Research expansion from seed
  cluster_keywords        # K-means clustering on embeddings
  calculate_difficulty    # Backlink analysis per keyword
```

#### 2.1.4 Crawl Service (`crawl-service`)

```yaml
Purpose: Website crawling, technical SEO audit, page analysis
Stack: FastAPI + Celery + Playwright (headless Chrome) + BeautifulSoup + PostgreSQL + S3
Port: 8004
Instances: 5 (API), 10 workers (CPU-heavy crawling)
Workers: 10 Celery workers

Capabilities:
  - Full website crawling (configurable depth, speed, JavaScript rendering)
  - Technical SEO audit (broken links, redirects, duplicate content, missing meta)
  - Page speed analysis (Core Web Vitals via Lighthouse)
  - Mobile-friendliness checking
  - Structured data validation (Schema.org, JSON-LD, Microdata)
  - XML Sitemap generation and validation
  - Robots.txt analysis and recommendations
  - Canonical URL verification
  - Hreflang tag validation (international SEO)
  - Internal link graph analysis
  - Crawl budget optimization
  - Screenshot capture for visual diff

Endpoints:
  POST   /crawls                         # Start new crawl
  GET    /crawls/{id}                    # Crawl status & summary
  GET    /crawls/{id}/issues             # Technical issues found
  GET    /crawls/{id}/pages              # Crawled pages
  GET    /crawls/{id}/pages/{page_id}    # Page detail
  GET    /crawls/{id}/link-graph         # Internal link structure
  POST   /crawls/{id}/re-crawl           # Re-crawl specific URLs
  GET    /crawls/{id}/export             # Export crawl data (CSV/PDF)
  GET    /crawls/{id}/diff/{page_id}     # Visual diff from previous crawl

Data Model:
  crawls: id, tenant_id, site_id, status, config_json, pages_found,
          pages_crawled, issues_count, started_at, finished_at
  crawled_pages: id, crawl_id, url, status_code, title, meta_description,
                 h1, canonical, content_hash, load_time_ms, screenshot_s3_key,
                 structured_data_json, issues_json
  internal_links: id, crawl_id, source_url, target_url, anchor_text, follow

Crawl Engine Pipeline:
  1. URL frontier (priority queue) → deduplication via URL fingerprint
  2. HTTP fetch (requests) or JS render (Playwright, configurable)
  3. Parse → extract links, meta tags, structured data, content
  4. Analyze → run 50+ SEO checks in parallel
  5. Store → page data to PostgreSQL, screenshots to S3
  6. Report → emit domain events for notification service
```

#### 2.1.5 Content Service (`content-service`)

```yaml
Purpose: AI-powered content optimization, generation, and recommendations
Stack: FastAPI + OpenAI API / Anthropic Claude + PostgreSQL + Redis + S3
Port: 8005
Instances: 5 (API), 5 workers (AI generation)

Capabilities:
  - Content brief generation (target keywords, questions, outline, word count)
  - AI-powered content writing (GPT-4o / Claude with SEO guidelines)
  - Content optimization scoring (readability, keyword density, NLP entity coverage)
  - Meta title & description generation (A/B variants)
  - Content gap analysis (vs. top-ranking competitors)
  - Semantic content analysis (entity extraction, topic coverage)
  - Internal link suggestions (contextual anchor text)
  - Content calendar planning
  - Content performance tracking (pre/post optimization)
  - Plagiarism detection integration

Endpoints:
  POST   /content/briefs                # Generate content brief
  POST   /content/generate              # AI content generation
  POST   /content/optimize              # Score & optimize existing content
  POST   /content/meta-generate         # Generate title/description variants
  GET    /content/gaps/{keyword_id}     # Content gap analysis
  POST   /content/link-suggestions      # Internal link recommendations
  GET    /content/calendar              # Content calendar
  POST   /content/bulk-optimize         # Bulk optimization

AI Pipeline:
  1. Collect SERP top-10 content for target keyword
  2. Extract entities, topics, questions (NLP analysis)
  3. Generate content brief with recommended structure
  4. AI generation with SEO-aware prompting
  5. Post-processing: readability check, keyword integration, link insertion
  6. Score against optimization rubric (0-100)
  7. Store in S3, index in Elasticsearch
```

#### 2.1.6 Rank Tracker Service (`rank-tracker-service`)

```yaml
Purpose: SERP monitoring at scale — position tracking, volatility detection, alerts
Stack: FastAPI + Celery + ClickHouse + PostgreSQL + Redis
Port: 8006
Instances: 5 (API), 8 workers (SERP fetching)

Capabilities:
  - Daily SERP position tracking across Google, Bing, YouTube
  - Multi-device tracking (desktop, mobile, tablet)
  - Multi-location tracking (country, state, city, ZIP code level)
  - SERP volatility index (Google algorithm update detection)
  - Competitor position tracking & comparison
  - Featured snippet & SERP feature tracking
  - Local pack / Google Maps ranking
  - Historical ranking data (unlimited retention on Enterprise plan)
  - Ranking alerts (email, Slack, webhook on significant changes)
  - Share of Voice calculation

Data Pipeline:
  1. Celery Beat schedules rank checks per tenant (configurable: daily/weekly)
  2. Workers fetch SERP via scraping infrastructure (rotating proxies)
  3. Parse SERP: extract positions, features, related searches
  4. Store raw SERP in ClickHouse (append-only, TTL 3 years)
  5. Calculate deltas: position change, SERP feature changes
  6. Trigger alerts if threshold crossed (e.g., dropped 5+ positions)
  7. Update materialized views for dashboard aggregation

ClickHouse Schema:
  CREATE TABLE serp_positions (
    tenant_id UInt32,
    keyword_id UInt64,
    search_engine Enum('google','bing','youtube'),
    device Enum('desktop','mobile','tablet'),
    country String,
    region String,
    city String,
    position UInt8,
    url String,
    serp_features Array(String),
    previous_position UInt8,
    volatity_score Float32,
    fetched_at DateTime
  ) ENGINE = MergeTree()
  PARTITION BY toYYYYMM(fetched_at)
  ORDER BY (tenant_id, keyword_id, fetched_at)
  TTL fetched_at + INTERVAL 3 YEAR;
```

#### 2.1.7 SERP Monitor Service (`serp-monitor-service`)

```yaml
Purpose: Real-time SERP landscape monitoring, algorithm update detection
Stack: FastAPI + ClickHouse + Redis + WebSocket
Port: 8007
Instances: 5

Capabilities:
  - SERP volatility tracking (aggregate position changes across all tracked keywords)
  - Google algorithm update detection & correlation
  - SERP feature change monitoring (new featured snippets, PAA changes)
  - Competitor SERP movement alerts
  - SERP snapshot comparison (before/after updates)
  - Real-time WebSocket dashboard for live SERP monitoring
  - Historical SERP volatility charts
```

#### 2.1.8 Analytics Service (`analytics-service`)

```yaml
Purpose: Unified SEO analytics, performance dashboards, cross-channel attribution
Stack: FastAPI + ClickHouse + PostgreSQL + Redis
Port: 8008
Instances: 3 (API), 3 workers (data ingestion)

Capabilities:
  - Google Search Console integration (impressions, clicks, CTR, position)
  - Google Analytics 4 integration (traffic, conversions, user behavior)
  - Cross-channel data correlation (organic + paid + social)
  - Custom dashboard builder (drag-and-drop widgets)
  - Scheduled report generation (PDF, email)
  - Anomaly detection (traffic drops, ranking changes)
  - ROI calculation (organic traffic value vs. SEO spend)
  - Attribution modeling (first-touch, last-touch, multi-touch)
  - Custom metrics and dimensions

Integrations:
  Google Search Console API → daily data sync
  Google Analytics 4 API → daily data sync
  DataForSEO Backlinks API → backlink data
  SEMrush API → competitor data (optional)
  Moz API → domain authority (optional)
  Custom: webhook ingestion for any data source
```

#### 2.1.9 Notification Service (`notification-service`)

```yaml
Purpose: Multi-channel notifications — email, Slack, webhook, in-app
Stack: FastAPI + Celery + RabbitMQ + SendGrid/SES + Slack SDK
Port: 8009
Instances: 2 (API), 3 workers

Capabilities:
  - Email notifications (transactional + digest)
  - Slack integration (webhook + bot)
  - Webhook delivery (custom endpoints with retry)
  - In-app notifications (WebSocket push)
  - Notification preferences per user (channel, frequency, severity)
  - Alert rules engine (custom triggers & thresholds)
  - Digest emails (daily/weekly summary of SEO changes)

Alert Rules Examples:
  - "Keyword X dropped more than 5 positions" → Slack + Email
  - "Crawl found critical issues" → Email + In-app
  - "Competitor outranked us for keyword Y" → Slack
  - "Weekly ranking summary" → Email digest
  - "Content optimization score below 60" → In-app
```

#### 2.1.10 Billing Service (`billing-service`)

```yaml
Purpose: Subscription management, invoicing, payment processing
Stack: FastAPI + Stripe SDK + PostgreSQL
Port: 8010
Instances: 2

Capabilities:
  - Stripe Checkout session creation
  - Subscription lifecycle (trial, active, past_due, canceled)
  - Usage-based billing (overage charges for exceeding quotas)
  - Invoice generation & delivery
  - Payment method management
  - Plan comparison & upgrade flows
  - Coupon/promo code support
  - Revenue recognition & MRR tracking

Stripe Webhook Events Handled:
  customer.subscription.created
  customer.subscription.updated
  customer.subscription.deleted
  invoice.paid
  invoice.payment_failed
  payment_method.attached
  payment_method.detached
```

#### 2.1.11 Report Service (`report-service`)

```yaml
Purpose: Automated report generation — white-label PDF, scheduled delivery
Stack: FastAPI + Celery + WeasyPrint/Puppeteer + S3 + PostgreSQL
Port: 8011
Instances: 3 (API), 3 workers (PDF generation)

Capabilities:
  - Template-based report builder
  - White-label reports (custom logo, colors, branding)
  - Scheduled report delivery (daily, weekly, monthly)
  - On-demand report generation
  - Report sections: rankings, traffic, issues, content scores, backlinks
  - Multi-format: PDF, HTML, CSV, XLSX
  - Interactive HTML reports (embeddable)
  - Report sharing via unique URL

Report Templates:
  - Monthly SEO Performance Report
  - Technical Audit Report
  - Keyword Ranking Report
  - Content Performance Report
  - Competitor Analysis Report
  - Executive Summary
  - Custom (user-assembled sections)
```

#### 2.1.12 Link Analysis Service (`link-analysis-service`)

```yaml
Purpose: Backlink analysis, link building opportunities, toxic link detection
Stack: FastAPI + PostgreSQL + ClickHouse + Celery
Port: 8012
Instances: 3 (API), 3 workers

Capabilities:
  - Backlink profile analysis (via DataForSEO Backlinks API)
  - New & lost backlink monitoring
  - Toxic link detection & disavow file generation
  - Link building opportunity identification
  - Competitor backlink gap analysis
  - Anchor text distribution analysis
  - Domain authority tracking over time
  - Internal link optimization suggestions
  - Link intersect analysis (sites linking to competitors but not you)
```

#### 2.1.13 AI/ML Service (`ai-service`)

```yaml
Purpose: Machine learning models for SEO predictions, content scoring, NLP
Stack: FastAPI + PyTorch/Transformers + Redis + PostgreSQL + GPU nodes
Port: 8013
Instances: 5 (CPU), 2 (GPU for inference)

Capabilities:
  - Keyword difficulty prediction (regression model)
  - Search volume estimation (time-series model)
  - Content quality scoring (NLP model)
  - SERP feature prediction (classification model)
  - Keyword clustering (sentence-transformers embeddings + HDBSCAN)
  - Entity extraction from content
  - Sentiment analysis for brand mentions
  - Traffic prediction models
  - Auto-tagging & categorization

Model Serving:
  - FastAPI endpoints for real-time inference (<100ms p95)
  - Batch inference via Celery for bulk operations
  - Model versioning with MLflow
  - A/B testing framework for model updates
  - GPU nodes (NVIDIA T4) for heavy inference workloads

Models:
  keyword_difficulty_v3      # XGBoost, features: backlinks, DA, competition
  search_volume_v2           # LSTM, features: historical trends, seasonality
  content_quality_v4         # Fine-tuned BERT, features: readability, NLP coverage
  keyword_clustering_v2      # sentence-transformers/all-MiniLM-L6-v2 + HDBSCAN
  serp_feature_predictor_v1  # Gradient Boosted Trees
```

#### 2.1.14 Audit & Compliance Service (`audit-service`)

```yaml
Purpose: Audit trail, GDPR compliance, data retention, access logging
Stack: FastAPI + PostgreSQL + Elasticsearch
Port: 8014
Instances: 2

Capabilities:
  - Complete audit log of all user actions
  - GDPR data export (right to access)
  - GDPR data deletion (right to erasure)
  - Data retention policy enforcement
  - SOC 2 compliance logging
  - IP access logging & anomaly detection
  - API usage tracking & anomaly alerts
  - Session activity monitoring
```

#### 2.1.15 Frontend Service (`frontend-service`)

```yaml
Purpose: Web application UI — SSR + client-side rendering
Stack: Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui + React Query
Port: 3000
Instances: 3

Capabilities:
  - Server-side rendering for SEO & initial load performance
  - Client-side routing with React Server Components
  - Real-time dashboards (WebSocket for live ranking updates)
  - Drag-and-drop report builder
  - Keyword research UI with auto-suggestions
  - Crawl visualization (site architecture graphs)
  - Content editor with live optimization scoring
  - Settings, team management, billing portal
  - Dark/light mode
  - Responsive design (desktop, tablet, mobile)

Key Pages:
  /dashboard                 # Overview: rankings, traffic, issues
  /keywords                  # Keyword tracking & research
  /keywords/[id]             # Keyword detail with SERP history
  /crawls                    # Site audit list
  /crawls/[id]               # Crawl detail with issues
  /content                   # Content optimization tools
  /reports                   # Report builder & scheduled reports
  /analytics                 # Analytics dashboards
  /settings                  # Tenant settings, integrations
  /settings/team             # Team management
  /settings/billing          # Billing & subscription
  /settings/api-keys         # API key management
```

### 2.2 Service Communication Matrix

```
┌──────────────────┬────────────────────────────────────────────────────────────────┐
│ Service          │ Communicates With                                             │
├──────────────────┼────────────────────────────────────────────────────────────────┤
│ auth-service     │ tenant-service (sync), Redis (sessions)                        │
│ tenant-service   │ billing-service (sync), auth-service (sync), PostgreSQL        │
│ keyword-service  │ rank-tracker (async), ai-service (sync), ClickHouse, Redis     │
│ crawl-service    │ notification (async), s3, PostgreSQL                           │
│ content-service  │ ai-service (sync), keyword-service (sync), s3, Redis          │
│ rank-tracker     │ keyword-service (sync), notification (async), ClickHouse       │
│ serp-monitor     │ rank-tracker (async), notification (async), ClickHouse         │
│ analytics-service│ ClickHouse, PostgreSQL, Redis                                  │
│ notification     │ RabbitMQ (consumer), SendGrid, Slack SDK, WebSocket            │
│ billing-service  │ tenant-service (sync), Stripe API, PostgreSQL                  │
│ report-service   │ analytics (sync), keyword (sync), crawl (sync), s3            │
│ link-analysis    │ ai-service (sync), s3, PostgreSQL                              │
│ ai-service       │ PostgreSQL, Redis (model cache), GPU cluster                   │
│ audit-service    │ Elasticsearch, PostgreSQL                                      │
│ frontend         │ ALL services via API Gateway (BFF pattern)                     │
└──────────────────┴────────────────────────────────────────────────────────────────┘

Communication Patterns:
  Sync: gRPC (internal) / REST (external) via API Gateway
  Async: RabbitMQ (task queues) + Redis Pub/Sub (real-time events)
  WebSocket: Frontend ↔ Gateway → Notification service (live updates)
```

---

## 3. Technology Stack

### 3.1 Full Stack Reference

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LAYER                          │ TECHNOLOGY          │ VERSION │ PURPOSE   │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ Frontend Framework             │ Next.js             │ 14.x    │ SSR/CSR   │
│ UI Component Library           │ shadcn/ui           │ latest  │ Components│
│ CSS Framework                  │ Tailwind CSS        │ 3.x     │ Styling   │
│ State Management               │ React Query (TanStack│ 5.x    │ Server    │
│                                │   Query)            │         │ state     │
│ Charting                       │ Recharts / Nivo      │ latest  │ Dashboards│
│ Graph Visualization            │ D3.js / Cytoscape.js │ latest │ Link graph│
│ Form Handling                  │ React Hook Form     │ 7.x     │ Forms     │
│ Validation                     │ Zod                 │ 3.x     │ Schema    │
│ Testing                        │ Vitest + Playwright │ latest  │ E2E/unit  │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ API Gateway                    │ Kong                │ 3.x     │ Routing   │
│ Ingress Controller             │ NGINX Ingress       │ 1.x     │ K8s entry │
│ Service Mesh (optional)        │ Istio / Linkerd     │ latest  │ mTLS, obs │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ Backend Framework              │ FastAPI             │ 0.110+  │ APIs      │
│ Language                       │ Python              │ 3.12    │ Runtime   │
│ ASGI Server                    │ Uvicorn             │ 0.29+   │ App server│
│ ORM                            │ SQLAlchemy          │ 2.x     │ DB access │
│ DB Migrations                  │ Alembic             │ 1.x     │ Migrations│
│ Validation                     │ Pydantic            │ 2.x     │ Schemas   │
│ HTTP Client                    │ httpx               │ 0.27+   │ Async HTTP│
│ Task Queue                     │ Celery              │ 5.x     │ Async jobs│
│ Message Broker                 │ RabbitMQ            │ 3.x     │ Messaging │
│ Testing                        │ pytest + httpx      │ latest  │ Testing   │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ Primary Database               │ PostgreSQL          │ 16.x    │ OLTP      │
│ Analytics Database             │ ClickHouse          │ 24.x    │ OLAP      │
│ Search & Logs                  │ Elasticsearch       │ 8.x     │ Full-text │
│ Cache                          │ Redis               │ 7.x     │ Caching   │
│ Task Queue Backend             │ Redis               │ 7.x     │ Celery    │
│ Object Storage                 │ S3 / MinIO          │ latest  │ Files     │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ Container Runtime              │ Docker              │ 24+     │ Build     │
│ Container Orchestration        │ Kubernetes          │ 1.29+   │ Deploy    │
│ K8s Distribution               │ EKS / GKE / AKS     │ latest  │ Managed K8s│
│ Service Mesh                   │ Istio               │ 1.x     │ mTLS, obs │
│ Ingress                        │ NGINX Ingress       │ 1.x     │ Traffic   │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ CI                             │ GitHub Actions       │ N/A     │ Build/test│
│ CD                             │ ArgoCD              │ 2.x     │ GitOps    │
│ Artifact Registry              │ GitHub Container Reg │ N/A    │ Images    │
│ IaC                            │ Terraform           │ 1.x     │ Infra     │
│ Secrets Management             │ HashiCorp Vault     │ 1.x     │ Secrets   │
│ DNS                            │ Cloudflare          │ N/A     │ DNS/CDN   │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ Metrics                        │ Prometheus          │ 2.x     │ Metrics   │
│ Dashboards                     │ Grafana             │ 10.x    │ Viz       │
│ Logging                        │ Loki + Promtail     │ 2.x     │ Logs      │
│ Tracing                        │ Jaeger              │ 1.x     │ Traces    │
│ Alerting                       │ Alertmanager        │ 0.27+   │ Alerts    │
│ Error Tracking                 │ Sentry              │ N/A     │ Errors    │
│ On-Call                        │ PagerDuty           │ N/A     │ Incidents │
├────────────────────────────────┼─────────────────────┼─────────┼───────────┤
│ Auth Provider                  │ Keycloak            │ 24.x    │ IAM       │
│ Email                          │ SendGrid / AWS SES  │ N/A     │ Email     │
│ Payments                       │ Stripe              │ N/A     │ Billing   │
│ LLM Providers                  │ OpenAI / Anthropic  │ N/A     │ AI gen    │
│ SERP Data                      │ Internal scrapers   │ N/A     │ SERP      │
│ Proxy Network                  │ Bright Data / Oxylabs│ N/A    │ Proxies   │
└────────────────────────────────┴─────────────────────┴─────────┴───────────┘
```

### 3.2 Python Dependencies (requirements.txt)

```txt
# Core
fastapi==0.110.*
uvicorn[standard]==0.29.*
pydantic==2.*
pydantic-settings==2.*
sqlalchemy[asyncio]==2.*
alembic==1.*
asyncpg==0.29.*
psycopg2-binary==2.9.*

# Task Queue
celery[redis]==5.*
celery-redbeat==2.*
kombu==5.*

# Redis
redis[hiredis]==5.*

# HTTP
httpx==0.27.*
aiohttp==3.9.*

# Search & Analytics
elasticsearch[async]==8.*
clickhouse-driver==0.2.*
clickhouse-connect==0.7.*

# Storage
boto3==1.34.*

# Auth
python-jose[cryptography]==3.*
passlib[bcrypt]==1.7.*
python-multipart==0.0.*

# AI/ML
openai==1.*
anthropic==0.25.*
sentence-transformers==2.*
scikit-learn==1.*
torch==2.*

# Monitoring
prometheus-client==0.20.*
sentry-sdk[fastapi]==1.*
structlog==24.*

# Email
sendgrid==6.*

# Payments
stripe==8.*

# Testing
pytest==8.*
pytest-asyncio==0.23.*
httpx==0.27.*
factory-boy==3.*

# Utilities
python-dateutil==2.*
orjson==3.*
tenacity==8.*
```

---

## 4. Infrastructure

### 4.1 Kubernetes Cluster Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    AWS / GCP / AZURE (Primary Region)                 │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │              KUBERNETES CLUSTER (EKS/GKE)                      │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  Node Pool: general (System + API workloads)             │  │  │
│  │  │  Instance: m6i.2xlarge (8 vCPU, 32GB)                   │  │  │
│  │  │  Nodes: 6-12 (auto-scaling)                              │  │  │
│  │  │  Taints: none                                            │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  Node Pool: workers (CPU-intensive crawl/tasks)          │  │  │
│  │  │  Instance: c6i.4xlarge (16 vCPU, 32GB)                  │  │  │
│  │  │  Nodes: 4-20 (auto-scaling based on queue depth)         │  │  │
│  │  │  Taints: workload=cpu-intensive:NoSchedule               │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  Node Pool: ai-gpu (ML inference)                        │  │  │
│  │  │  Instance: g5.xlarge (4 vCPU, 16GB, 1x T4 GPU)         │  │  │
│  │  │  Nodes: 2-5 (auto-scaling)                               │  │  │
│  │  │  Taints: workload=gpu:NoSchedule                         │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  │                                                                │  │
│  │  ┌──────────────────────────────────────────────────────────┐  │  │
│  │  │  NAMESPACES                                               │  │  │
│  │  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐│  │  │
│  │  │  │ proactive-  │ │ proactive-  │ │ proactive-monitoring││  │  │
│  │  │  │ seo-prod    │ │ seo-staging │ │                     ││  │  │
│  │  │  │             │ │             │ │ Prometheus          ││  │  │
│  │  │  │ All prod    │ │ Staging     │ │ Grafana             ││  │  │
│  │  │  │ services    │ │ services    │ │ Loki                ││  │  │
│  │  │  │             │ │             │ │ Jaeger              ││  │  │
│  │  │  │             │ │             │ │ Alertmanager        ││  │  │
│  │  │  └─────────────┘ └─────────────┘ └─────────────────────┘│  │  │
│  │  │  ┌─────────────┐ ┌─────────────┐                        │  │  │
│  │  │  │ proactive-  │ │ proactive-  │                        │  │  │
│  │  │  │ seo-data    │ │ seo-ci      │                        │  │  │
│  │  │  │             │ │             │                        │  │  │
│  │  │  │ PostgreSQL  │ │ CI runners  │                        │  │  │
│  │  │  │ Redis       │ │ Build tools │                        │  │  │
│  │  │  │ RabbitMQ    │ │             │                        │  │  │
│  │  │  │ ClickHouse  │ │             │                        │  │  │
│  │  │  │ Elasticsearch││             │                        │  │  │
│  │  │  └─────────────┘ └─────────────┘                        │  │  │
│  │  └──────────────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  MANAGED SERVICES (outside K8s)                                │  │
│  │  ┌──────────────────┐  ┌──────────────────┐                   │  │
│  │  │ RDS PostgreSQL   │  │ ElastiCache Redis │                   │  │
│  │  │ Multi-AZ         │  │ Cluster mode      │                   │  │
│  │  │ db.r6g.2xlarge   │  │ cache.r6g.xlarge  │                   │  │
│  │  │ Primary + 3 RR   │  │ 7 nodes           │                   │  │
│  │  └──────────────────┘  └──────────────────┘                   │  │
│  │  ┌──────────────────┐  ┌──────────────────┐                   │  │
│  │  │ Amazon MQ        │  │ Amazon S3         │                   │  │
│  │  │ (RabbitMQ)       │  │ Object storage    │                   │  │
│  │  │ mq.m5.xlarge     │  │ Standard + IA      │                   │  │
│  │  │ 3-node cluster   │  │                    │                   │  │
│  │  └──────────────────┘  └──────────────────┘                   │  │
│  │  ┌──────────────────┐  ┌──────────────────┐                   │  │
│  │  │ Amazon OpenSearch│  │ CloudFront CDN    │                   │  │
│  │  │ (Elasticsearch)  │  │ (optional, backup │                   │  │
│  │  │ r6g.xlarge.search│  │  to Cloudflare)   │                   │  │
│  │  │ 5-node cluster   │  │                    │                   │  │
│  │  └──────────────────┘  └──────────────────┘                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
```

### 4.2 Docker Image Strategy

```dockerfile
# Base image for all Python services
FROM python:3.12-slim AS base
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Multi-stage build for production
FROM base AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM base AS production
COPY --from=builder /install /usr/local
COPY ./app /app
RUN useradd -r -s /bin/false appuser
USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
```

### 4.3 Resource Allocation per Service

```
┌─────────────────────┬──────────┬───────────┬──────────┬──────────────┐
│ Service             │ CPU Req  │ Mem Req   │ CPU Limit│ Mem Limit    │
├─────────────────────┼──────────┼───────────┼──────────┼──────────────┤
│ frontend (Next.js)  │ 500m     │ 512Mi     │ 2000m    │ 2Gi          │
│ auth-service        │ 250m     │ 512Mi     │ 1000m    │ 1Gi          │
│ tenant-service      │ 250m     │ 256Mi     │ 1000m    │ 1Gi          │
│ keyword-service     │ 500m     │ 512Mi     │ 2000m    │ 2Gi          │
│ crawl-service       │ 1000m    │ 1Gi       │ 4000m    │ 4Gi          │
│ content-service     │ 500m     │ 1Gi       │ 2000m    │ 4Gi          │
│ rank-tracker        │ 500m     │ 512Mi     │ 2000m    │ 2Gi          │
│ serp-monitor        │ 500m     │ 512Mi     │ 2000m    │ 2Gi          │
│ analytics-service   │ 500m     │ 1Gi       │ 2000m    │ 4Gi          │
│ notification-svc    │ 250m     │ 256Mi     │ 1000m    │ 1Gi          │
│ billing-service     │ 250m     │ 256Mi     │ 1000m    │ 512Mi        │
│ report-service      │ 1000m    │ 2Gi       │ 4000m    │ 8Gi          │
│ link-analysis       │ 500m     │ 512Mi     │ 2000m    │ 2Gi          │
│ ai-service (CPU)    │ 2000m    │ 4Gi       │ 4000m    │ 8Gi          │
│ ai-service (GPU)    │ 4000m    │ 8Gi       │ 8000m    │ 16Gi (+GPU)  │
│ audit-service       │ 250m     │ 256Mi     │ 1000m    │ 1Gi          │
│ celery-worker-crawl │ 2000m    │ 2Gi       │ 4000m    │ 4Gi          │
│ celery-worker-kw    │ 500m     │ 512Mi     │ 2000m    │ 2Gi          │
│ celery-worker-rpt   │ 1000m    │ 2Gi       │ 4000m    │ 4Gi          │
│ celery-beat         │ 250m     │ 256Mi     │ 500m     │ 512Mi        │
└─────────────────────┴──────────┴───────────┴──────────┴──────────────┘
```

---

## 5. Scaling Strategy

### 5.1 Horizontal Auto-Scaling

```yaml
# Kubernetes HorizontalPodAutoscaler for keyword-service
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: keyword-service-hpa
  namespace: proactive-seo-prod
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: keyword-service
  minReplicas: 5
  maxReplicas: 20
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
    - type: Pods
      pods:
        metric:
          name: http_requests_per_second
        target:
          type: AverageValue
          averageValue: "1000"
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 3
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

### 5.2 Scaling Strategies by Component

```
┌─────────────────────────┬───────────────┬──────────────────────────────────────┐
│ Component               │ Strategy      │ Trigger                              │
├─────────────────────────┼───────────────┼──────────────────────────────────────┤
│ Frontend (Next.js)      │ HPA           │ CPU > 70%, RPS > 1000               │
│ API Services            │ HPA           │ CPU > 70%, RPS > 500/pod             │
│ Crawl Workers           │ KEDA          │ RabbitMQ queue depth > 100           │
│ Keyword Workers         │ KEDA          │ RabbitMQ queue depth > 500           │
│ Content Gen Workers     │ KEDA          │ RabbitMQ queue depth > 50            │
│ Report Workers          │ KEDA          │ RabbitMQ queue depth > 10            │
│ PostgreSQL              │ Vertical + RR │ Connection count > 80%, CPU > 70%    │
│ Redis Cluster           │ Horizontal    │ Memory > 80%, connections > 80%      │
│ Elasticsearch           │ Horizontal    │ Storage > 70%, query latency p99     │
│ ClickHouse              │ Horizontal    │ Storage > 70%, query latency p99     │
│ RabbitMQ                │ Vertical      │ Queue depth > 10K, memory > 80%      │
│ K8s Nodes (general)     │ Cluster Autoscaler│ Pending pods > 0 for 60s          │
│ K8s Nodes (workers)     │ Cluster Autoscaler│ Pending pods > 0 for 30s          │
│ K8s Nodes (GPU)         │ Cluster Autoscaler│ Pending pods > 0 for 120s         │
└─────────────────────────┴───────────────┴──────────────────────────────────────┘
```

### 5.3 KEDA ScaledObject (Queue-Based Workers)

```yaml
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata:
  name: crawl-worker-scaledobject
  namespace: proactive-seo-prod
spec:
  scaleTargetRef:
    name: celery-worker-crawl
  minReplicaCount: 5
  maxReplicaCount: 50
  triggers:
    - type: rabbitmq
      metadata:
        queueName: crawl.tasks
        host: amqp://user:password@rabbitmq.proactive-seo-data:5672
        queueLength: "20"   # Target: 20 tasks per worker
    - type: prometheus
      metadata:
        serverAddress: http://prometheus.proactive-seo-monitoring:9090
        metricName: celery_queue_length
        query: celery_queue_length{queue="crawl.tasks"}
        threshold: "100"
```

### 5.4 Database Scaling Strategy

```
Phase 1 (0-10K users):   Single PostgreSQL primary + 1 read replica
Phase 2 (10K-50K users):  Primary + 3 read replicas, PgBouncer connection pooling
Phase 3 (50K-200K users): Primary + 5 read replicas, tenant sharding by hash(tenant_id)
Phase 4 (200K+ users):    Citus extension for distributed PostgreSQL, table partitioning

Read/Write Splitting:
  Writes → Primary (via PgBouncer)
  Reads  → Read replicas (round-robin via PgBouncer)
  
  SQLAlchemy routing:
    class RoutingSession:
        def get_bind(self, mapper=None, clause=None):
            if self._flushing:
                return primary_engine
            return random.choice(read_replica_engines)

Connection Pooling (PgBouncer):
  pool_mode = transaction
  max_client_conn = 10000
  default_pool_size = 100
  reserve_pool_size = 20
  server_idle_timeout = 300
```

---

## 6. Disaster Recovery

### 6.1 RPO/RTO Targets

```
┌─────────────────────────┬──────────┬──────────┬──────────────────────────────┐
│ Component               │ RPO      │ RTO      │ Strategy                     │
├─────────────────────────┼──────────┼──────────┼──────────────────────────────┤
│ PostgreSQL              │ 5 min    │ 15 min   │ Streaming replication + PITR │
│ Redis Cluster           │ 1 min    │ 5 min    │ AOF + RDB snapshots          │
│ RabbitMQ                │ 0 (msgs) │ 5 min    │ Quorum queues, mirrored      │
│ Elasticsearch           │ 5 min    │ 30 min   │ Snapshot to S3               │
│ ClickHouse              │ 1 hour   │ 30 min   │ Backup to S3                 │
│ S3 Objects              │ 0        │ 0        │ Cross-region replication      │
│ Application State       │ N/A      │ 5 min    │ Stateless, redeploy          │
│ Kubernetes Config       │ 0        │ 10 min   │ GitOps (ArgoCD)              │
│ Secrets                 │ 0        │ 5 min    │ Vault with Raft storage      │
└─────────────────────────┴──────────┴──────────┴──────────────────────────────┘

Overall SLA: 99.9% uptime → max 8.76 hours downtime/year
```

### 6.2 Backup Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        BACKUP ARCHITECTURE                              │
│                                                                         │
│  PostgreSQL                                                             │
│  ├── Continuous: WAL archiving to S3 (every 60s)                       │
│  ├── Full backup: pg_dump daily at 03:00 UTC → S3 (encrypted)          │
│  ├── Incremental: pgBackRest every 6 hours                              │
│  ├── Retention: 30 daily, 12 monthly, 3 yearly                          │
│  └── Cross-region: S3 replication to us-west-2 (from us-east-1)        │
│                                                                         │
│  Redis                                                                  │
│  ├── AOF: every-write fsync                                             │
│  ├── RDB snapshot: every 15 minutes                                     │
│  ├── Backup: RDB to S3 every 6 hours                                   │
│  └── Retention: 7 days                                                  │
│                                                                         │
│  Elasticsearch                                                          │
│  ├── Snapshot to S3: daily                                              │
│  ├── Retention: 30 days                                                 │
│  └── Cross-cluster replication for DR                                   │
│                                                                         │
│  ClickHouse                                                             │
│  ├── Backup to S3: weekly full, daily incremental                       │
│  ├── Retention: 90 days                                                 │
│  └── Replicated tables (3 replicas per shard)                           │
│                                                                         │
│  S3 Objects                                                             │
│  ├── Versioning enabled                                                 │
│  ├── Cross-region replication (us-east-1 → us-west-2)                   │
│  ├── Lifecycle: Standard → IA after 90 days → Glacier after 1 year     │
│  └── MFA delete protection                                              │
│                                                                         │
│  Kubernetes                                                             │
│  ├── Velero: daily backup of all namespaces to S3                       │
│  ├── etcd snapshots: every 2 hours (managed K8s handles this)           │
│  └── GitOps: entire cluster state in Git (ArgoCD)                      │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.3 Failover Strategy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     FAILOVER & HIGH AVAILABILITY                        │
│                                                                         │
│  Single-Region HA (Primary)                                             │
│  ├── PostgreSQL: Multi-AZ (primary in AZ-a, standbys in AZ-b, AZ-c)   │
│  ├── Redis: Multi-AZ cluster (nodes spread across 3 AZs)              │
│  ├── RabbitMQ: 3-node cluster across AZs, quorum queues               │
│  ├── K8s: Nodes across 3 AZs, pod anti-affinity rules                  │
│  └── Application: Rolling deployments, zero-downtime                   │
│                                                                         │
│  Multi-Region DR (Secondary)                                            │
│  ├── Hot Standby in us-west-2 (or eu-west-1 for EU customers)         │
│  │   ├── PostgreSQL: Async replication from primary region             │
│  │   ├── Redis: Independent cluster, synced via application logic      │
│  │   ├── K8s: Pre-provisioned cluster, ArgoCD auto-sync               │
│  │   └── DNS: Cloudflare failover with health checks                  │
│  │                                                                     │
│  ├── Failover Process:                                                 │
│  │   1. Health check detects primary region failure (30s timeout)      │
│  │   2. Cloudflare DNS failover triggers (TTL 60s)                    │
│  │   3. Secondary region promoted: PostgreSQL promoted to primary      │
│  │   4. Application traffic routed to secondary                       │
│  │   5. Team notified via PagerDuty                                   │
│  │   6. Estimated failover time: 2-5 minutes                          │
│  │                                                                     │
│  └── Failback Process:                                                 │
│      1. Primary region restored and verified                           │
│      2. Data synchronized from secondary → primary                    │
│      3. DNS switched back to primary (gradual via weighted routing)    │
│      4. Secondary demoted back to standby                              │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Chaos Engineering

```yaml
# Scheduled chaos experiments (using Litmus Chaos)
experiments:
  - name: pod-kill-random
    schedule: "0 4 * * 3"  # Wednesday 4am
    target: random pod in proactive-seo-prod
    action: delete pod
    expected: self-healing within 60s

  - name: node-drain
    schedule: "0 5 * * 3"  # Wednesday 5am
    target: random node in general pool
    action: cordon + drain
    expected: pods rescheduled, no downtime

  - name: network-latency
    schedule: "0 6 * * 3"  # Wednesday 6am
    target: PostgreSQL primary
    action: add 200ms latency
    expected: replicas serve reads, write latency acceptable

  - name: az-outage
    schedule: "0 3 * * 1"  # Monday 3am (quarterly)
    target: simulate AZ-a failure
    action: block all traffic to AZ-a
    expected: services failover to remaining AZs
```

---

## 7. CI/CD Pipeline

### 7.1 Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD PIPELINE (GitHub Actions + ArgoCD)            │
│                                                                             │
│  Developer Push → GitHub                                                    │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STAGE 1: CI (GitHub Actions)                                        │    │
│  │                                                                      │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │    │
│  │  │ Lint & Format│  │ Unit Tests   │  │ Integration Tests        │   │    │
│  │  │ (ruff, mypy) │  │ (pytest)     │  │ (docker-compose stack)   │   │    │
│  │  │ ~2 min       │  │ ~5 min       │  │ ~10 min                  │   │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘   │    │
│  │         │                 │                      │                   │    │
│  │         ▼                 ▼                      ▼                   │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐   │    │
│  │  │ Security Scan│  │ E2E Tests    │  │ Build Docker Images      │   │    │
│  │  │ (Trivy, Snyk)│  │ (Playwright) │  │ (multi-stage, push GHCR)│   │    │
│  │  │ ~3 min       │  │ ~10 min      │  │ ~5 min                   │   │    │
│  │  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────────┘   │    │
│  │         │                 │                      │                   │    │
│  │         ▼                 ▼                      ▼                   │    │
│  │  ┌──────────────────────────────────────────────────────────────┐   │    │
│  │  │ Push image tags to GitHub Container Registry (GHCR)          │   │    │
│  │  │ Update Helm chart values with new image tags                 │   │    │
│  │  └──────────────────────────────────────────────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STAGE 2: CD (ArgoCD)                                                │    │
│  │                                                                      │    │
│  │  ┌──────────────────┐     ┌──────────────────┐                      │    │
│  │  │ Staging Deploy   │     │ Production Deploy │                      │    │
│  │  │ (auto, on merge  │     │ (manual approval  │                      │    │
│  │  │  to main)        │     │  + canary rollout) │                      │    │
│  │  └────────┬─────────┘     └────────┬──────────┘                      │    │
│  │           │                        │                                 │    │
│  │           ▼                        ▼                                 │    │
│  │  ┌──────────────────┐     ┌──────────────────────────────────┐      │    │
│  │  │ Smoke Tests      │     │ Canary: 10% → 50% → 100%        │      │    │
│  │  │ + Load Tests     │     │ (Flagger progressive delivery)   │      │    │
│  │  │ (k6/Gatling)     │     │                                  │      │    │
│  │  └──────────────────┘     │ Automated rollback if:           │      │    │
│  │                           │   - Error rate > 1%              │      │    │
│  │                           │   - p99 latency > 2s             │      │    │
│  │                           │   - Health check failure         │      │    │
│  │                           └──────────────────────────────────┘      │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  STAGE 3: Post-Deploy                                                │    │
│  │  ├── Synthetic monitoring (canary tests against production)         │    │
│  │  ├── Error rate monitoring (Sentry)                                 │    │
│  │  ├── Performance regression detection                               │    │
│  │  └── Slack notification of deployment status                        │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 7.2 GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  REGISTRY: ghcr.io
  IMAGE_PREFIX: proactive-seo

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync && uv run ruff check . && uv run mypy app/

  test:
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: test_db
          POSTGRES_PASSWORD: test
        ports: ['5432:5432']
      redis:
        image: redis:7
        ports: ['6379:6379']
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync && uv run pytest --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  security:
    runs-on: ubuntu-latest
    needs: lint
    steps:
      - uses: actions/checkout@v4
      - uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
      - uses: snyk/actions/python@master

  build-and-push:
    runs-on: ubuntu-latest
    needs: [test, security]
    if: github.ref == 'refs/heads/main'
    strategy:
      matrix:
        service:
          - keyword-service
          - crawl-service
          - content-service
          - rank-tracker
          - analytics-service
          - auth-service
          - tenant-service
          - notification-service
          - billing-service
          - report-service
          - link-analysis
          - ai-service
          - audit-service
          - frontend
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - uses: docker/build-push-action@v5
        with:
          context: ./services/${{ matrix.service }}
          push: true
          tags: |
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service }}:${{ github.sha }}
            ${{ env.REGISTRY }}/${{ env.IMAGE_PREFIX }}/${{ matrix.service }}:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    runs-on: ubuntu-latest
    needs: build-and-push
    steps:
      - uses: actions/checkout@v4
      - name: Update Helm values for staging
        run: |
          # Update image tags in ArgoCD Helm values
          yq -i '.image.tag = "${{ github.sha }}"' \
            k8s/staging/values.yaml
      - name: Commit to staging branch
        run: |
          git config user.name "CI Bot"
          git config user.email "ci@proactiveseo.com"
          git add k8s/staging/values.yaml
          git commit -m "deploy: staging ${{ github.sha }}"
          git push origin staging

  deploy-production:
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.ref == 'refs/heads/main'
    environment: production  # Requires manual approval
    steps:
      - uses: actions/checkout@v4
      - name: Update Helm values for production
        run: |
          yq -i '.image.tag = "${{ github.sha }}"' \
            k8s/production/values.yaml
      - name: Commit to production branch
        run: |
          git config user.name "CI Bot"
          git config user.email "ci@proactiveseo.com"
          git add k8s/production/values.yaml
          git commit -m "deploy: production ${{ github.sha }}"
          git push origin production
```

### 7.3 ArgoCD Application

```yaml
# argocd/application.yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: proactive-seo-production
  namespace: argocd
spec:
  project: proactive-seo
  source:
    repoURL: https://github.com/proactive-seo/infra.git
    targetRevision: production
    path: k8s/production
    helm:
      valueFiles:
        - values.yaml
        - values-production.yaml
  destination:
    server: https://kubernetes.default.svc
    namespace: proactive-seo-prod
  syncPolicy:
    automated:
      prune: true
      selfHealf: true
    syncOptions:
      - CreateNamespace=true
      - PrunePropagationPolicy=foreground
    retry:
      limit: 5
      backoff:
        duration: 5s
        factor: 2
        maxDuration: 3m
```

---

## 8. Environment Configuration

### 8.1 Environment Matrix

```
┌──────────────────────┬──────────────────┬──────────────────┬──────────────────┐
│ Aspect               │ Development      │ Staging          │ Production       │
├──────────────────────┼──────────────────┼──────────────────┼──────────────────┤
│ Cluster              │ docker-compose   │ EKS/GKE (shared) │ EKS/GKE (ded.)  │
│ Namespace            │ local            │ proactive-staging │ proactive-prod   │
│ Replicas (per svc)   │ 1                │ 2                │ 3-10 (auto)      │
│ PostgreSQL           │ Docker container │ RDS db.t3.medium │ RDS db.r6g.2xl   │
│ Read Replicas        │ 0                │ 1                │ 3-5              │
│ Redis                │ Docker container │ ElastiCache t3   │ ElastiCache r6g  │
│ Redis Nodes          │ 1 (standalone)   │ 3 (cluster)      │ 7 (cluster)      │
│ RabbitMQ             │ Docker container │ AmazonMQ t3      │ AmazonMQ m5      │
│ Elasticsearch        │ Docker container │ 3-node t3        │ 5-node r6g       │
│ ClickHouse           │ Docker container │ 3-node           │ 3-node (larger)  │
│ S3 Storage           │ MinIO (local)    │ AWS S3           │ AWS S3           │
│ CDN                  │ none             │ Cloudflare (dev) │ Cloudflare (pro) │
│ SSL                  │ self-signed      │ Let's Encrypt    │ Cloudflare TLS   │
│ Domain               │ localhost:3000   │ staging.app.com  │ app.com          │
│ Secrets              │ .env files       │ Vault (dev)      │ Vault (prod)     │
│ Monitoring           │ basic (stdout)   │ Prometheus+Grafana│ Full stack       │
│ Log Level            │ DEBUG            │ INFO             │ WARNING          │
│ Feature Flags        │ all enabled      │ production-like  │ gradual rollout  │
│ Rate Limiting        │ disabled         │ lenient          │ strict           │
│ Email                │ Mailhog (local)  │ SendGrid (test)  │ SendGrid/SES     │
│ LLM                  │ mock responses   │ real (limited)   │ real (full)      │
│ SERP Scraping        │ mock data        │ real (limited)   │ real (full)      │
│ Data                 │ seed data        │ anonymized prod  │ real data        │
│ Backup               │ none             │ daily            │ continuous+daily │
│ Cost Estimate/month  │ ~$0              │ ~$2,000          │ ~$15,000-30,000  │
└──────────────────────┴──────────────────┴──────────────────┴──────────────────┘
```

### 8.2 Environment Variables (Shared ConfigMap)

```yaml
# k8s/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: proactive-seo-config
  namespace: proactive-seo-prod
data:
  APP_NAME: "ProActive SEO"
  APP_ENV: "production"
  APP_VERSION: "1.0.0"
  LOG_LEVEL: "WARNING"
  LOG_FORMAT: "json"

  # Database
  DB_HOST: "proactive-seo-db.xxxxx.us-east-1.rds.amazonaws.com"
  DB_PORT: "5432"
  DB_NAME: "proactive_seo"
  DB_POOL_SIZE: "20"
  DB_MAX_OVERFLOW: "40"
  DB_POOL_RECYCLE: "300"

  # Read Replicas
  DB_READ_HOSTS: "proactive-seo-db-ro-1.xxxxx.rds.amazonaws.com,proactive-seo-db-ro-2.xxxxx.rds.amazonaws.com,proactive-seo-db-ro-3.xxxxx.rds.amazonaws.com"

  # Redis
  REDIS_HOST: "proactive-seo-cache.xxxxx.cache.amazonaws.com"
  REDIS_PORT: "6379"
  REDIS_DB_CACHE: "0"
  REDIS_DB_SESSION: "1"
  REDIS_DB_QUEUE: "2"

  # RabbitMQ
  RABBITMQ_HOST: "proactive-seo-mq.xxxxx.mq.us-east-1.amazonaws.com"
  RABBITMQ_PORT: "5672"
  RABBITMQ_VHOST: "proactive_seo"

  # Elasticsearch
  ES_HOSTS: "https://proactive-seo-es.xxxxx.us-east-1.es.amazonaws.com"
  ES_INDEX_PREFIX: "proactive-seo"

  # ClickHouse
  CLICKHOUSE_HOST: "proactive-seo-ch.xxxxx.us-east-1.aws.clickhouse.cloud"
  CLICKHOUSE_PORT: "8443"
  CLICKHOUSE_DATABASE: "proactive_seo"

  # S3
  S3_BUCKET: "proactive-seo-production"
  S3_REGION: "us-east-1"
  S3_ENDPOINT: ""  # Empty for AWS S3, set for MinIO

  # Auth
  KEYCLOAK_URL: "https://auth.proactiveseo.com"
  KEYCLOAK_REALM: "proactive-seo"
  KEYCLOAK_CLIENT_ID: "proactive-seo-api"

  # External APIs
  OPENAI_API_KEY: ""  # From Vault
  ANTHROPIC_API_KEY: ""  # From Vault
  SENDGRID_API_KEY: ""  # From Vault
  STRIPE_SECRET_KEY: ""  # From Vault

  # Feature Flags
  FEATURE_AI_CONTENT: "true"
  FEATURE_BULK_IMPORT: "true"
  FEATURE_WHITE_LABEL: "true"
  FEATURE_API_ACCESS: "true"

  # Rate Limiting
  RATE_LIMIT_API: "100/minute"
  RATE_LIMIT_CRAWL: "10/minute"
  RATE_LIMIT_KEYWORD_RESEARCH: "20/minute"
```

### 8.3 Secrets Management (HashiCorp Vault)

```yaml
# Vault policy structure
secret/proactive-seo/production/database    → DB credentials
secret/proactive-seo/production/redis       → Redis password
secret/proactive-seo/production/rabbitmq    → RabbitMQ credentials
secret/proactive-seo/production/jwt         → JWT signing keys
secret/proactive-seo/production/openai      → OpenAI API key
secret/proactive-seo/production/anthropic   → Anthropic API key
secret/proactive-seo/production/stripe      → Stripe keys
secret/proactive-seo/production/sendgrid    → SendGrid API key
secret/proactive-seo/production/s3          → AWS credentials (if not using IRSA)

# Kubernetes integration via Vault Agent Injector
apiVersion: apps/v1
kind: Deployment
metadata:
  name: keyword-service
spec:
  template:
    metadata:
      annotations:
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "proactive-seo"
        vault.hashicorp.com/agent-inject-secret-db: "secret/data/proactive-seo/production/database"
        vault.hashicorp.com/agent-inject-template-db: |
          {{- with secret "secret/data/proactive-seo/production/database" -}}
          export DB_USER="{{ .Data.data.username }}"
          export DB_PASSWORD="{{ .Data.data.password }}"
          {{- end }}
```

---

## 9. Network Topology

### 9.1 Network Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                            │
│                           (Users, APIs)                                          │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                        CLOUDFLARE EDGE NETWORK                                  │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────────────────┐ │
│   │ DNS        │  │ WAF        │  │ DDoS       │  │ SSL/TLS (Full Strict)   │ │
│   │ (Anycast)  │  │ (OWASP 10) │  │ Protection │  │ Origin: self-signed     │ │
│   └────────────┘  └────────────┘  └────────────┘  └──────────────────────────┘ │
└─────────────────────────────────┬───────────────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │    AWS VPC 10.0.0.0/16     │
                    │                             │
                    ▼                             ▼
┌──────────────────────────────────┐  ┌──────────────────────────────────────────┐
│  PUBLIC SUBNETS (10.0.0.0/20)   │  │  PRIVATE SUBNETS (10.0.16.0/20)          │
│                                  │  │                                          │
│  ┌──────────────────────────┐   │  │  ┌──────────────────────────────────┐    │
│  │  ALB / NLB               │   │  │  │  EKS Worker Nodes                │    │
│  │  (Internet-facing)       │   │  │  │  (10.0.16.0 - 10.0.31.255)      │    │
│  │                          │   │  │  │                                  │    │
│  │  Ports: 80, 443          │   │  │  │  ┌────────────────────────────┐  │    │
│  │  Target: NGINX Ingress   │   │  │  │  │  General Node Pool        │  │    │
│  └──────────────────────────┘   │  │  │  │  (m6i.2xlarge x6-12)      │  │    │
│                                  │  │  │  ├────────────────────────────┤  │    │
│  ┌──────────────────────────┐   │  │  │  │  Worker Node Pool         │  │    │
│  │  NAT Gateway             │   │  │  │  │  (c6i.4xlarge x4-20)      │  │    │
│  │  (outbound internet      │   │  │  │  ├────────────────────────────┤  │    │
│  │   for K8s pods)          │   │  │  │  │  GPU Node Pool            │  │    │
│  └──────────────────────────┘   │  │  │  │  (g5.xlarge x2-5)        │  │    │
│                                  │  │  │  └────────────────────────────┘  │    │
└──────────────────────────────────┘  │  └──────────────────────────────────┘    │
                                      │                                          │
                                      │  ┌──────────────────────────────────┐    │
                                      │  │  DATA SUBNETS (10.0.32.0/20)     │    │
                                      │  │  (Private, no internet access)   │    │
                                      │  │                                  │    │
                                      │  │  ┌────────────────────────────┐  │    │
                                      │  │  │  RDS PostgreSQL           │  │    │
                                      │  │  │  (10.0.32.10)             │  │    │
                                      │  │  │  Port: 5432               │  │    │
                                      │  │  ├────────────────────────────┤  │    │
                                      │  │  │  ElastiCache Redis        │  │    │
                                      │  │  │  (10.0.32.20-26)          │  │    │
                                      │  │  │  Port: 6379               │  │    │
                                      │  │  ├────────────────────────────┤  │    │
                                      │  │  │  Amazon MQ (RabbitMQ)     │  │    │
                                      │  │  │  (10.0.32.30-32)          │  │    │
                                      │  │  │  Ports: 5672, 15672       │  │    │
                                      │  │  ├────────────────────────────┤  │    │
                                      │  │  │  OpenSearch (ES)          │  │    │
                                      │  │  │  (10.0.32.40-44)          │  │    │
                                      │  │  │  Ports: 443               │  │    │
                                      │  │  ├────────────────────────────┤  │    │
                                      │  │  │  ClickHouse               │  │    │
                                      │  │  │  (10.0.32.50-52)          │  │    │
                                      │  │  │  Ports: 8443, 9000        │  │    │
                                      │  │  └────────────────────────────┘  │    │
                                      │  └──────────────────────────────────┘    │
                                      └──────────────────────────────────────────┘

Security Groups:
  alb-sg:       inbound 80,443 from 0.0.0.0/0 → outbound to eks-sg
  eks-sg:       inbound from alb-sg + self → outbound to data-sg + NAT
  data-sg:      inbound from eks-sg only → outbound to eks-sg only
  bastion-sg:   inbound 22 from VPN CIDR → outbound to eks-sg, data-sg
```

### 9.2 Service Mesh (Istio)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ISTIO SERVICE MESH                                  │
│                                                                             │
│  Features Enabled:                                                          │
│  ├── mTLS: All pod-to-pod communication encrypted (strict mode)            │
│  ├── Traffic Management:                                                    │
│  │   ├── Canary deployments (10% → 50% → 100%)                            │
│  │   ├── Circuit breaking (5xx threshold: 5, consecutive errors: 5)        │
│  │   ├── Retries (3 attempts, 25ms-250ms backoff)                          │
│  │   └── Timeout (30s default, per-service overrides)                      │
│  ├── Observability:                                                         │
│  │   ├── Distributed tracing (Jaeger integration)                          │
│  │   ├── Request-level metrics (Prometheus)                                │
│  │   └── Access logging (Loki)                                             │
│  └── Security:                                                              │
│      ├── AuthorizationPolicy per service (who can call whom)               │
│      ├── JWT validation at mesh level                                       │
│      └── Rate limiting per source service                                   │
│                                                                             │
│  VirtualService Example:                                                    │
│  apiVersion: networking.istio.io/v1beta1                                   │
│  kind: VirtualService                                                       │
│  spec:                                                                      │
│    hosts: [keyword-service]                                                 │
│    http:                                                                     │
│      - route:                                                                │
│          - destination:                                                     │
│              host: keyword-service                                          │
│              subset: stable                                                 │
│            weight: 90                                                       │
│          - destination:                                                     │
│              host: keyword-service                                          │
│              subset: canary                                                 │
│            weight: 10                                                       │
│        timeout: 30s                                                         │
│        retries:                                                              │
│          attempts: 3                                                        │
│          perTryTimeout: 10s                                                 │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 10. Data Flow Diagrams

### 10.1 Keyword Tracking Flow

```
┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐
│ Celery   │    │ RabbitMQ  │    │ SERP      │    │ Proxy    │    │ Google   │
│ Beat     │───▶│ Queue:    │───▶│ Worker    │───▶│ Network  │───▶│ SERP     │
│ (cron)   │    │ serp.fetch│    │ (fetch)   │    │ (rotate) │    │          │
└──────────┘    └───────────┘    └─────┬─────┘    └──────────┘    └──────────┘
                                       │
                                       ▼
                                 ┌───────────┐
                                 │ Parse SERP│
                                 │ Extract   │
                                 │ positions │
                                 └─────┬─────┘
                                       │
                          ┌────────────┼────────────┐
                          ▼            ▼            ▼
                    ┌──────────┐ ┌──────────┐ ┌──────────────┐
                    │ClickHouse│ │PostgreSQL│ │ Notification │
                    │ (raw     │ │ (delta   │ │ Service      │
                    │  SERP)   │ │  calc)   │ │ (alerts)     │
                    └──────────┘ └────┬─────┘ └──────┬───────┘
                                      │              │
                                      ▼              ▼
                                ┌──────────┐  ┌───────────┐
                                │ Frontend │  │ Slack/    │
                                │ Dashboard│  │ Email     │
                                └──────────┘  └───────────┘
```

### 10.2 Content Optimization Flow

```
┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐
│ User     │    │ Content   │    │ SERP      │    │ AI       │
│ enters   │───▶│ Service   │───▶│ Analysis  │───▶│ Service  │
│ URL +    │    │ (optimize)│    │ (top 10)  │    │ (score)  │
│ keyword  │    └───────────┘    └─────┬─────┘    └────┬─────┘
└──────────┘                          │               │
                                      ▼               ▼
                                ┌───────────┐  ┌──────────────┐
                                │ NLP Entity│  │ Content Score│
                                │ Extraction│  │ (0-100)      │
                                └─────┬─────┘  └──────┬───────┘
                                      │               │
                                      ▼               ▼
                                ┌─────────────────────────────┐
                                │ Generate Recommendations:   │
                                │ - Add missing entities      │
                                │ - Improve readability       │
                                │ - Optimize keyword density  │
                                │ - Suggest internal links    │
                                │ - Generate meta variants    │
                                └─────────────┬───────────────┘
                                              │
                                              ▼
                                        ┌──────────┐
                                        │ Frontend │
                                        │ UI with  │
                                        │ live     │
                                        │ scoring  │
                                        └──────────┘
```

### 10.3 Crawl & Audit Flow

```
┌──────────┐    ┌───────────┐    ┌───────────┐    ┌──────────┐
│ User     │    │ Crawl     │    │ URL       │    │ HTTP     │
│ starts   │───▶│ Service   │───▶│ Frontier  │───▶│ Fetcher  │
│ crawl    │    │ (create)  │    │ (queue)   │    │ (async)  │
└──────────┘    └───────────┘    └─────┬─────┘    └────┬─────┘
                                       │               │
                                       │        ┌──────▼──────┐
                                       │        │ Playwright  │
                                       │        │ (JS render) │
                                       │        └──────┬──────┘
                                       │               │
                                       ▼               ▼
                                 ┌─────────────────────────────┐
                                 │  PARSE & ANALYZE            │
                                 │  ├── Extract links          │
                                 │  ├── Extract meta tags      │
                                 │  ├── Validate structured    │
                                 │  │   data (JSON-LD)         │
                                 │  ├── Check status codes     │
                                 │  ├── Measure load time      │
                                 │  ├── Screenshot (Playwright)│
                                 │  └── Run 50+ SEO checks     │
                                 └─────────────┬───────────────┘
                                               │
                          ┌────────────────────┼────────────────┐
                          ▼                    ▼                ▼
                    ┌──────────┐        ┌──────────┐    ┌──────────┐
                    │PostgreSQL│        │ S3       │    │Elastic-  │
                    │ (pages,  │        │(screenshots│   │search    │
                    │  issues) │        │ & HTML)  │    │(index)   │
                    └──────────┘        └──────────┘    └──────────┘
```

---

## 11. Security Architecture

### 11.1 Security Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SECURITY ARCHITECTURE                                 │
│                                                                             │
│  Layer 1: Edge (Cloudflare)                                                 │
│  ├── WAF rules (OWASP Top 10)                                              │
│  ├── DDoS protection (L3/L4/L7)                                           │
│  ├── Bot management                                                        │
│  ├── Rate limiting (IP-based, 1000 req/min)                               │
│  └── SSL/TLS (Full Strict mode)                                            │
│                                                                             │
│  Layer 2: Ingress (NGINX Ingress Controller)                               │
│  ├── Additional rate limiting (service-specific)                           │
│  ├── Request size limits                                                   │
│  ├── CORS policies                                                         │
│  └── Security headers (HSTS, CSP, X-Frame-Options)                        │
│                                                                             │
│  Layer 3: API Gateway (Kong)                                                │
│  ├── JWT validation (RSA256)                                               │
│  ├── API key authentication                                                │
│  ├── OAuth 2.0 token introspection                                        │
│  ├── Request transformation                                                │
│  ├── Response filtering (hide internal details)                            │
│  ├── Rate limiting per API key/user                                        │
│  └── Request logging & audit                                               │
│                                                                             │
│  Layer 4: Application                                                       │
│  ├── RBAC (Role-Based Access Control)                                      │
│  ├── Tenant isolation (row-level security)                                 │
│  ├── Input validation (Pydantic)                                           │
│  ├── SQL injection prevention (SQLAlchemy parameterization)                │
│  ├── XSS prevention (output encoding)                                      │
│  └── Business logic authorization                                          │
│                                                                             │
│  Layer 5: Data                                                              │
│  ├── Encryption at rest (AES-256 for RDS, S3)                              │
│  ├── Encryption in transit (TLS 1.3 everywhere)                            │
│  ├── Field-level encryption (PII, credentials)                             │
│  ├── Database row-level security (PostgreSQL RLS)                          │
│  └── Audit logging (all data access logged)                                │
│                                                                             │
│  Layer 6: Infrastructure                                                    │
│  ├── VPC with private subnets (data tier)                                  │
│  ├── Security groups (least privilege)                                     │
│  ├── Network policies (Kubernetes)                                         │
│  ├── Pod security standards (restricted)                                   │
│  ├── Secrets management (HashiCorp Vault)                                  │
│  └── Container image scanning (Trivy in CI)                               │
│                                                                             │
│  Layer 7: Identity                                                          │
│  ├── Keycloak (SSO, MFA, session management)                              │
│  ├── Password policy (min 12 chars, complexity)                            │
│  ├── Account lockout (5 failed attempts → 15min lock)                     │
│  ├── Session timeout (30min idle, 24h absolute)                            │
│  └── API key rotation (90-day expiry, manual)                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 11.2 Multi-Tenant Isolation

```sql
-- PostgreSQL Row-Level Security (RLS)
ALTER TABLE keywords ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON keywords
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Every query sets tenant context
SET app.current_tenant_id = 'tenant-uuid-here';

-- Additional: connection-level tenant isolation for sensitive operations
-- Each service extracts tenant_id from JWT token, never from request body
```

---

## 12. Cache Invalidation Strategy

### 12.1 Cache Layers

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CACHE ARCHITECTURE                                   │
│                                                                             │
│  Layer 1: CDN Cache (Cloudflare)                                           │
│  ├── Static assets: CSS, JS, images → Cache-Control: max-age=31536000     │
│  ├── API responses: dashboard data → Cache-Control: max-age=300            │
│  ├── Purge: On deploy (all) or per-URL (content update)                    │
│  └── Edge TTL: 5min-24h depending on content type                          │
│                                                                             │
│  Layer 2: Application Cache (Redis Cluster — 64GB cache namespace)         │
│  ├── Key patterns:                                                          │
│  │   tenant:{id}:keywords:list         → TTL: 60s                          │
│  │   tenant:{id}:keyword:{id}:positions → TTL: 1h                         │
│  │   tenant:{id}:dashboard             → TTL: 5min                         │
│  │   tenant:{id}:crawl:{id}:summary    → TTL: 10min                        │
│  │   keyword:search-volume:{keyword}   → TTL: 7d                           │
│  │   serp:features:{keyword}:{country} → TTL: 24h                          │
│  │   content:score:{page_id}           → TTL: 1h                           │
│  │   user:{id}:profile                 → TTL: 15min                        │
│  │   rate_limit:{api_key}:{window}     → TTL: window                       │
│  │                                                                         │
│  ├── Invalidation strategies:                                               │
│  │   ├── TTL-based: Most caches expire naturally                           │
│  │   ├── Event-driven: Domain events trigger cache bust                    │
│  │   │   (e.g., keyword.position.updated → bust keyword:{id}:positions)   │
│  │   ├── Write-through: Update cache on write for hot data                 │
│  │   └── Manual: Admin can flush per-tenant caches                        │
│  │                                                                         │
│  └── Cache warming:                                                         │
│      ├── On tenant login: pre-warm dashboard + recent keywords             │
│      ├── On crawl completion: pre-warm crawl summary                       │
│      └── Scheduled: Celery Beat warms top-100 keywords per tenant daily   │
│                                                                             │
│  Layer 3: Session Cache (Redis Cluster — 32GB session namespace)           │
│  ├── Session storage: user:{session_id} → JSON → TTL: 24h                 │
│  ├── JWT blacklist: blacklist:{jti} → TTL: token_expiry                   │
│  └── OAuth state: oauth:{state} → TTL: 5min                               │
│                                                                             │
│  Layer 4: Database Query Cache (PgBouncer + application-level)             │
│  ├── Prepared statements cached in PgBouncer                               │
│  ├── SQLAlchemy query result caching for read-heavy patterns               │
│  └── Materialized views for dashboard aggregations (refreshed every 5min)  │
│                                                                             │
│  Layer 5: Browser Cache                                                     │
│  ├── Service worker for offline-capable dashboard                          │
│  ├── LocalStorage for user preferences                                     │
│  └── IndexedDB for offline keyword data                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 12.2 Cache Invalidation Event Flow

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Rank Tracker │    │ RabbitMQ     │    │ Cache        │
│ publishes    │───▶│ Exchange:    │───▶│ Invalidator  │
│ event:       │    │ cache.invalidate│  │ Service      │
│ keyword.pos  │    │              │    │              │
│ .updated     │    └──────────────┘    └──────┬───────┘
└──────────────┘                               │
                                               │  DEL pattern:{tenant}:{id}:*
                                               ▼
                                         ┌──────────┐
                                         │ Redis    │
                                         │ Cluster  │
                                         │ (delete) │
                                         └──────────┘
```

---

## 13. Database Replication & Sharding

### 13.1 PostgreSQL Replication

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    POSTGRESQL REPLICATION ARCHITECTURE                       │
│                                                                             │
│  ┌──────────────────┐                                                       │
│  │  PRIMARY          │  AZ-a                                                │
│  │  (db.r6g.2xlarge) │                                                      │
│  │  Writer + DDL     │                                                      │
│  │  8 vCPU, 64GB RAM │                                                      │
│  │  500GB gp3 SSD    │                                                      │
│  │  12K IOPS, 500MB/s│                                                      │
│  └────────┬─────────┘                                                       │
│           │                                                                 │
│     Streaming replication (synchronous for 1 replica, async for rest)       │
│           │                                                                 │
│  ┌────────┴────────────────────────────────────────────────────┐            │
│  │                                                             │            │
│  ▼              ▼                    ▼              ▼           │            │
│ ┌──────────┐  ┌──────────┐      ┌──────────┐  ┌──────────┐   │            │
│ │Replica 1 │  │Replica 2 │      │Replica 3 │  │Replica 4 │   │            │
│ │(sync)    │  │(async)   │      │(async)   │  │(async)   │   │            │
│ │AZ-b      │  │AZ-c      │      │AZ-b      │  │AZ-c      │   │            │
│ │Hot standby│ │Hot standby│     │Reporting │  │Analytics │   │            │
│ │Failover  │  │Read-only │      │Read-only │  │Read-only │   │            │
│ └──────────┘  └──────────┘      └──────────┘  └──────────┘   │            │
│                                                                │            │
│  PgBouncer (Connection Pooler)                                 │            │
│  ├── Primary pool: writes (max 200 connections)                │            │
│  ├── Replica pool: reads (round-robin, max 500 connections)   │            │
│  └── Transaction-level pooling                                 │            │
│                                                                │            │
│  Monitoring:                                                   │            │
│  ├── Replication lag: < 100ms (sync), < 1s (async)           │            │
│  ├── Connection count: alert at 80%                           │            │
│  ├── Query duration: alert at p99 > 1s                        │            │
│  └── Deadlocks: alert on any occurrence                       │            │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Table Partitioning Strategy

```sql
-- Keyword positions: partitioned by month (hot data in recent partitions)
CREATE TABLE keyword_positions (
    id BIGSERIAL,
    tenant_id UUID NOT NULL,
    keyword_id BIGINT NOT NULL,
    position SMALLINT NOT NULL,
    url TEXT,
    search_engine VARCHAR(20),
    device VARCHAR(10),
    country VARCHAR(3),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- Create partitions for each month
CREATE TABLE keyword_positions_2026_01 PARTITION OF keyword_positions
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE keyword_positions_2026_02 PARTITION OF keyword_positions
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
-- ... automated partition creation via pg_partman

-- Indexes on each partition
CREATE INDEX idx_kp_tenant_keyword ON keyword_positions (tenant_id, keyword_id, recorded_at DESC);
CREATE INDEX idx_kp_recorded_at ON keyword_positions (recorded_at);

-- Crawl results: partitioned by tenant hash (even distribution)
CREATE TABLE crawled_pages (
    id BIGSERIAL,
    tenant_id UUID NOT NULL,
    crawl_id UUID NOT NULL,
    url TEXT NOT NULL,
    status_code SMALLINT,
    -- ...
    PRIMARY KEY (id, tenant_id)
) PARTITION BY HASH (tenant_id);

CREATE TABLE crawled_pages_p0 PARTITION OF crawled_pages FOR VALUES WITH (MODULUS 8, REMAINDER 0);
CREATE TABLE crawled_pages_p1 PARTITION OF crawled_pages FOR VALUES WITH (MODULUS 8, REMAINDER 1);
-- ... 8 partitions for even distribution
```

### 13.3 Future Sharding Strategy

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SHARDING ROADMAP                                          │
│                                                                             │
│  Phase 1 (Current - 0-50K tenants):                                        │
│  ├── Single PostgreSQL cluster (primary + replicas)                        │
│  ├── Table partitioning by time (keyword_positions) and hash (crawls)      │
│  ├── Citus extension for distributed queries (if needed)                   │
│  └── Vertical scaling: upgrade instance type                               │
│                                                                             │
│  Phase 2 (50K-200K tenants):                                               │
│  ├── Tenant-based sharding: hash(tenant_id) → shard                       │
│  ├── 4 shards, each with primary + 2 replicas                             │
│  ├── Application-level routing: shard = hash(tenant_id) % num_shards      │
│  ├── Cross-shard queries: via Citus coordinator or application             │
│  └── Migration: online schema migration via pg_repack                      │
│                                                                             │
│  Phase 3 (200K+ tenants):                                                  │
│  ├── Move to Citus distributed tables (native sharding)                    │
│  ├── Reference tables for shared data (plans, features)                    │
│  ├── Distributed tables for tenant data (colocated by tenant_id)           │
│  ├── ClickHouse for all analytics queries                                  │
│  └── Consider Aurora PostgreSQL for managed scaling                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Appendix A: Helm Chart Structure

```
k8s/
├── base/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml (encrypted with SOPS)
│   ├── network-policies.yaml
│   └── pod-security.yaml
├── services/
│   ├── keyword-service/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml
│   │   ├── pdb.yaml
│   │   └── servicemonitor.yaml
│   ├── crawl-service/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml
│   │   ├── keda-scaledobject.yaml
│   │   └── pdb.yaml
│   └── ... (all services)
├── workers/
│   ├── celery-worker-crawl/
│   │   ├── deployment.yaml
│   │   └── keda-scaledobject.yaml
│   └── ... (all workers)
├── infrastructure/
│   ├── prometheus/
│   ├── grafana/
│   ├── loki/
│   ├── jaeger/
│   ├── argocd/
│   └── vault/
├── staging/
│   ├── values.yaml
│   └── kustomization.yaml
└── production/
    ├── values.yaml
    ├── values-production.yaml
    └── kustomization.yaml
```

## Appendix B: Health Check Endpoints

```
Every service exposes:
  GET /health          → 200 OK (liveness)
  GET /health/ready    → 200 OK (readiness — includes DB/Redis checks)
  GET /health/startup  → 200 OK (startup probe)
  GET /metrics         → Prometheus metrics

Kubernetes probes:
  livenessProbe:
    httpGet: { path: /health, port: 8000 }
    initialDelaySeconds: 10
    periodSeconds: 15
    failureThreshold: 3
  readinessProbe:
    httpGet: { path: /health/ready, port: 8000 }
    initialDelaySeconds: 5
    periodSeconds: 10
    failureThreshold: 3
  startupProbe:
    httpGet: { path: /health/startup, port: 8000 }
    failureThreshold: 30
    periodSeconds: 10
```

## Appendix C: Rate Limiting Configuration

```
┌──────────────────────────────┬──────────────┬──────────────────────────────┐
│ Endpoint Category            │ Rate Limit   │ Scope                        │
├──────────────────────────────┼──────────────┼──────────────────────────────┤
│ Auth (login, register)       │ 10/min       │ per IP                       │
│ API (read endpoints)         │ 100/min      │ per API key                  │
│ API (write endpoints)        │ 30/min       │ per API key                  │
│ Keyword research             │ 20/min       │ per tenant                   │
│ Crawl initiation             │ 10/hour      │ per tenant                   │
│ Content generation           │ 50/hour      │ per tenant (plan-based)      │
│ Report generation            │ 10/hour      │ per tenant                   │
│ Bulk import                  │ 5/day        │ per tenant                   │
│ Webhook delivery             │ 100/min      │ per tenant                   │
│ File upload                  │ 100MB/req    │ per request                  │
│ Search/autocomplete          │ 200/min      │ per user                     │
│ WebSocket connections        │ 5/user       │ per user                     │
└──────────────────────────────┴──────────────┴──────────────────────────────┘
```

---

> **Document Status:** Production-ready architecture specification.  
> **Review Cycle:** Quarterly, or upon significant infrastructure changes.  
> **Owner:** Platform Engineering Team  
> **Next Review:** 2026-10-19
