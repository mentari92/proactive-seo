# 04 — Agent System Specification

> **Status:** Production-Ready  
> **Version:** 2.0  
> **Last Updated:** 2026-07-19  
> **Scope:** 8 autonomous agents with full execution layer integration

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Agent 1: Crawl Agent (Sentinel)](#2-agent-1-crawl-agent-sentinel)
3. [Agent 2: Content Agent (Forge)](#3-agent-2-content-agent-forge)
4. [Agent 3: Technical Agent](#4-agent-3-technical-agent)
5. [Agent 4: Rank Agent (Scout)](#5-agent-4-rank-agent-scout)
6. [Agent 5: Backlink & Outreach Agent](#6-agent-5-backlink--outreach-agent)
7. [Agent 6: Competitor Agent](#7-agent-6-competitor-agent)
8. [Agent 7: Decision Engine](#8-agent-7-decision-engine)
9. [Agent 8: Action Executor](#9-agent-8-action-executor)
10. [Inter-Agent Communication Protocol](#10-inter-agent-communication-protocol)
11. [Shared Infrastructure](#11-shared-infrastructure)
12. [Deployment & Operations](#12-deployment--operations)

---

## 1. System Overview

### 1.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DECISION ENGINE (Orchestrator)                     │
│   Priority Scoring │ Resource Allocation │ Conflict Resolution │ Triggers   │
└──────┬──────────────┬──────────────────────┬──────────────────────┬─────────┘
       │              │                      │                      │
       ▼              ▼                      ▼                      ▼
┌────────────┐ ┌────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  SENTINEL  │ │   FORGE    │ │    TECHNICAL      │ │     SCOUT        │
│ Crawl Agent│ │Content Agt │ │     Agent         │ │   Rank Agent     │
│            │ │            │ │                   │ │                  │
│• Multi-Eng │ │• On-page   │ │• CWV Monitor     │ │• SERP Tracking   │
│• Broken    │ │• Keywords  │ │• Schema Gen      │ │• Feature Detect  │
│• Index     │ │• Content   │ │• Self-Healing    │ │• Position Alert  │
│• Sitemap   │ │• AEO/GEO   │ │• Validation      │ │• Local SERP      │
└──────┬─────┘ └─────┬──────┘ └────────┬─────────┘ └────────┬─────────┘
       │             │                 │                     │
       ▼             ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BACKLINK & OUTREACH AGENT                                │
│  HARO │ Broken Link │ Guest Post │ Unlinked Mention │ Campaign Tracker      │
│  Gmail API │ Exa AI │ Tavily │ DataForSEO │ Follow-ups │ Link Verification     │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
       ┌───────────────────────────────┼───────────────────────────────┐
       ▼                               ▼                               ▼
┌────────────┐                 ┌──────────────────┐           ┌──────────────────┐
│ COMPETITOR │                 │ ACTION EXECUTOR   │           │  SHARED LAYER    │
│   AGENT    │                 │                   │           │                  │
│• Content   │                 │• Auto-Fix         │           │• Message Bus     │
│• Keywords  │                 │• Publishing       │           │• State Store     │
│• Backlinks │                 │• Email Send       │           │• API Gateway     │
│• Gaps      │                 │• Notifications    │           │• Rate Limiter    │
└────────────┘                 └──────────────────┘           │• Circuit Breaker │
                                                               └──────────────────┘
```

### 1.2 Execution Layer API Registry

| API | Purpose | Rate Limit | Auth | Endpoint |
|-----|---------|------------|------|----------|
| **Gmail API** | Send outreach emails, track opens, webhooks | 250/day (consumer), 1500/day (workspace) | OAuth2 | `https://gmail.googleapis.com/gmail/v1/` |
| **Exa AI** | Semantic search, content extraction, link discovery | 1000 req/min | API Key | `https://api.exa.ai/` |
| **Tavily** | Research queries, content extraction | 1000 req/day (pro) | API Key | `https://api.tavily.com/` |
| **DataForSEO SERP API** | SERP tracking across engines (Google, Bing, Yandex, Naver) | 2000 req/min | Basic Auth | `https://api.dataforseo.com/v3/serp` |
| **GSC API** | Search analytics, index management | 200 req/min | OAuth2 | `https://searchconsole.googleapis.com/webmasters/v3/` |
| **Bing Webmaster** | Bing crawl/index data | 120 req/min | API Key | `https://ssl.bing.com/webmaster/api.svc/json/` |
| **Yandex Webmaster** | Yandex index/crawl data | 100 req/min | OAuth2 | `https://api.webmaster.yandex.net/v4/` |
| **Naver Webmaster** | Naver search data | 60 req/min | API Key | `https://searchadvisor.naver.com/api/` |
| **GA4 API** | Traffic analytics, conversion data | 10,000 req/day | OAuth2 | `https://analyticsdata.googleapis.com/v1beta/` |
| **DataForSEO Backlinks API** | Backlink data, domain rank, referring domains | 2000 req/min | Basic Auth | `https://api.dataforseo.com/v3/backlinks` |
| **PageSpeed Insights** | Core Web Vitals, performance scores | 60 req/min | API Key | `https://www.googleapis.com/pagespeedonline/v5/runPagespeed` |

### 1.3 Message Bus Protocol

All agents communicate through an event-driven message bus (Redis Streams):

```
Stream: seo:agent:events
Consumer Groups: sentinel, forge, technical, scout, outreach, competitor, decision, executor

Event Schema:
{
  "event_id": "uuid-v7",
  "timestamp": "ISO-8601",
  "source_agent": "sentinel",
  "target_agent": "decision|broadcast",
  "event_type": "issue.detected|task.completed|alert.critical|resource.freed",
  "priority": "P0|P1|P2|P3",
  "payload": { ... },
  "correlation_id": "links back to originating task",
  "ttl_seconds": 3600
}
```

### 1.4 Shared State Store

```
PostgreSQL Schema (shared across all agents):

agent_tasks          — Task queue with status tracking
agent_state          — Per-agent state machines
crawl_results        — URL-level crawl data
content_scores       — On-page audit results
rank_snapshots       — SERP position history
backlink_profiles    — Link data + outreach status
competitor_data      — Competitor intelligence
decision_log         — Decision history with rationale
action_log           — Executed actions with outcomes
api_quota_tracker    — Per-API usage and remaining quota
```

---

## 2. Agent 1: Crawl Agent (Sentinel)

### 2.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      SENTINEL CRAWL AGENT                        │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────────────┐ │
│  │ URL Frontier │  │ Crawler Pool │  │ Analysis Pipeline       │ │
│  │             │  │              │  │                         │ │
│  │ Priority Q  │  │ Google Eng   │  │ Broken Link Detector    │ │
│  │ Dedup       │  │ Bing Engine  │  │ Index Status Checker    │ │
│  │ Politeness  │  │ Yandex Eng   │  │ Sitemap Analyzer        │ │
│  │ rules       │  │ Naver Engine │  │ robots.txt Parser       │ │
│  └──────┬──────┘  └──────┬───────┘  └────────────┬────────────┘ │
│         │                │                        │              │
│         ▼                ▼                        ▼              │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                   State Machine                              ││
│  │  IDLE → CRAWLING → ANALYZING → REPORTING → WAITING → IDLE   ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Class Hierarchy:**

```python
class SentinelAgent(BaseAgent):
    """Crawl Agent — monitors indexability, broken links, sitemaps."""

    components: dict = {
        "url_frontier": URLFrontier,         # Priority queue with dedup
        "crawler_pool": CrawlerPool,         # Multi-engine HTTP clients
        "link_checker": BrokenLinkDetector,   # Link validation
        "index_monitor": IndexStatusMonitor,  # GSC/Bing/Yandex/Naver index checks
        "sitemap_mgr": SitemapManager,       # Sitemap parse/generate/submit
        "robots_parser": RobotsParser,        # robots.txt analysis
        "rate_limiter": DomainRateLimiter,    # Per-domain politeness
        "result_store": CrawlResultStore,     # PostgreSQL persistence
    }

    state_machine: StateMachine = {
        "IDLE":      {"start_crawl": "CRAWLING"},
        "CRAWLING":  {"crawl_complete": "ANALYZING", "crawl_failed": "ERROR"},
        "ANALYZING": {"analysis_complete": "REPORTING"},
        "REPORTING": {"report_sent": "WAITING"},
        "WAITING":   {"interval_elapsed": "IDLE", "priority_override": "CRAWLING"},
        "ERROR":     {"retry": "CRAWLING", "max_retries": "DEAD_LETTER"},
    }
```

### 2.2 Triggers

| Trigger Type | Condition | Priority |
|-------------|-----------|----------|
| **Scheduled** | Full site crawl: configurable interval (default: daily at 02:00 UTC) | P2 |
| **Scheduled** | Incremental crawl: every 6 hours for high-priority URLs | P2 |
| **Event** | New sitemap detected via robots.txt change | P1 |
| **Event** | Sitemap submission requested by Content Agent (new page published) | P1 |
| **Proactive** | 404 rate exceeds 5% threshold → immediate crawl | P0 |
| **Proactive** | GSC crawl errors spike >20% day-over-day | P0 |
| **Proactive** | robots.txt modification detected (hash change) | P1 |

### 2.3 Workflow

#### 2.3.1 Full Site Crawl

```pseudocode
FUNCTION execute_full_crawl(domain):
    # 1. Preparation
    robots = fetch_and_parse_robots(domain)
    rate_config = load_rate_config(domain)  # e.g., {"requests_per_second": 2, "burst": 5}
    sitemap_urls = extract_sitemap_urls(robots)
    known_urls = load_known_urls_from_db(domain)

    # 2. Sitemap Discovery & Merge
    new_sitemap_urls = []
    FOR EACH sitemap_url IN sitemap_urls:
        IF sitemap_url NOT IN known_sitemaps:
            new_sitemap_urls.append(sitemap_url)
            emit_event("sitemap.new_detected", {url: sitemap_url})

    all_urls = merge(known_urls, crawl_sitemaps(sitemap_urls))

    # 3. Prioritized Crawling
    frontier = URLFrontier(all_urls)
    frontier.prioritize_by(
        depth=0,           # Homepage first
        recent_changes,    # URLs with recent GA4 traffic changes
        known_issues,      # URLs with prior crawl errors
    )

    results = []
    WHILE frontier.has_next():
        batch = frontier.next_batch(size=rate_config.burst)
        batch_results = parallel_crawl(batch, engines=["googlebot"], rate=rate_config)
        results.extend(batch_results)

        # Real-time broken link check
        FOR EACH result IN batch_results:
            IF result.status_code >= 400:
                emit_event("issue.broken_link", {
                    url: result.url,
                    status: result.status_code,
                    referrer: result.parent_url,
                    auto_fixable: result.status_code == 404
                })

    # 4. Index Status Cross-Check
    index_statuses = {}
    FOR EACH engine IN ["google", "bing", "yandex", "naver"]:
        index_statuses[engine] = check_index_status(results, engine)

    # 5. Report Generation
    report = CrawlReport(
        total_urls=len(results),
        broken_links=filter(results, lambda r: r.status >= 400),
        not_indexed=filter_by_index_status(index_statuses, "not_indexed"),
        new_urls=filter(results, lambda r: r.url NOT IN known_urls),
        robots_blocked=filter(results, lambda r: r.robots_blocked),
    )

    emit_event("crawl.complete", report.to_dict())
    store_results(report)
    RETURN report
```

#### 2.3.2 Broken Link Auto-Fix

```pseudocode
FUNCTION auto_fix_broken_link(broken_url, referrer_url):
    # Step 1: Attempt to find replacement
    candidates = []

    # Check if URL was redirected (follow redirect chain)
    redirect_target = check_redirect_chain(broken_url)
    IF redirect_target AND is_200(redirect_target):
        candidates.append({"url": redirect_target, "score": 1.0, "method": "redirect"})

    # Search Exa AI for similar content
    exa_results = exa_search(
        query=extract_topic_from_url(broken_url),
        num_results=5,
        use_autoprompt=true
    )
    FOR EACH result IN exa_results:
        IF result.url != broken_url AND is_200(result.url):
            candidates.append({
                "url": result.url,
                "score": result.similarity_score * 0.8,
                "method": "exa_search"
            })

    # Check DataForSEO for pages linking to similar content
    dataforseo_similar = dataforseo_get_similar_pages(broken_url)
    FOR EACH page IN dataforseo_similar:
        candidates.append({
            "url": page.url,
            "score": page.similarity * 0.7,
            "method": "dataforseo_similar"
        })

    # Step 2: Select best candidate
    IF candidates IS EMPTY:
        emit_event("issue.broken_link.no_replacement", {url: broken_url})
        RETURN {"status": "no_fix_found"}

    best = max(candidates, key=lambda c: c.score)

    IF best.score >= 0.6:
        # Auto-fix: emit action for Action Executor
        emit_event("action.fix_broken_link", {
            "broken_url": broken_url,
            "replacement_url": best.url,
            "referrer_url": referrer_url,
            "method": best.method,
            "confidence": best.score,
            "requires_approval": best.score < 0.8
        })
        RETURN {"status": "fix_proposed", "replacement": best.url}
    ELSE:
        emit_event("issue.broken_link.low_confidence", {url: broken_url, best_candidate: best})
        RETURN {"status": "low_confidence", "best": best}
```

### 2.4 Execution Layer

```python
class SentinelExecutionLayer:
    """Exact API calls for Crawl Agent."""

    # --- Google Index Status via GSC API ---
    def check_gsc_index(self, site_url: str, urls: list[str]) -> dict:
        """POST https://searchconsole.googleapis.com/webmasters/v3/sites/{siteUrl}/urlInspection/index:inspect"""
        response = self.gsc_client.post(
            f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/urlInspection/index:inspect",
            headers={"Authorization": f"Bearer {self.gsc_token}"},
            json={
                "inspectionUrl": url,
                "siteUrl": site_url,
            }
        )
        return {
            "verdict": response.json()["inspectionResult"]["indexStatusResult"]["verdict"],
            "coverageState": response.json()["inspectionResult"]["indexStatusResult"]["coverageState"],
            "lastCrawlTime": response.json()["inspectionResult"]["indexStatusResult"].get("lastCrawlTime"),
        }

    # --- Bing Index Status via Bing Webmaster API ---
    def check_bing_index(self, site_url: str, url: str) -> dict:
        """GET https://ssl.bing.com/webmaster/api.svc/json/GetUrlDetails"""
        response = self.bing_client.get(
            "https://ssl.bing.com/webmaster/api.svc/json/GetUrlDetails",
            params={
                "apikey": self.bing_api_key,
                "siteUrl": site_url,
                "url": url,
            }
        )
        data = response.json()
        return {
            "indexed": data.get("d", {}).get("IsIndexed", False),
            "last_crawl": data.get("d", {}).get("LastCrawled"),
        }

    # --- Yandex Index Status ---
    def check_yandex_index(self, host_id: str, url: str) -> dict:
        """GET https://api.webmaster.yandex.net/v4/user/{host_id}/urls/{url_hash}/"""
        url_hash = sha256(url.encode()).hexdigest()
        response = self.yandex_client.get(
            f"https://api.webmaster.yandex.net/v4/user/{self.user_id}/hosts/{host_id}/urls/{url_hash}/",
            headers={"Authorization": f"OAuth {self.yandex_token}"}
        )
        return response.json()

    # --- Naver Index Status ---
    def check_naver_index(self, site_id: str, url: str) -> dict:
        """GET https://searchadvisor.naver.com/api/v1/sites/{siteId}/urls/inspect"""
        response = self.naver_client.get(
            f"https://searchadvisor.naver.com/api/v1/sites/{site_id}/urls/inspect",
            params={"url": url},
            headers={"Authorization": f"Bearer {self.naver_token}"}
        )
        return response.json()

    # --- PageSpeed Insights (for crawl-triggered CWV check) ---
    def check_pagespeed(self, url: str) -> dict:
        """GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed"""
        response = self.pagespeed_client.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params={
                "url": url,
                "strategy": "mobile",
                "category": ["performance", "accessibility", "seo"],
                "key": self.pagespeed_api_key,
            }
        )
        lh = response.json()["lighthouseResult"]
        return {
            "performance_score": lh["categories"]["performance"]["score"] * 100,
            "lcp": lh["audits"]["largest-contentful-paint"]["numericValue"],
            "fid": lh["audits"]["max-potential-fid"]["numericValue"],
            "cls": lh["audits"]["cumulative-layout-shift"]["numericValue"],
        }

    # --- Broken Link Detection (HTTP HEAD/GET) ---
    def check_url_status(self, url: str, timeout: int = 10) -> dict:
        """Direct HTTP check with redirect chain tracking."""
        try:
            resp = httpx.head(url, follow_redirects=True, timeout=timeout, headers={
                "User-Agent": "SEOPlatform-Sentinel/1.0 (+https://platform.com/bot)"
            })
            return {
                "status_code": resp.status_code,
                "final_url": str(resp.url),
                "redirect_chain": [str(r.url) for r in resp.history],
                "content_type": resp.headers.get("content-type"),
            }
        except httpx.TimeoutException:
            return {"status_code": 0, "error": "timeout"}
        except Exception as e:
            return {"status_code": 0, "error": str(e)}
```

### 2.5 Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| CPU | 2 cores per crawl worker | Max 4 parallel workers |
| Memory | 2 GB per worker | URL frontier held in memory for speed |
| Disk | 50 GB | Crawl cache + HTML snapshots |
| Time | Full crawl: ≤4 hours for 100K URLs | Incremental: ≤30 min |
| Network | 100 Mbps dedicated | Rate-limited per domain |
| API Quota | GSC: 200 req/min, Bing: 120 req/min | Tracked in `api_quota_tracker` |

### 2.6 Error Handling

```python
class SentinelErrorHandler:
    retry_policy = {
        "http_429":       {"backoff": "exponential", "base_delay": 60, "max_retries": 5},
        "http_5xx":       {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "timeout":        {"backoff": "linear",      "base_delay": 30, "max_retries": 3},
        "dns_failure":    {"backoff": "none",         "max_retries": 1},
        "rate_limited":   {"backoff": "exponential", "base_delay": 120, "max_retries": 10},
        "auth_expired":   {"action": "refresh_token", "max_retries": 2},
    }

    fallback_strategies = {
        "gsc_unavailable":   "fallback_to_bing_webmaster",
        "all_engines_down":  "cache_serve + alert + retry_later",
        "sitemap_parse_err": "skip_malformed + report + continue",
    }

    dead_letter_queue = {
        "queue_name": "sentinel:dlq",
        "max_size": 10000,
        "ttl_days": 30,
        "alert_threshold": 100,  # Alert when DLQ exceeds 100 items
        "reprocess_schedule": "every_6_hours",
    }
```

### 2.7 Configuration

```yaml
sentinel:
  crawl:
    full_crawl_cron: "0 2 * * *"           # Daily at 02:00 UTC
    incremental_cron: "0 */6 * * *"        # Every 6 hours
    max_concurrent_requests: 20
    request_timeout_seconds: 30
    respect_robots_txt: true
    user_agent: "SEOPlatform-Sentinel/1.0"
    max_depth: 10
    max_urls_per_domain: 500000
    url_pattern_include: ["*"]
    url_pattern_exclude: ["/admin/*", "/api/*", "*.pdf"]

  rate_limiting:
    default_requests_per_second: 2
    default_burst: 5
    per_domain_overrides:
      "example.com": {"rps": 5, "burst": 10}
    backoff_on_429: true

  engines:
    google:
      enabled: true
      api: "gsc"
      check_index: true
    bing:
      enabled: true
      api: "bing_webmaster"
      check_index: true
    yandex:
      enabled: false
      api: "yandex_webmaster"
      host_id: ""
    naver:
      enabled: false
      api: "naver_searchadvisor"
      site_id: ""

  broken_link_detection:
    auto_fix_enabled: true
    auto_fix_confidence_threshold: 0.8
    require_approval_below_threshold: true
    max_auto_fixes_per_run: 50

  sitemap:
    auto_generate: true
    auto_submit: true
    max_urls_per_sitemap: 50000
    include_images: true
    include_lastmod: true
    include_changefreq: true
    include_priority: true
```

### 2.8 Monitoring

```yaml
sentinel_metrics:
  counters:
    - urls_crawled_total
    - broken_links_detected_total
    - broken_links_auto_fixed_total
    - index_checks_performed_total
    - sitemaps_submitted_total
    - robots_txt_changes_detected_total

  gauges:
    - crawl_queue_size
    - active_crawl_workers
    - domain_rate_limit_remaining
    - last_crawl_duration_seconds
    - last_crawl_coverage_percent

  histograms:
    - url_response_time_seconds
    - crawl_depth_distribution
    - http_status_code_distribution

  alerts:
    - name: "high_404_rate"
      condition: "broken_links_detected_total / urls_crawled_total > 0.05"
      severity: "critical"
      notify: ["slack", "email"]
    - name: "crawl_failure_spike"
      condition: "crawl_errors_rate > 0.2 for 1h"
      severity: "warning"
    - name: "gsc_crawl_errors_spike"
      condition: "gsc_crawl_errors_today > gsc_crawl_errors_yesterday * 1.2"
      severity: "critical"
```

---

## 3. Agent 2: Content Agent (Forge)

### 3.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      FORGE CONTENT AGENT                         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────────┐  ┌────────────────────┐ │
│  │ On-Page Audit │  │ Keyword Engine    │  │ Content Pipeline   │ │
│  │              │  │                  │  │                    │ │
│  │ Google Score │  │ Gap Analysis     │  │ Generation         │ │
│  │ AI Score     │  │ Opportunity ID   │  │ Optimization       │ │
│  │ Technical    │  │ Cluster Mapping  │  │ Internal Linking   │ │
│  │ checklist    │  │ Trend Detection  │  │ AEO/GEO Enrichment │ │
│  └──────┬───────┘  └────────┬─────────┘  └────────┬───────────┘ │
│         │                   │                     │              │
│         ▼                   ▼                     ▼              │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                   State Machine                              ││
│  │  IDLE → AUDITING → SCORING → GENERATING → OPTIMIZING →      ││
│  │  REVIEWING → PUBLISHING → IDLE                               ││
│  └──────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

**Class Hierarchy:**

```python
class ForgeAgent(BaseAgent):
    """Content Agent — audits, generates, and optimizes content."""

    components: dict = {
        "on_page_auditor": OnPageAuditor,        # 200+ signal audit
        "google_scorer": GoogleContentScorer,     # E-E-A-T + helpful content
        "ai_readiness_scorer": AIReadinessScorer, # AEO/GEO readiness
        "keyword_engine": KeywordEngine,          # Gap analysis + clustering
        "content_generator": ContentGenerator,    # LLM-powered content creation
        "meta_optimizer": MetaTagOptimizer,       # Title/desc/OG optimization
        "internal_linker": InternalLinkEngine,    # Link graph analysis + recs
        "aeo_optimizer": AEOOptimizer,            # Answer Engine Optimization
        "geo_optimizer": GEOOptimizer,            # Generative Engine Optimization
        "tavily_client": TavilyClient,            # Research extraction
        "exa_client": ExaClient,                  # Semantic search
    }

    state_machine: StateMachine = {
        "IDLE":       {"audit_request": "AUDITING", "generate_request": "GENERATING"},
        "AUDITING":   {"audit_complete": "SCORING"},
        "SCORING":    {"scored": "GENERATING", "no_action_needed": "IDLE"},
        "GENERATING": {"content_ready": "OPTIMIZING"},
        "OPTIMIZING": {"optimized": "REVIEWING"},
        "REVIEWING":  {"approved": "PUBLISHING", "rejected": "GENERATING"},
        "PUBLISHING": {"published": "IDLE"},
    }
```

### 3.2 Dual Scoring System

```python
class DualScorer:
    """Two independent scoring axes for content quality."""

    # Google Score (0-100): Traditional SEO quality signals
    google_signals = {
        "title_optimization":      {"weight": 0.10, "checks": ["length", "keyword_placement", "uniqueness"]},
        "meta_description":        {"weight": 0.08, "checks": ["length", "cta_present", "keyword_included"]},
        "heading_structure":       {"weight": 0.10, "checks": ["h1_unique", "hierarchy", "keyword_in_h1"]},
        "content_depth":           {"weight": 0.15, "checks": ["word_count", "topic_coverage", "subtopic_count"]},
        "keyword_usage":           {"weight": 0.12, "checks": ["density", "placement", "semantic_variants"]},
        "internal_linking":        {"weight": 0.08, "checks": ["count", "relevance", "anchor_text"]},
        "image_optimization":      {"weight": 0.05, "checks": ["alt_text", "compression", "lazy_load"]},
        "eeat_signals":            {"weight": 0.12, "checks": ["author_bio", "citations", "freshness", "credentials"]},
        "url_structure":           {"weight": 0.05, "checks": ["shortness", "keyword", "hyphens"]},
        "mobile_readability":      {"weight": 0.05, "checks": ["font_size", "line_spacing", "paragraph_length"]},
        "schema_markup":           {"weight": 0.05, "checks": ["article_schema", "faq_schema", "breadcrumb"]},
        "page_speed_correlation":  {"weight": 0.05, "checks": ["cwv_pass", "resource_count"]},
    }

    # AI Readiness Score (0-100): AEO/GEO optimization signals
    ai_readiness_signals = {
        "question_answer_format":   {"weight": 0.15, "checks": ["faq_present", "q_in_heading", "direct_answer"]},
        "structured_data":          {"weight": 0.12, "checks": ["schema_completeness", "json_ld_valid"]},
        "entity_clarity":           {"weight": 0.12, "checks": ["named_entities", "unambiguous_references"]},
        "citation_worthiness":      {"weight": 0.10, "checks": ["data_sources", "statistics", "expert_quotes"]},
        "conversational_tone":      {"weight": 0.08, "checks": ["natural_language", "readability_score"]},
        "featured_snippet_ready":   {"weight": 0.12, "checks": ["paragraph_snippet", "list_format", "table_format"]},
        "passage_independence":     {"weight": 0.10, "checks": ["self_contained_paragraphs", "topic_sentences"]},
        "freshness_signals":        {"weight": 0.08, "checks": ["date_present", "recent_data", "update_frequency"]},
        "source_authority":         {"weight": 0.08, "checks": ["external_links_to_authority", "domain_authority"]},
        "ai_crawlability":          {"weight": 0.05, "checks": ["no_js_required", "text_extractable", "clean_html"]},
    }
```

### 3.3 Triggers

| Trigger Type | Condition | Priority |
|-------------|-----------|----------|
| **Scheduled** | Weekly content audit of top 100 pages by traffic | P2 |
| **Event** | Rank drop detected by Scout Agent (position decrease ≥3) | P1 |
| **Event** | New keyword opportunity identified by keyword gap analysis | P2 |
| **Proactive** | Competitor publishes content targeting our keywords | P1 |
| **Proactive** | Content age > 6 months with declining traffic | P2 |
| **Proactive** | Google algorithm update detected → re-audit affected pages | P0 |
| **Event** | Manual request from Decision Engine | P1 |

### 3.4 Workflow

#### 3.4.1 Full On-Page Audit

```pseudocode
FUNCTION audit_page(url, target_keyword):
    # 1. Fetch & Parse
    html = fetch_page(url)
    dom = parse_html(html)
    text_content = extract_text(dom)
    headings = extract_headings(dom)

    # 2. Google Score (Traditional SEO)
    google_checks = {}
    google_checks["title"] = audit_title(dom, target_keyword)
    google_checks["meta_desc"] = audit_meta_description(dom, target_keyword)
    google_checks["headings"] = audit_heading_structure(headings, target_keyword)
    google_checks["content_depth"] = analyze_content_depth(text_content, target_keyword)
    google_checks["keywords"] = analyze_keyword_usage(text_content, target_keyword)
    google_checks["internal_links"] = audit_internal_links(dom, url)
    google_checks["images"] = audit_images(dom)
    google_checks["eeat"] = audit_eeat_signals(dom, url)
    google_checks["url"] = audit_url_structure(url)
    google_checks["schema"] = audit_schema_markup(dom)

    google_score = weighted_sum(google_checks, google_signals)  # 0-100

    # 3. AI Readiness Score (AEO/GEO)
    ai_checks = {}
    ai_checks["qa_format"] = detect_qa_format(text_content, headings)
    ai_checks["structured_data"] = validate_structured_data(dom)
    ai_checks["entities"] = extract_named_entities(text_content)
    ai_checks["citations"] = count_citations_and_sources(dom)
    ai_checks["readability"] = calculate_readability(text_content)
    ai_checks["snippet_ready"] = check_featured_snippet_format(text_content)
    ai_checks["passage_indep"] = score_passage_independence(text_content)
    ai_checks["freshness"] = check_freshness_signals(dom)
    ai_checks["ai_crawlable"] = check_ai_crawlability(html)

    ai_readiness_score = weighted_sum(ai_checks, ai_readiness_signals)  # 0-100

    # 4. Keyword Gap Analysis via Tavily + Exa
    competitor_content = tavily_search(
        query=f"best results for '{target_keyword}'",
        search_depth="advanced",
        include_answer=true,
        max_results=5
    )
    exa_analysis = exa_search(
        query=target_keyword,
        num_results=10,
        contents={"text": {"maxCharacters": 5000}}
    )
    gap_analysis = identify_content_gaps(text_content, competitor_content, exa_analysis)

    # 5. Internal Link Recommendations
    link_graph = load_internal_link_graph()
    internal_recs = recommend_internal_links(
        source_url=url,
        source_content=text_content,
        target_keyword=target_keyword,
        link_graph=link_graph,
        max_recommendations=10
    )

    # 6. AEO/GEO Optimization Recommendations
    aeo_recs = generate_aeo_recommendations(ai_checks, competitor_content)
    geo_recs = generate_geo_recommendations(ai_checks, exa_analysis)

    # 7. Compile Report
    report = ContentAuditReport(
        url=url,
        google_score=google_score,
        ai_readiness_score=ai_readiness_score,
        checks={**google_checks, **ai_checks},
        gap_analysis=gap_analysis,
        internal_link_recs=internal_recs,
        aeo_recommendations=aeo_recs,
        geo_recommendations=geo_recs,
        priority=calculate_priority(google_score, ai_readiness_score, gap_analysis),
    )

    emit_event("content.audit_complete", report.to_dict())
    RETURN report
```

#### 3.4.2 Content Generation Pipeline

```pseudocode
FUNCTION generate_content(target_keyword, content_type, tone, word_count):
    # 1. Research Phase (Tavily + Exa)
    research = tavily_search(
        query=target_keyword,
        search_depth="advanced",
        include_answer=true,
        include_raw_content=true,
        max_results=10
    )
    exa_context = exa_search(
        query=f"comprehensive guide about {target_keyword}",
        num_results=10,
        contents={"text": {"maxCharacters": 3000}}
    )

    # 2. SERP Analysis (via DataForSEO SERP API — delegated to Scout if available, else direct)
    serp_data = dataforseo_serp_search(
        engine="google",
        q=target_keyword,
        num=10,
    )
    serp_features = detect_serp_features(serp_data)  # Featured snippet, PAA, etc.

    # 3. Outline Generation
    outline = llm_generate(
        prompt=CONTENT_OUTLINE_PROMPT,
        context={
            "keyword": target_keyword,
            "serp_analysis": serp_data,
            "competitor_research": research,
            "serp_features": serp_features,
            "content_type": content_type,
        }
    )

    # 4. Content Generation (Section by Section)
    sections = []
    FOR EACH section IN outline.sections:
        section_content = llm_generate(
            prompt=SECTION_GENERATION_PROMPT,
            context={
                "section": section,
                "research": relevant_research_snippets(research, section.topic),
                "tone": tone,
                "target_words": section.word_count,
                "keyword": target_keyword,
            }
        )
        sections.append(section_content)

    # 5. Meta Tag Optimization
    meta = generate_meta_tags(
        title_options=llm_generate(TITLE_PROMPT, keyword=target_keyword, count=5),
        description_options=llm_generate(DESC_PROMPT, keyword=target_keyword, count=5),
        og_tags=generate_og_tags(content_type),
    )

    # 6. AEO/GEO Enrichment
    aeo_enrichment = enrich_for_aeo(sections, serp_features)
    geo_enrichment = enrich_for_geo(sections, exa_context)

    # 7. Internal Link Placement
    internal_links = recommend_internal_links(
        source_content=concatenate(sections),
        target_keyword=target_keyword,
    )
    enriched_sections = insert_internal_links(sections, internal_links)

    # 8. Schema Markup Generation
    schema = generate_schema_markup(
        type="Article",
        data={
            "headline": meta.title,
            "description": meta.description,
            "author": get_author_info(),
            "datePublished": now_iso(),
            "faq": extract_faqs(enriched_sections),
        }
    )

    # 9. Final Assembly
    content_package = ContentPackage(
        title=meta.title,
        meta_description=meta.description,
        sections=enriched_sections,
        schema_markup=schema,
        internal_links=internal_links,
        target_keyword=target_keyword,
        word_count=count_words(enriched_sections),
        google_score_estimate=estimate_google_score(enriched_sections),
        ai_readiness_estimate=estimate_ai_score(enriched_sections, aeo_enrichment),
    )

    emit_event("content.generated", content_package.to_dict())
    RETURN content_package
```

### 3.5 Execution Layer

```python
class ForgeExecutionLayer:
    """Exact API calls for Content Agent."""

    # --- Tavily Research ---
    def tavily_search(self, query: str, **kwargs) -> dict:
        """POST https://api.tavily.com/search"""
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": kwargs.get("search_depth", "basic"),
                "include_answer": kwargs.get("include_answer", True),
                "include_raw_content": kwargs.get("include_raw_content", False),
                "max_results": kwargs.get("max_results", 5),
            },
            timeout=30,
        )
        return response.json()

    def tavily_extract(self, urls: list[str]) -> dict:
        """POST https://api.tavily.com/extract"""
        response = httpx.post(
            "https://api.tavily.com/extract",
            json={
                "api_key": self.tavily_api_key,
                "urls": urls,
            },
            timeout=30,
        )
        return response.json()

    # --- Exa AI Search ---
    def exa_search(self, query: str, **kwargs) -> dict:
        """POST https://api.exa.ai/search"""
        response = httpx.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": self.exa_api_key},
            json={
                "query": query,
                "numResults": kwargs.get("num_results", 10),
                "useAutoprompt": kwargs.get("use_autoprompt", True),
                "contents": kwargs.get("contents", {"text": {"maxCharacters": 3000}}),
            },
            timeout=30,
        )
        return response.json()

    def exa_find_similar(self, url: str, **kwargs) -> dict:
        """POST https://api.exa.ai/findSimilar"""
        response = httpx.post(
            "https://api.exa.ai/findSimilar",
            headers={"x-api-key": self.exa_api_key},
            json={
                "url": url,
                "numResults": kwargs.get("num_results", 10),
                "contents": {"text": {"maxCharacters": 2000}},
            },
            timeout=30,
        )
        return response.json()

    # --- DataForSEO SERP API ---
    def dataforseo_serp_search(self, engine: str, q: str, **kwargs) -> dict:
        """POST https://api.dataforseo.com/v3/serp/{engine}/organic/live/regular"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/serp/" + engine + "/organic/live/regular",
            params={
                "engine": engine,
                "q": q,
                "login": self.dataforseo_login,
                "num": kwargs.get("num", 10),
                "gl": kwargs.get("gl", "us"),
                "hl": kwargs.get("hl", "en"),
            },
            timeout=30,
        )
        return response.json()

    # --- GSC Search Analytics (for content performance) ---
    def gsc_query(self, site_url: str, start_date: str, end_date: str, dimensions: list, **filters) -> dict:
        """POST https://searchconsole.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query"""
        response = self.gsc_client.post(
            f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {self.gsc_token}"},
            json={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": dimensions,
                "dimensionFilterGroups": filters.get("filters", []),
                "rowLimit": filters.get("row_limit", 1000),
            }
        )
        return response.json()

    # --- GA4 API (for traffic data) ---
    def ga4_run_report(self, property_id: str, **params) -> dict:
        """POST https://analyticsdata.googleapis.com/v1beta/properties/{propertyId}:runReport"""
        response = self.ga4_client.post(
            f"https://analyticsdata.googleapis.com/v1beta/properties/{property_id}:runReport",
            headers={"Authorization": f"Bearer {self.ga4_token}"},
            json={
                "dateRanges": params.get("date_ranges", [{"startDate": "30daysAgo", "endDate": "today"}]),
                "dimensions": params.get("dimensions", [{"name": "pagePath"}]),
                "metrics": params.get("metrics", [
                    {"name": "sessions"},
                    {"name": "totalUsers"},
                    {"name": "screenPageViews"},
                    {"name": "bounceRate"},
                    {"name": "averageSessionDuration"},
                ]),
                "limit": params.get("limit", 1000),
            }
        )
        return response.json()
```

### 3.6 Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| CPU | 4 cores | LLM inference offloaded to API |
| Memory | 4 GB | Content analysis buffers |
| Time | Single page audit: ≤2 min, Content generation: ≤10 min | |
| API Quota | Tavily: 1000/day, Exa: 1000/min, DataForSEO: 2000/min | Shared with other agents |
| LLM Tokens | 50K tokens/day for content generation | Configurable budget |

### 3.7 Error Handling

```python
class ForgeErrorHandler:
    retry_policy = {
        "llm_timeout":       {"backoff": "exponential", "base_delay": 5, "max_retries": 3},
        "llm_rate_limited":  {"backoff": "exponential", "base_delay": 60, "max_retries": 5},
        "tavily_error":      {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "exa_error":         {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "dataforseo_error":     {"backoff": "exponential", "base_delay": 30, "max_retries": 3},
        "gsc_quota":         {"backoff": "linear", "base_delay": 60, "max_retries": 3},
    }

    fallback_strategies = {
        "tavily_unavailable":  "fallback_to_exa_only",
        "exa_unavailable":     "fallback_to_tavily_only",
        "both_search_down":    "use_cached_results + alert",
        "llm_unavailable":     "queue_for_retry + use_template_content",
        "gsc_unavailable":     "use_ga4_data_only",
    }

    dead_letter_queue = {
        "queue_name": "forge:dlq",
        "max_size": 5000,
        "ttl_days": 14,
    }
```

### 3.8 Configuration

```yaml
forge:
  audit:
    weekly_audit_cron: "0 3 * * 1"          # Monday 03:00 UTC
    top_pages_count: 100
    min_google_score_threshold: 60
    min_ai_readiness_threshold: 50

  scoring:
    google_signals:
      title_optimization: 0.10
      meta_description: 0.08
      heading_structure: 0.10
      content_depth: 0.15
      keyword_usage: 0.12
      internal_linking: 0.08
      image_optimization: 0.05
      eeat_signals: 0.12
      url_structure: 0.05
      mobile_readability: 0.05
      schema_markup: 0.05
      page_speed_correlation: 0.05

  generation:
    default_word_count: 2000
    max_word_count: 5000
    default_tone: "professional"
    llm_provider: "openai"
    llm_model: "codex"
    max_tokens_per_request: 4096
    daily_token_budget: 50000
    human_review_required: true

  research:
    tavily_search_depth: "advanced"
    tavily_max_results: 10
    exa_num_results: 10
    exa_use_autoprompt: true

  meta_optimization:
    title_max_length: 60
    description_max_length: 155
    generate_variants: 5
    auto_select_best: false  # Require human selection

  aeo_geo:
    enabled: true
    optimize_for_featured_snippets: true
    optimize_for_people_also_ask: true
    optimize_for_ai_overviews: true
    enrich_with_statistics: true
    add_faq_sections: true
```

### 3.9 Monitoring

```yaml
forge_metrics:
  counters:
    - pages_audited_total
    - content_pieces_generated_total
    - meta_tags_optimized_total
    - internal_links_suggested_total
    - aeo_geo_optimizations_applied_total

  gauges:
    - average_google_score
    - average_ai_readiness_score
    - pages_below_threshold_count
    - daily_llm_tokens_used
    - content_generation_queue_size

  histograms:
    - google_score_distribution
    - ai_readiness_score_distribution
    - audit_duration_seconds
    - content_generation_duration_seconds

  alerts:
    - name: "scores_declining"
      condition: "avg_google_score_7d < avg_google_score_30d * 0.9"
      severity: "warning"
    - name: "token_budget_exhausted"
      condition: "daily_llm_tokens_used >= daily_token_budget * 0.9"
      severity: "warning"
```

---

## 4. Agent 3: Technical Agent

### 4.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     TECHNICAL AGENT                              │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ CWV Monitor       │  │ Schema Engine     │  │ Self-Healer    │ │
│  │                  │  │                  │  │                │ │
│  │ LCP/FID/CLS      │  │ JSON-LD Gen      │  │ 8 Issue Types  │ │
│  │ INP/TTFB         │  │ Validation       │  │ Auto-Fix       │ │
│  │ Field + Lab      │  │ Injection        │  │ Rollback       │ │
│  └──────────────────┘  └──────────────────┘  └────────────────┘ │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Tech Validator    │  │ Mobile Checker    │                     │
│  │                  │  │                  │                     │
│  │ Multi-Engine     │  │ Responsive       │                     │
│  │ Canonical/Dup    │  │ Touch Targets    │                     │
│  │ HTTPS/Security   │  │ Viewport         │                     │
│  └──────────────────┘  └──────────────────┘                     │
│                                                                  │
│  State Machine:                                                  │
│  IDLE → MONITORING → DETECTING → HEALING → VALIDATING → IDLE    │
└─────────────────────────────────────────────────────────────────┘
```

**Class Hierarchy:**

```python
class TechnicalAgent(BaseAgent):
    """Technical SEO Agent — monitors CWV, generates schema, self-heals issues."""

    components: dict = {
        "cwv_monitor": CWVMonitor,                # Core Web Vitals tracking
        "schema_engine": SchemaMarkupEngine,       # JSON-LD generation + injection
        "self_healer": SelfHealingEngine,          # Auto-fix 8 issue types
        "tech_validator": MultiEngineValidator,     # Technical SEO checks
        "mobile_checker": MobileFriendlinessChecker,# Mobile optimization
        "pagespeed_client": PageSpeedInsightsClient,# PSI API wrapper
    }

    # 8 Self-Healing Issue Types
    HEALABLE_ISSUES = {
        "missing_title":          {"confidence": 0.95, "auto_fix": True},
        "missing_meta_desc":      {"confidence": 0.90, "auto_fix": True},
        "missing_h1":             {"confidence": 0.85, "auto_fix": True},
        "missing_alt_text":       {"confidence": 0.80, "auto_fix": True},
        "broken_canonical":       {"confidence": 0.90, "auto_fix": True},
        "missing_schema":         {"confidence": 0.85, "auto_fix": True},
        "duplicate_meta":         {"confidence": 0.75, "auto_fix": False},  # Requires content analysis
        "redirect_chain":         {"confidence": 0.95, "auto_fix": True},
    }
```

### 4.2 Triggers

| Trigger Type | Condition | Priority |
|-------------|-----------|----------|
| **Scheduled** | CWV check: every 6 hours for top 200 pages | P2 |
| **Scheduled** | Schema validation: weekly full scan | P2 |
| **Event** | PageSpeed score drops below 50 | P1 |
| **Event** | New page published → immediate schema + tech check | P1 |
| **Proactive** | CLS spike detected (>0.25 for 24h) | P0 |
| **Proactive** | INP regression (>200ms for 7d) | P0 |
| **Proactive** | LCP >4s for top pages | P0 |
| **Proactive** | Mobile usability errors in GSC | P1 |

### 4.3 Workflows

#### 4.3.1 CWV Monitoring

```pseudocode
FUNCTION monitor_core_web_vitals(urls):
    results = []
    FOR EACH url IN urls:
        # Lab data (PageSpeed Insights)
        lab_data = pagespeed_insights_api(
            url=url,
            strategy="mobile",
            categories=["performance"]
        )

        # Field data (CrUX via GA4 or direct)
        field_data = ga4_get_web_vitals(property_id, url)

        # GSC CWV report
        gsc_cwv = gsc_query(
            site_url=site_url,
            dimensions=["page"],
            filters=[{"page": url}],
            metrics=["LCP", "FID", "CLS", "INP", "TTFB"]
        )

        cwv_result = CWVResult(
            url=url,
            lab={
                "lcp": lab_data["lcp_ms"],
                "fid": lab_data["fid_ms"],
                "cls": lab_data["cls"],
                "inp": lab_data.get("inp_ms"),
                "ttfb": lab_data["ttfb_ms"],
                "performance_score": lab_data["score"],
            },
            field={
                "lcp_p75": field_data.get("lcp_p75"),
                "fid_p75": field_data.get("fid_p75"),
                "cls_p75": field_data.get("cls_p75"),
                "inp_p75": field_data.get("inp_p75"),
            },
            status=evaluate_cwv_status(lab_data, field_data),
        )

        IF cwv_result.status IN ["poor", "needs_improvement"]:
            emit_event("technical.cwv_issue", cwv_result.to_dict())

        results.append(cwv_result)

    RETURN results
```

#### 4.3.2 Self-Healing Engine

```pseudocode
FUNCTION self_heal(issue_type, page_data, context):
    """Auto-fix one of 8 technical issue types."""

    CONFIDENCE_THRESHOLD = load_config("technical.self_healing.confidence_threshold", 0.8)
    healable = HEALABLE_ISSUES[issue_type]

    IF healable.confidence < CONFIDENCE_THRESHOLD:
        emit_event("action.requires_approval", {issue: issue_type, page: page_data.url})
        RETURN {"status": "pending_approval"}

    SWITCH issue_type:
        CASE "missing_title":
            # Generate title from H1 + keyword
            title = generate_title(page_data.h1, page_data.target_keyword)
            fix = {"type": "inject_meta", "tag": "title", "value": title}

        CASE "missing_meta_desc":
            desc = generate_meta_description(page_data.content[:500], page_data.target_keyword)
            fix = {"type": "inject_meta", "tag": "meta_description", "value": desc}

        CASE "missing_h1":
            h1 = generate_h1(page_data.title, page_data.target_keyword)
            fix = {"type": "inject_element", "tag": "h1", "value": h1}

        CASE "missing_alt_text":
            FOR EACH image IN page_data.images_without_alt:
                alt = generate_alt_text(image.src, page_data.content)
                fix = {"type": "inject_attribute", "element": image.id, "attr": "alt", "value": alt}

        CASE "broken_canonical":
            correct_url = resolve_canonical(page_data.url, page_data.redirect_chain)
            fix = {"type": "inject_link", "rel": "canonical", "href": correct_url}

        CASE "missing_schema":
            schema = generate_schema_for_page(page_data)
            fix = {"type": "inject_schema", "json_ld": schema}

        CASE "redirect_chain":
            target = page_data.redirect_chain[-1]
            fix = {"type": "update_redirect", "from": page_data.url, "to": target, "status": 301}

        CASE "duplicate_meta":
            # Requires content analysis — not auto-fixed, but recommendation generated
            fix = {"type": "recommendation", "message": "Duplicate meta detected", "details": page_data.duplicates}

    emit_event("action.auto_fix", {
        "issue": issue_type,
        "page": page_data.url,
        "fix": fix,
        "confidence": healable.confidence,
        "auto_applied": healable.auto_fix AND healable.confidence >= CONFIDENCE_THRESHOLD,
    })

    RETURN {"status": "fix_proposed", "fix": fix}
```

#### 4.3.3 Schema Markup Generation

```pseudocode
FUNCTION generate_schema_markup(page_data):
    """Generate comprehensive JSON-LD schema for a page."""

    schemas = []

    # Always: Organization + WebSite
    schemas.append(generate_organization_schema())
    schemas.append(generate_website_schema())

    # Always: BreadcrumbList
    schemas.append(generate_breadcrumb_schema(page_data.url_path))

    # Conditional: Article / BlogPosting
    IF page_data.content_type IN ["article", "blog_post"]:
        article_schema = {
            "@type": "Article",
            "headline": page_data.title,
            "description": page_data.meta_description,
            "author": {"@type": "Person", "name": page_data.author},
            "datePublished": page_data.publish_date,
            "dateModified": page_data.modified_date,
            "image": page_data.featured_image,
            "publisher": {"@id": organization_schema["@id"]},
            "mainEntityOfPage": page_data.url,
        }
        schemas.append(article_schema)

    # Conditional: FAQ
    IF page_data.has_faq:
        faq_schema = {
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq.question,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq.answer,
                    }
                } FOR faq IN page_data.faqs
            ]
        }
        schemas.append(faq_schema)

    # Conditional: HowTo
    IF page_data.has_howto:
        schemas.append(generate_howto_schema(page_data.steps))

    # Conditional: Product / Review
    IF page_data.content_type == "product":
        schemas.append(generate_product_schema(page_data))

    # Merge into @graph
    final_schema = {
        "@context": "https://schema.org",
        "@graph": schemas,
    }

    # Validate
    validation = validate_json_ld(json.dumps(final_schema))
    IF NOT validation.valid:
        log.warning(f"Schema validation failed: {validation.errors}")

    RETURN final_schema
```

### 4.4 Execution Layer

```python
class TechnicalExecutionLayer:
    """Exact API calls for Technical Agent."""

    # --- PageSpeed Insights API ---
    def pagespeed_insights(self, url: str, strategy: str = "mobile") -> dict:
        """GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed"""
        response = httpx.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
            params={
                "url": url,
                "strategy": strategy,
                "category": ["performance", "accessibility", "best-practices", "seo"],
                "key": self.pagespeed_api_key,
            },
            timeout=120,
        )
        data = response.json()
        lh = data["lighthouseResult"]
        audits = lh["audits"]
        return {
            "performance_score": lh["categories"]["performance"]["score"] * 100,
            "lcp_ms": audits["largest-contentful-paint"]["numericValue"],
            "fid_ms": audits["max-potential-fid"]["numericValue"],
            "cls": audits["cumulative-layout-shift"]["numericValue"],
            "inp_ms": audits.get("experimental-interaction-to-next-paint", {}).get("numericValue"),
            "ttfb_ms": audits["server-response-time"]["numericValue"],
            "opportunities": [
                {"id": a["id"], "title": a["title"], "savings": a.get("details", {}).get("overallSavingsMs", 0)}
                for a in audits.values()
                if a.get("score") is not None and a["score"] < 1 and "overallSavingsMs" in a.get("details", {})
            ],
        }

    # --- GSC URL Inspection (for mobile + index status) ---
    def gsc_inspect_url(self, site_url: str, url: str) -> dict:
        """POST https://searchconsole.googleapis.com/webmasters/v3/sites/{siteUrl}/urlInspection/index:inspect"""
        response = self.gsc_client.post(
            f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/urlInspection/index:inspect",
            headers={"Authorization": f"Bearer {self.gsc_token}"},
            json={"inspectionUrl": url, "siteUrl": site_url}
        )
        result = response.json().get("inspectionResult", {})
        return {
            "index_status": result.get("indexStatusResult", {}),
            "mobile_usability": result.get("mobileUsabilityResult", {}),
            "amp_result": result.get("ampResult", {}),
        }

    # --- Schema Validation (Google Rich Results Test) ---
    def validate_schema(self, url: str = None, html: str = None) -> dict:
        """Uses schema.org validator or Google Rich Results Test."""
        if url:
            response = httpx.get(
                "https://search.google.com/test/rich-results",
                params={"url": url},
                timeout=30,
            )
        # Fallback: local validation against schema.org context
        return self._local_json_ld_validate(html)

    # --- Bing Webmaster: Crawl Issues ---
    def bing_crawl_issues(self, site_url: str) -> dict:
        """GET https://ssl.bing.com/webmaster/api.svc/json/GetCrawlIssues"""
        response = httpx.get(
            "https://ssl.bing.com/webmaster/api.svc/json/GetCrawlIssues",
            params={
                "apikey": self.bing_api_key,
                "siteUrl": site_url,
                "issueType": "all",
            },
            timeout=30,
        )
        return response.json()
```

### 4.5 Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| CPU | 2 cores | Heavy lifting is API-side (PSI) |
| Memory | 2 GB | Schema validation buffers |
| Time | CWV check per page: ≤2 min (PSI timeout) | Full scan 200 pages: ≤3 hours |
| API Quota | PageSpeed Insights: 60 req/min | GSC shared with Sentinel |

### 4.6 Error Handling

```python
class TechnicalErrorHandler:
    retry_policy = {
        "pagespeed_timeout":   {"backoff": "exponential", "base_delay": 30, "max_retries": 3},
        "pagespeed_500":       {"backoff": "exponential", "base_delay": 60, "max_retries": 2},
        "gsc_quota":           {"backoff": "linear", "base_delay": 60, "max_retries": 5},
        "schema_gen_error":    {"backoff": "none", "max_retries": 1},  # Fallback to generic schema
    }

    fallback_strategies = {
        "pagespeed_unavailable":   "use_lighthouse_cli_locally",
        "gsc_unavailable":         "skip_mobile_check + flag_for_later",
        "schema_gen_fails":        "use_generic_article_schema",
    }
```

### 4.7 Configuration

```yaml
technical:
  cwv:
    check_cron: "0 */6 * * *"               # Every 6 hours
    top_pages_count: 200
    strategy: "mobile"                        # mobile | desktop
    lcp_threshold_ms: 2500
    fid_threshold_ms: 100
    cls_threshold: 0.1
    inp_threshold_ms: 200
    ttfb_threshold_ms: 800

  schema:
    auto_generate: true
    auto_inject: false                        # Requires approval by default
    types_enabled: ["Article", "FAQPage", "HowTo", "Product", "Organization", "WebSite", "BreadcrumbList"]
    validate_before_inject: true

  self_healing:
    enabled: true
    confidence_threshold: 0.8
    auto_apply_threshold: 0.9
    require_approval_below: true
    max_fixes_per_run: 100
    rollback_on_error: true
    issue_types:
      missing_title: {enabled: true, auto_fix: true}
      missing_meta_desc: {enabled: true, auto_fix: true}
      missing_h1: {enabled: true, auto_fix: true}
      missing_alt_text: {enabled: true, auto_fix: true}
      broken_canonical: {enabled: true, auto_fix: true}
      missing_schema: {enabled: true, auto_fix: true}
      duplicate_meta: {enabled: true, auto_fix: false}
      redirect_chain: {enabled: true, auto_fix: true}

  mobile:
    check_enabled: true
    viewport_required: true
    min_touch_target_px: 48
    min_font_size_px: 16
```

### 4.8 Monitoring

```yaml
technical_metrics:
  counters:
    - cwv_checks_total
    - schema_generated_total
    - schema_injected_total
    - self_healing_fixes_applied_total
    - self_healing_fixes_rolled_back_total
    - mobile_issues_detected_total

  gauges:
    - pages_with_good_cwv_percent
    - pages_with_schema_percent
    - average_performance_score
    - self_healing_success_rate

  histograms:
    - lcp_distribution_ms
    - cls_distribution
    - inp_distribution_ms
    - performance_score_distribution

  alerts:
    - name: "cwv_regression"
      condition: "pages_with_good_cwv_percent < 75"
      severity: "critical"
    - name: "cls_spike"
      condition: "avg_cls_24h > 0.25"
      severity: "critical"
    - name: "self_healing_failure_rate"
      condition: "self_healing_failures_24h > 10"
      severity: "warning"
```

---

## 5. Agent 4: Rank Agent (Scout)

### 5.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       SCOUT RANK AGENT                           │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ SERP Tracker      │  │ Feature Detector  │  │ Position Alert │ │
│  │                  │  │                  │  │                │ │
│  │ Google           │  │ Featured Snippet  │  │ Threshold      │ │
│  │ Bing             │  │ PAA              │  │ Velocity       │ │
│  │ Yandex           │  │ Local Pack       │  │ Trend          │ │
│  │ Naver            │  │ Knowledge Panel  │  │ Competitor     │ │
│  └──────────────────┘  └──────────────────┘  └────────────────┘ │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Competitor Rank   │  │ Local SERP       │                     │
│  │ Comparison        │  │ Tracker          │                     │
│  └──────────────────┘  └──────────────────┘                     │
│                                                                  │
│  State Machine:                                                  │
│  IDLE → TRACKING → ANALYZING → ALERTING → IDLE                  │
└─────────────────────────────────────────────────────────────────┘
```

**Class Hierarchy:**

```python
class ScoutAgent(BaseAgent):
    """Rank Agent — tracks SERP positions across multiple engines."""

    components: dict = {
        "serp_tracker": MultiEngineSERPTracker,     # Google/Bing/Yandex/Naver
        "feature_detector": SERPFeatureDetector,     # Snippets, PAA, etc.
        "position_alerter": PositionChangeAlerter,   # Threshold-based alerts
        "competitor_comparator": CompetitorRankComparator,
        "local_tracker": LocalSERPTracker,           # Geo-specific rankings
        "rank_store": RankSnapshotStore,              # Historical position data
        "dataforseo_client": DataForSEOClient,              # Primary SERP data source
    }
```

### 5.2 Triggers

| Trigger Type | Condition | Priority |
|-------------|-----------|----------|
| **Scheduled** | Daily rank check: all tracked keywords | P2 |
| **Scheduled** | Local rank check: geo-specific keywords (weekly) | P2 |
| **Event** | New keyword added to tracking list | P2 |
| **Proactive** | Position drop ≥3 for any keyword (immediate alert) | P0 |
| **Proactive** | Position gain ≥5 for any keyword (opportunity alert) | P1 |
| **Proactive** | Competitor overtakes us for tracked keyword | P1 |
| **Proactive** | SERP feature change (we lost/gained featured snippet) | P1 |

### 5.3 Workflow

```pseudocode
FUNCTION track_rankings(keyword_batch, engines, location=None):
    """Track SERP positions for a batch of keywords across engines."""

    results = []

    FOR EACH keyword IN keyword_batch:
        engine_results = {}

        FOR EACH engine IN engines:
            # DataForSEO SERP API call per engine
            serp_data = dataforseo_serp_search(
                engine=engine,  # "google", "bing", "yandex", "naver"
                q=keyword,
                gl=location or "us",
                hl="en",
                num=100,
            )

            # Find our position
            our_position = find_our_position(serp_data, our_domain)
            our_url = our_position.url if our_position else null

            # Detect SERP features
            features = detect_serp_features(serp_data, engine)

            # Find competitor positions
            competitor_positions = find_competitor_positions(serp_data, competitor_domains)

            engine_results[engine] = {
                "position": our_position.rank if our_position else null,
                "url": our_url,
                "features": features,
                "competitor_positions": competitor_positions,
                "serp_snapshot": serp_data,  # Full snapshot for historical
            }

        # Compare with previous snapshot
        previous = load_previous_rank(keyword, date=yesterday)
        delta = calculate_delta(engine_results, previous)

        # Alert evaluation
        IF delta.max_drop >= 3:
            emit_event("alert.rank_drop", {
                "keyword": keyword,
                "drop": delta.max_drop,
                "from": delta.previous_best,
                "to": delta.current_best,
                "engine": delta.engine,
                "priority": "P0",
            })

        IF delta.max_gain >= 5:
            emit_event("alert.rank_gain", {
                "keyword": keyword,
                "gain": delta.max_gain,
                "from": delta.previous_worst,
                "to": delta.current_best,
                "priority": "P1",
            })

        # Store snapshot
        store_rank_snapshot(keyword, engine_results, delta)

        results.append(RankResult(keyword=keyword, engines=engine_results, delta=delta))

    RETURN results
```

### 5.4 Execution Layer

```python
class ScoutExecutionLayer:
    """Exact API calls for Rank Agent."""

    # --- DataForSEO: Google SERP ---
    def google_serp(self, keyword: str, location: str = "us", num: int = 100) -> dict:
        """POST https://api.dataforseo.com/v3/serp/google/organic/live/regular"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/serp/google/organic/live/regular",
            params={
                "engine": "google",
                "q": keyword,
                "login": self.dataforseo_login,
                "num": num,
                "gl": location,
                "hl": "en",
            },
            timeout=30,
        )
        return response.json()

    # --- DataForSEO: Bing SERP ---
    def bing_serp(self, keyword: str, location: str = "us") -> dict:
        """POST https://api.dataforseo.com/v3/serp/bing/organic/live/regular"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/serp/bing/organic/live/regular",
            params={
                "engine": "bing",
                "q": keyword,
                "login": self.dataforseo_login,
                "cc": location,
            },
            timeout=30,
        )
        return response.json()

    # --- DataForSEO: Yandex SERP ---
    def yandex_serp(self, keyword: str) -> dict:
        """POST https://api.dataforseo.com/v3/serp/yandex/organic/live/regular"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/serp/" + engine + "/organic/live/regular",
            params={
                "engine": "yandex",
                "text": keyword,
                "login": self.dataforseo_login,
            },
            timeout=30,
        )
        return response.json()

    # --- DataForSEO: Naver SERP ---
    def naver_serp(self, keyword: str) -> dict:
        """POST https://api.dataforseo.com/v3/serp/naver/organic/live/regular"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/serp/" + engine + "/organic/live/regular",
            params={
                "engine": "naver",
                "query": keyword,
                "login": self.dataforseo_login,
            },
            timeout=30,
        )
        return response.json()

    # --- GSC Search Analytics (supplementary, real click data) ---
    def gsc_impressions_clicks(self, site_url: str, query: str, days: int = 28) -> dict:
        """POST https://searchconsole.googleapis.com/webmasters/v3/sites/{siteUrl}/searchAnalytics/query"""
        end = date.today()
        start = end - timedelta(days=days)
        response = self.gsc_client.post(
            f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(site_url, safe='')}/searchAnalytics/query",
            headers={"Authorization": f"Bearer {self.gsc_token}"},
            json={
                "startDate": start.isoformat(),
                "endDate": end.isoformat(),
                "dimensions": ["query", "date"],
                "dimensionFilterGroups": [{
                    "filters": [{"dimension": "query", "expression": query}]
                }],
                "rowLimit": days,
            }
        )
        return response.json()

    # --- Local SERP Tracking ---
    def local_serp(self, keyword: str, location: str, engine: str = "google") -> dict:
        """DataForSEO with location parameter for local pack tracking."""
        response = httpx.get(
            "https://api.dataforseo.com/v3/serp/" + engine + "/organic/live/regular",
            params={
                "engine": engine,
                "q": keyword,
                "login": self.dataforseo_login,
                "location": location,  # e.g., "Austin, Texas, United States"
                "gl": "us",
                "hl": "en",
            },
            timeout=30,
        )
        return response.json()
```

### 5.5 Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| CPU | 2 cores | Parsing is lightweight |
| Memory | 1 GB | SERP snapshots in memory |
| Time | 1 keyword × 1 engine: ≤5s, 1000 keywords × 4 engines: ≤3 hours | |
| API Quota | DataForSEO: 2000 req/min | Budget across all engines |

### 5.6 Error Handling

```python
class ScoutErrorHandler:
    retry_policy = {
        "dataforseo_rate_limit":   {"backoff": "exponential", "base_delay": 60, "max_retries": 5},
        "dataforseo_error":        {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "gsc_quota":            {"backoff": "linear", "base_delay": 60, "max_retries": 3},
        "parse_error":          {"backoff": "none", "max_retries": 1},
    }

    fallback_strategies = {
        "dataforseo_unavailable":   "use_cached_ranks + delay_tracking",
        "engine_unavailable":    "skip_engine + track_remaining",
        "parse_failure":         "store_raw_response + retry_parse_later",
    }

    dead_letter_queue = {"queue_name": "scout:dlq", "max_size": 5000, "ttl_days": 14}
```

### 5.7 Configuration

```yaml
scout:
  tracking:
    daily_check_cron: "0 5 * * *"            # Daily at 05:00 UTC
    local_check_cron: "0 6 * * 1"            # Monday 06:00 UTC
    max_keywords: 10000
    engines: ["google", "bing"]
    default_location: "us"
    results_per_keyword: 100

  alerts:
    rank_drop_threshold: 3
    rank_gain_threshold: 5
    velocity_window_hours: 24
    competitor_overtake_alert: true

  serp_features:
    track_featured_snippet: true
    track_people_also_ask: true
    track_local_pack: true
    track_knowledge_panel: true
    track_image_pack: true
    track_video_carousel: true

  local_tracking:
    locations:
      - "New York, NY"
      - "Los Angeles, CA"
      - "Chicago, IL"
    radius_miles: 25

  api_budget:
    dataforseo_monthly_limit: 5000
    dataforseo_reserve_for_alerts: 500  # Reserve for alert-triggered checks
    engine_distribution:
      google: 0.60
      bing: 0.25
      yandex: 0.10
      naver: 0.05
```

### 5.8 Monitoring

```yaml
scout_metrics:
  counters:
    - keywords_tracked_total
    - serp_checks_performed_total
    - rank_drops_detected_total
    - rank_gains_detected_total
    - serp_feature_changes_total

  gauges:
    - average_position
    - keywords_in_top10_percent
    - keywords_in_top3_percent
    - dataforseo_quota_remaining_monthly

  alerts:
    - name: "dataforseo_quota_low"
      condition: "dataforseo_quota_remaining_monthly < 500"
      severity: "warning"
    - name: "massive_rank_drop"
      condition: "rank_drops_detected_24h > 50"
      severity: "critical"
```

---

## 6. Agent 5: Backlink & Outreach Agent

> **THE DIFFERENTIATOR** — This agent is the primary competitive advantage. It handles the full E2E outreach lifecycle: discovery, outreach, follow-up, verification, and tracking.

### 6.1 Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                  BACKLINK & OUTREACH AGENT                                   │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     CAMPAIGN TYPES                                      ││
│  │                                                                         ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ ││
│  │  │ HARO Response│  │ Broken Link  │  │ Guest Post   │  │ Unlinked   │ ││
│  │  │ Generator    │  │ Builder      │  │ Outreach     │  │ Mentions   │ ││
│  │  │              │  │              │  │              │  │            │ ││
│  │  │ Query Monitor│  │ Dead Link    │  │ Prospect     │  │ Mention    │ ││
│  │  │ Response Gen │  │ Finder       │  │ Discovery    │  │ Scanner    │ ││
│  │  │ Pitch Sender │  │ Content Match│  │ Pitch Writer │  │ Outreach   │ ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │                     SHARED COMPONENTS                                    ││
│  │                                                                         ││
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐ ││
│  │  │ Campaign      │  │ Gmail Client │  │ Follow-up    │  │ Link       │ ││
│  │  │ Tracker       │  │ (Send/Track) │  │ Engine       │  │ Verifier   │ ││
│  │  │              │  │              │  │              │  │            │ ││
│  │  │ 6 States:    │  │ OAuth2       │  │ Sequences    │  │ HTTP check │ ││
│  │  │ prospecting  │  │ Templates    │  │ Scheduling   │  │DataForSEO  │ ││
│  │  │ outreach_sent│  │ Tracking     │  │ Escalation   │  │ Verification││
│  │  │ follow_up_1  │  │ Webhooks     │  │ Limits       │  │            │ ││
│  │  │ follow_up_2  │  │              │  │              │  │            │ ││
│  │  │ negotiating  │  │              │  │              │  │            │ ││
│  │  │ acquired     │  │              │  │              │  │            │ ││
│  │  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  State Machine (per campaign):                                               │
│  PROSPECTING → OUTREACH_SENT → FOLLOW_UP_1 → FOLLOW_UP_2 →                  │
│  NEGOTIATING → ACQUIRED (or DEAD at any point)                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Campaign Status State Machine:**

```
                    ┌─────────────┐
                    │ PROSPECTING │ ← Initial discovery phase
                    └──────┬──────┘
                           │ pitch sent
                           ▼
                    ┌──────────────┐
              ┌─────│ OUTREACH_SENT│
              │     └──────┬───────┘
              │            │ no reply after 3 days
              │            ▼
              │     ┌──────────────┐
              │ ┌───│ FOLLOW_UP_1  │
              │ │   └──────┬───────┘
              │ │          │ no reply after 5 days
              │ │          ▼
              │ │   ┌──────────────┐
              │ │ ┌─│ FOLLOW_UP_2  │
              │ │ │ └──────┬───────┘
              │ │ │        │ reply received
              │ │ │        ▼
              │ │ │ ┌──────────────┐
              │ │ │ │ NEGOTIATING  │
              │ │ │ └──────┬───────┘
              │ │ │        │ link placed
              │ │ │        ▼
              │ │ │ ┌──────────────┐
              │ │ │ │  ACQUIRED    │ ← Success state
              │ │ │ └──────────────┘
              │ │ │
              ▼ ▼ ▼
        ┌──────────────┐
        │     DEAD     │ ← Terminal failure (any state)
        └──────────────┘
```

**Class Hierarchy:**

```python
class OutreachAgent(BaseAgent):
    """Backlink & Outreach Agent — the competitive differentiator."""

    components: dict = {
        # Campaign Types
        "haro_generator": HAROResponseGenerator,
        "broken_link_builder": BrokenLinkBuilder,
        "guest_post_outreach": GuestPostOutreach,
        "unlinked_mention_monitor": UnlinkedMentionMonitor,

        # Shared Components
        "campaign_tracker": CampaignTracker,       # 6-state machine per campaign
        "gmail_client": GmailAPIClient,            # Send, track, webhooks
        "followup_engine": FollowUpEngine,         # Automated sequences
        "link_verifier": LinkVerifier,             # Check if backlink is live
        "email_template_engine": EmailTemplateEngine,
        "prospect_enricher": ProspectEnricher,     # Contact discovery via Exa/Tavily

        # External APIs
        "exa_client": ExaClient,
        "tavily_client": TavilyClient,
        "dataforseo_client": DataForSEOClient,
    }

    # Campaign Status States
    CAMPAIGN_STATES = [
        "prospecting",      # Finding and qualifying prospects
        "outreach_sent",    # Initial pitch email sent
        "follow_up_1",      # First follow-up sent (3-5 days after initial)
        "follow_up_2",      # Second follow-up sent (5-7 days after follow_up_1)
        "negotiating",      # Active conversation / negotiation
        "acquired",         # Link successfully placed and verified
        "dead",             # Campaign failed (no response, rejected, etc.)
    ]
```

### 6.2 HARO Response Generator (Full E2E)

```pseudocode
FUNCTION haro_pipeline():
    """End-to-end HARO query monitoring and response generation."""

    # STEP 1: Monitor HARO Queries
    haro_queries = fetch_haro_emails()  # Via Gmail API webhook or polling
    relevant_queries = []

    FOR EACH query IN haro_queries:
        relevance = score_relevance(
            query=query,
            our_expertise=load_expert_profiles(),
            min_relevance=0.6
        )
        IF relevance >= 0.6:
            relevant_queries.append({query, relevance})

    # STEP 2: Research Context for Each Query
    FOR EACH item IN relevant_queries:
        # Research via Tavily
        research = tavily_search(
            query=item.query.summary,
            search_depth="advanced",
            include_answer=true,
            max_results=5
        )

        # Find supporting data via Exa
        supporting = exa_search(
            query=f"data statistics about {item.query.topic}",
            num_results=5,
            contents={"text": {"maxCharacters": 2000}}
        )

        item.research = research
        item.supporting_data = supporting

    # STEP 3: Generate Responses
    FOR EACH item IN relevant_queries:
        response_text = llm_generate(
            prompt=HARO_RESPONSE_PROMPT,
            context={
                "query": item.query,
                "expert_profile": best_matching_expert(item.query, our_expertise),
                "research": item.research,
                "supporting_data": item.supporting_data,
                "max_words": 300,
            }
        )

        # Add credentials and authority signals
        enriched_response = add_expert_credentials(response_text, item.expert)

        item.response = enriched_response

    # STEP 4: Send Responses via Gmail
    FOR EACH item IN relevant_queries:
        IF item.query.deadline > now():
            email_result = gmail_send(
                to=item.query.journalist_email,
                subject=f"Re: {item.query.subject}",
                body=item.response,
                from_name=item.expert.name,
                reply_to=item.expert.email,
            )

            # Track campaign
            campaign = create_campaign(
                type="haro",
                prospect=item.query.journalist,
                query=item.query,
                status="outreach_sent",
                email_id=email_result.message_id,
            )

    # STEP 5: Follow-up Monitoring
    monitor_haro_outcomes(campaign_ids)

    RETURN {"queries_found": len(haro_queries), "responses_sent": len(sent_items)}
```

### 6.3 Broken Link Building (Full E2E)

```pseudocode
FUNCTION broken_link_building_pipeline(niche_keywords, target_domains=None):
    """Find broken links on authority sites, create replacement content, reach out."""

    # STEP 1: Find Broken Links on Target Domains
    broken_links = []

    IF target_domains:
        domains = target_domains
    ELSE:
        # Discover authority domains in niche via Exa
        authority_results = exa_search(
            query=f"top authority sites for {niche_keywords[0]}",
            num_results=20,
        )
        domains = [r.url for r in authority_results]

    FOR EACH domain IN domains:
        # Use DataForSEO to find broken outbound links
        dataforseo_broken = dataforseo_get_broken_links(
            target=domain,
            mode="subdomains",
        )

        # Also crawl resource pages for broken links
        resource_pages = find_resource_pages(domain, niche_keywords)
        FOR EACH page IN resource_pages:
            page_broken = crawl_and_check_links(page.url)
            broken_links.extend(page_broken)

        broken_links.extend(dataforseo_broken)

    # STEP 2: Filter for Linkable Opportunities
    opportunities = []
    FOR EACH link IN broken_links:
        # Check if we have or can create matching content
        existing_content = find_matching_content(link.original_url, our_domain)

        IF existing_content:
            opportunities.append({
                "broken_link": link,
                "replacement_url": existing_content.url,
                "method": "existing_content",
                "score": 0.9,
            })
        ELSE:
            # Check if topic is worth creating content for
            topic_value = evaluate_topic_value(link.original_topic, niche_keywords)
            IF topic_value >= 0.7:
                opportunities.append({
                    "broken_link": link,
                    "replacement_url": None,  # Will create
                    "method": "create_content",
                    "score": topic_value * 0.8,
                })

    # STEP 3: Create Replacement Content (if needed)
    FOR EACH opp IN opportunities WHERE opp.method == "create_content":
        content = generate_content(
            target_keyword=opp.broken_link.original_topic,
            content_type="resource_page",
            word_count=2000,
        )
        published_url = publish_content(content)
        opp.replacement_url = published_url

    # STEP 4: Find Contact Information
    FOR EACH opp IN opportunities:
        opp.contact = find_contact(opp.broken_link.domain)  # Via Exa, Tavily, Hunter.io

    # STEP 5: Outreach
    FOR EACH opp IN opportunities WHERE opp.contact:
        email_body = template_render("broken_link_outreach", {
            "recipient_name": opp.contact.name,
            "broken_url": opp.broken_link.url,
            "page_url": opp.broken_link.found_on,
            "replacement_url": opp.replacement_url,
            "replacement_title": get_page_title(opp.replacement_url),
        })

        gmail_result = gmail_send(
            to=opp.contact.email,
            subject=f"Broken link on {opp.broken_link.found_on}",
            body=email_body,
        )

        create_campaign(
            type="broken_link",
            prospect=opp.contact,
            broken_link=opp.broken_link,
            replacement_url=opp.replacement_url,
            status="outreach_sent",
            email_id=gmail_result.message_id,
        )

    RETURN {"opportunities_found": len(opportunities), "outreach_sent": len(sent)}
```

### 6.4 Guest Post Outreach (Full E2E)

```pseudocode
FUNCTION guest_post_outreach_pipeline(niche, target_count=50):
    """Discover guest post opportunities, pitch, and track."""

    # STEP 1: Discover Guest Post Targets
    targets = []

    # Search for "write for us" / "guest post" pages
    search_queries = [
        f"{niche} \"write for us\"",
        f"{niche} \"guest post\"",
        f"{niche} \"contribute\"",
        f"{niche} \"submit an article\"",
    ]

    FOR EACH query IN search_queries:
        exa_results = exa_search(query=query, num_results=20)
        tavily_results = tavily_search(query=query, max_results=10)

        FOR EACH result IN merge(exa_results, tavily_results):
            # Verify it's actually a guest post page
            is_gp_page = verify_guest_post_page(result.url)
            IF is_gp_page:
                domain_dr = dataforseo_get_domain_rank(extract_domain(result.url))
                targets.append({
                    "url": result.url,
                    "domain": extract_domain(result.url),
                    "domain_rating": domain_dr,
                    "guidelines": extract_guidelines(result.content),
                })

    # Sort by DR, take top targets
    targets.sort(key=lambda t: t["domain_rating"], reverse=True)
    targets = targets[:target_count]

    # STEP 2: Generate Pitch Ideas for Each Target
    FOR EACH target IN targets:
        # Analyze their existing content
        existing_content = exa_search(
            query=f"site:{target.domain} {niche}",
            num_results=10,
        )

        # Find content gaps
        gaps = identify_content_gaps(existing_content, our_content)

        # Generate unique pitch ideas
        target.pitch_ideas = generate_pitch_ideas(
            niche=niche,
            guidelines=target.guidelines,
            content_gaps=gaps,
            count=3,
        )

    # STEP 3: Find Contacts
    FOR EACH target IN targets:
        target.contact = find_editor_contact(target.domain)

    # STEP 4: Send Pitches
    FOR EACH target IN targets WHERE target.contact:
        email_body = template_render("guest_post_pitch", {
            "editor_name": target.contact.name,
            "site_name": target.domain,
            "pitch_ideas": target.pitch_ideas[:2],  # Top 2 ideas
            "our_credentials": load_our_credentials(),
            "sample_links": get_our_best_content(n=3),
        })

        gmail_result = gmail_send(
            to=target.contact.email,
            subject=f"Guest post pitch for {target.domain}",
            body=email_body,
        )

        create_campaign(
            type="guest_post",
            prospect=target.contact,
            target_site=target,
            status="outreach_sent",
            email_id=gmail_result.message_id,
        )

    RETURN {"targets_found": len(targets), "pitches_sent": len(sent)}
```

### 6.5 Unlinked Mention Monitor (Full E2E)

```pseudocode
FUNCTION unlinked_mention_pipeline():
    """Find brand mentions without links and convert them to backlinks."""

    # STEP 1: Find Unlinked Mentions
    brand_variants = load_brand_variants()  # ["BrandName", "Brand Name", "@brandhandle"]
    unlinked = []

    FOR EACH variant IN brand_variants:
        # Exa search for mentions
        mentions = exa_search(
            query=f'"{variant}"',
            num_results=50,
            contents={"text": {"maxCharacters": 1000}},
        )

        FOR EACH mention IN mentions:
            # Check if it already links to us
            page_content = tavily_extract([mention.url])
            has_link = check_contains_link(page_content, our_domain)

            IF NOT has_link:
                # Verify it's actually about us (not a different brand with same name)
                is_our_mention = verify_mention_context(mention.text, variant)
                IF is_our_mention:
                    unlinked.append({
                        "url": mention.url,
                        "domain": extract_domain(mention.url),
                        "mention_text": mention.text,
                        "context": mention.context,
                        "domain_rank": dataforseo_get_domain_rank(extract_domain(mention.url)),
                    })

    # Sort by DR
    unlinked.sort(key=lambda u: u["domain_rating"], reverse=True)

    # STEP 2: Find Contact + Outreach
    FOR EACH mention IN unlinked:
        contact = find_contact(mention.domain)

        IF contact:
            email_body = template_render("unlinked_mention", {
                "author_name": contact.name,
                "mention_url": mention.url,
                "mention_text": mention.mention_text,
                "suggested_anchor": our_preferred_anchor_text,
                "target_url": our_most_relevant_page(mention.context),
            })

            gmail_result = gmail_send(
                to=contact.email,
                subject=f"Thanks for mentioning {our_brand_name}!",
                body=email_body,
            )

            create_campaign(
                type="unlinked_mention",
                prospect=contact,
                mention=mention,
                status="outreach_sent",
                email_id=gmail_result.message_id,
            )

    RETURN {"unlinked_found": len(unlinked), "outreach_sent": len(sent)}
```

### 6.6 Follow-Up Automation

```pseudocode
FUNCTION follow_up_engine():
    """Process all campaigns needing follow-up."""

    # Load campaigns in follow-up states
    campaigns_needing_followup = query_db("""
        SELECT * FROM campaigns
        WHERE status IN ('outreach_sent', 'follow_up_1', 'follow_up_2')
          AND next_followup_at <= NOW()
          AND is_active = true
    """)

    FOR EACH campaign IN campaigns_needing_followup:
        # Check for replies first
        replies = gmail_check_for_replies(
            thread_id=campaign.email_thread_id,
            since=campaign.last_email_sent_at,
        )

        IF replies:
            # Reply received — move to negotiating
            campaign.status = "negotiating"
            campaign.last_reply_at = now()
            emit_event("outreach.reply_received", campaign.to_dict())

            # Auto-respond if possible
            IF is_positive_reply(replies.latest):
                auto_reply = generate_positive_reply(replies.latest, campaign)
                gmail_send_reply(thread_id=campaign.email_thread_id, body=auto_reply)

            CONTINUE

        # No reply — send follow-up
        SWITCH campaign.status:
            CASE "outreach_sent":
                IF days_since(campaign.sent_at) >= 3:
                    followup_body = template_render("followup_1", {
                        "original_subject": campaign.subject,
                        "original_snippet": campaign.body[:200],
                        "days_since": days_since(campaign.sent_at),
                    })
                    gmail_send_reply(thread_id=campaign.email_thread_id, body=followup_body)
                    campaign.status = "follow_up_1"
                    campaign.next_followup_at = now() + timedelta(days=5)

            CASE "follow_up_1":
                IF days_since(campaign.last_email_sent_at) >= 5:
                    followup_body = template_render("followup_2", {
                        "original_subject": campaign.subject,
                        "value_add": generate_value_add(campaign),
                    })
                    gmail_send_reply(thread_id=campaign.email_thread_id, body=followup_body)
                    campaign.status = "follow_up_2"
                    campaign.next_followup_at = now() + timedelta(days=7)

            CASE "follow_up_2":
                IF days_since(campaign.last_email_sent_at) >= 7:
                    # Final follow-up or mark dead
                    IF campaign.prospect_value >= HIGH_VALUE_THRESHOLD:
                        followup_body = template_render("followup_final", {
                            "breakup_message": True,
                        })
                        gmail_send_reply(thread_id=campaign.email_thread_id, body=followup_body)

                    campaign.status = "dead"
                    campaign.death_reason = "no_response_after_followups"

        update_campaign(campaign)
```

### 6.7 Link Verification

```pseudocode
FUNCTION verify_link_placement(campaign):
    """Verify that an acquired backlink is actually live and correct."""

    target_url = campaign.target_url         # The page that should link to us
    expected_target = campaign.our_page_url  # Our page that should be linked

    # Method 1: Direct HTTP check
    page_content = httpx.get(target_url, timeout=15).text
    link_found = extract_link_to_domain(page_content, our_domain)

    IF link_found:
        verification = {
            "status": "live",
            "anchor_text": link_found.anchor,
            "target_url": link_found.href,
            "is_nofollow": link_found.rel and "nofollow" in link_found.rel,
            "is_sponsored": link_found.rel and "sponsored" in link_found.rel,
            "is_correct_page": link_found.href == expected_target,
        }
    ELSE:
        # Method 2: DataForSEO backlink check (may have indexing delay)
        dataforseo_check = dataforseo_check_backlink(
            target=target_url,
            source=our_domain,
        )

        IF dataforseo_check.found:
            verification = {
                "status": "live_dataforseo_only",
                "anchor_text": dataforseo_check.anchor,
                "target_url": dataforseo_check.target_url,
                "is_nofollow": dataforseo_check.is_nofollow,
                "first_seen": dataforseo_check.first_seen,
            }
        ELSE:
            verification = {"status": "not_found"}

    # Update campaign status
    IF verification["status"] IN ["live", "live_dataforseo_only"]:
        campaign.status = "acquired"
        campaign.verified_at = now()
        campaign.link_details = verification
        emit_event("backlink.verified", campaign.to_dict())
    ELSE:
        # Link was promised but not placed
        campaign.verification_failures += 1
        IF campaign.verification_failures >= 3:
            campaign.status = "dead"
            campaign.death_reason = "link_not_placed_after_verification"

    RETURN verification
```

### 6.8 Execution Layer

```python
class OutreachExecutionLayer:
    """Exact API calls for Backlink & Outreach Agent."""

    # === GMAIL API ===

    def gmail_send(self, to: str, subject: str, body: str, from_name: str = None, reply_to: str = None) -> dict:
        """POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send"""
        import base64
        from email.mime.text import MIMEText

        msg = MIMEText(body, "html")
        msg["to"] = to
        msg["subject"] = subject
        if from_name:
            msg["from"] = from_name
        if reply_to:
            msg["reply-to"] = reply_to

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        response = self.gmail_client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {self.gmail_token}"},
            json={"raw": raw},
        )
        return {"message_id": response.json()["id"], "thread_id": response.json()["threadId"]}

    def gmail_send_reply(self, thread_id: str, body: str, subject: str = None) -> dict:
        """POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send (with threadId)"""
        import base64
        from email.mime.text import MIMEText

        # Fetch original message for headers
        original = self.gmail_client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}",
            headers={"Authorization": f"Bearer {self.gmail_token}"},
            params={"format": "metadata", "metadataHeaders": ["Subject", "From", "To", "Message-ID"]},
        ).json()

        original_headers = {h["name"]: h["value"] for h in original["messages"][0]["payload"]["headers"]}

        msg = MIMEText(body, "html")
        msg["to"] = original_headers.get("From", original_headers.get("To"))
        msg["subject"] = subject or f"Re: {original_headers.get('Subject', '')}"
        msg["In-Reply-To"] = original_headers.get("Message-ID", "")
        msg["References"] = original_headers.get("Message-ID", "")

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        response = self.gmail_client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            headers={"Authorization": f"Bearer {self.gmail_token}"},
            json={"raw": raw, "threadId": thread_id},
        )
        return {"message_id": response.json()["id"]}

    def gmail_check_for_replies(self, thread_id: str, since: datetime) -> list:
        """GET https://gmail.googleapis.com/gmail/v1/users/me/threads/{id}"""
        response = self.gmail_client.get(
            f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}",
            headers={"Authorization": f"Bearer {self.gmail_token}"},
            params={"format": "full"},
        )
        thread = response.json()
        replies = []
        for msg in thread.get("messages", []):
            msg_date = datetime.fromtimestamp(int(msg["internalDate"]) / 1000)
            if msg_date > since and msg["labelIds"].contains("SENT") is False:
                replies.append({
                    "id": msg["id"],
                    "date": msg_date,
                    "snippet": msg["snippet"],
                    "body": extract_body(msg["payload"]),
                    "from": get_header(msg["payload"], "From"),
                })
        return replies

    def gmail_setup_webhook(self, topic_name: str) -> dict:
        """POST https://gmail.googleapis.com/gmail/v1/users/me/watch"""
        response = self.gmail_client.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/watch",
            headers={"Authorization": f"Bearer {self.gmail_token}"},
            json={
                "topicName": topic_name,  # e.g., "projects/my-project/topics/gmail-inbox"
                "labelIds": ["INBOX"],
                "labelFilterBehavior": "INCLUDE",
            },
        )
        return response.json()  # {"historyId": "...", "expiration": "..."}

    # === EXA AI ===

    def exa_search(self, query: str, **kwargs) -> dict:
        """POST https://api.exa.ai/search"""
        response = httpx.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": self.exa_api_key},
            json={
                "query": query,
                "numResults": kwargs.get("num_results", 10),
                "useAutoprompt": kwargs.get("use_autoprompt", True),
                "contents": kwargs.get("contents", {"text": {"maxCharacters": 3000}}),
            },
            timeout=30,
        )
        return response.json()

    def exa_find_similar(self, url: str) -> dict:
        """POST https://api.exa.ai/findSimilar"""
        response = httpx.post(
            "https://api.exa.ai/findSimilar",
            headers={"x-api-key": self.exa_api_key},
            json={"url": url, "numResults": 10},
            timeout=30,
        )
        return response.json()

    # === TAVILY ===

    def tavily_search(self, query: str, **kwargs) -> dict:
        """POST https://api.tavily.com/search"""
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.tavily_api_key,
                "query": query,
                "search_depth": kwargs.get("search_depth", "advanced"),
                "max_results": kwargs.get("max_results", 5),
                "include_answer": True,
            },
            timeout=30,
        )
        return response.json()

    def tavily_extract(self, urls: list[str]) -> dict:
        """POST https://api.tavily.com/extract"""
        response = httpx.post(
            "https://api.tavily.com/extract",
            json={"api_key": self.tavily_api_key, "urls": urls},
            timeout=30,
        )
        return response.json()

    # === DATAFORSEO BACKLINKS API ===

    def dataforseo_get_backlinks(self, target: str, mode: str = "subdomains") -> dict:
        """POST https://api.dataforseo.com/v3/backlinks/backlinks/live"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/backlinks",
            params={
                "password": self.dataforseo_password,
                "target": target,
                "mode": mode,
                "limit": 1000,
                "output": "json",
            },
            timeout=30,
        )
        return response.json()

    def dataforseo_get_domain_rank(self, domain: str) -> float:
        """POST https://api.dataforseo.com/v3/backlinks/summary/live"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/backlinks",
            params={
                "password": self.dataforseo_password,
                "target": domain,
                "mode": "domain-rating",
                "output": "json",
            },
            timeout=30,
        )
        return response.json().get("domain_rating", 0)

    def dataforseo_get_broken_links(self, target: str, mode: str = "subdomains") -> list:
        """POST https://api.dataforseo.com/v3/backlinks/broken_backlinks/live"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/backlinks",
            params={
                "password": self.dataforseo_password,
                "target": target,
                "mode": "broken-backlinks",
                "limit": 500,
                "output": "json",
            },
            timeout=30,
        )
        return response.json().get("backlinks", [])

    def dataforseo_check_backlink(self, target: str, source: str) -> dict:
        """Check if a specific backlink exists via DataForSEO."""
        backlinks = self.dataforseo_get_backlinks(target, mode="exact")
        for bl in backlinks.get("backlinks", []):
            if source in bl.get("url_from", ""):
                return {
                    "found": True,
                    "anchor": bl.get("anchor", ""),
                    "target_url": bl.get("url_to", ""),
                    "is_nofollow": bl.get("nofollow", False),
                    "first_seen": bl.get("first_seen", ""),
                }
        return {"found": False}
```

### 6.9 Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| CPU | 4 cores | LLM-intensive for pitch/response generation |
| Memory | 4 GB | Campaign data + research buffers |
| Time | Full pipeline run: ≤2 hours | Per campaign: ≤5 min |
| API Quota | Gmail: 250/day (consumer), Exa: 1000/min, DataForSEO: 2000/min, Tavily: 1000/day | |
| Daily Emails | Max 50 outreach emails/day | Configurable, respects Gmail limits |

### 6.10 Error Handling

```python
class OutreachErrorHandler:
    retry_policy = {
        "gmail_quota":        {"backoff": "exponential", "base_delay": 3600, "max_retries": 3},
        "gmail_auth_expired": {"action": "refresh_oauth_token", "max_retries": 2},
        "gmail_send_failed":  {"backoff": "exponential", "base_delay": 60, "max_retries": 3},
        "exa_error":          {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "dataforseo_quota":       {"backoff": "linear", "base_delay": 3600, "max_retries": 3},
        "tavily_error":       {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "contact_not_found":  {"action": "try_alternative_methods", "max_retries": 2},
        "verification_failed":{"backoff": "linear", "base_delay": 86400, "max_retries": 7},  # Wait 1 day between checks
    }

    fallback_strategies = {
        "gmail_unavailable":     "queue_emails + retry_later",
        "exa_unavailable":       "fallback_to_tavily_search",
        "dataforseo_unavailable":    "skip_backlink_verification + use_http_check",
        "contact_not_found_any": "mark_prospect_as_unreachable + move_to_dead",
        "llm_unavailable":       "use_template_pitches + flag_for_human_review",
    }

    dead_letter_queue = {
        "queue_name": "outreach:dlq",
        "max_size": 5000,
        "ttl_days": 90,  # Keep longer for outreach history
    }
```

### 6.11 Configuration

```yaml
outreach:
  gmail:
    oauth_client_id: "${GMAIL_CLIENT_ID}"
    oauth_client_secret: "${GMAIL_CLIENT_SECRET}"
    oauth_refresh_token: "${GMAIL_REFRESH_TOKEN}"
    from_name: "John Doe"
    from_email: "john@company.com"
    daily_send_limit: 50
    tracking_enabled: true
    webhook_topic: "projects/my-project/topics/gmail-inbox"

  campaigns:
    default_followup_delays:
      follow_up_1_days: 3
      follow_up_2_days: 5
      final_followup_days: 7
    max_followups: 2
    auto_mark_dead_after_days: 21
    require_link_verification: true
    verification_check_interval_hours: 24
    verification_max_attempts: 7

  haro:
    enabled: true
    check_interval_minutes: 30
    min_relevance_score: 0.6
    max_responses_per_day: 10
    auto_send: false              # Require human approval
    journalist_reply_timeout_days: 7

  broken_link:
    enabled: true
    run_cron: "0 4 * * 1"        # Monday 04:00 UTC
    target_domains: []            # Auto-discover if empty
    max_opportunities_per_run: 20
    auto_create_content: true
    min_domain_rating: 30

  guest_post:
    enabled: true
    run_cron: "0 4 * * 3"        # Wednesday 04:00 UTC
    target_count: 50
    min_domain_rating: 40
    max_pitches_per_week: 20

  unlinked_mentions:
    enabled: true
    run_cron: "0 5 * * 5"        # Friday 05:00 UTC
    brand_variants: ["BrandName", "Brand Name", "@brandhandle"]
    min_domain_rating: 20
    max_outreach_per_run: 15

  link_verification:
    check_after_days: 3
    recheck_interval_days: 1
    max_rechecks: 7
    methods: ["direct_http", "dataforseo"]

  rate_limits:
    emails_per_hour: 10
    emails_per_day: 50
    exa_searches_per_hour: 100
    dataforseo_queries_per_hour: 50
```

### 6.12 Monitoring

```yaml
outreach_metrics:
  counters:
    - campaigns_created_total{type="haro|broken_link|guest_post|unlinked_mention"}
    - emails_sent_total{type="initial|followup_1|followup_2|final"}
    - replies_received_total{sentiment="positive|negative|neutral"}
    - links_acquired_total
    - links_verified_total
    - campaigns_died_total{reason="no_response|rejected|link_not_placed"}

  gauges:
    - active_campaigns_count{status="prospecting|outreach_sent|follow_up_*|negotiating"}
    - email_send_quota_remaining_today
    - gmail_oauth_token_expires_in_hours
    - average_response_rate_percent
    - average_acquisition_rate_percent

  histograms:
    - campaign_duration_days (outreach_sent → acquired)
    - emails_per_acquisition
    - prospect_domain_rating_distribution

  alerts:
    - name: "gmail_quota_exhausted"
      condition: "email_send_quota_remaining_today == 0"
      severity: "critical"
    - name: "low_response_rate"
      condition: "response_rate_7d < 5%"
      severity: "warning"
    - name: "oauth_token_expiring"
      condition: "gmail_oauth_token_expires_in_hours < 24"
      severity: "critical"
    - name: "acquisition_rate_declining"
      condition: "acquisition_rate_30d < acquisition_rate_90d * 0.7"
      severity: "warning"
    - name: "dlq_growing"
      condition: "outreach_dlq_size > 100"
      severity: "warning"
```

---

## 7. Agent 6: Competitor Agent

### 7.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    COMPETITOR AGENT                               │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ Content Monitor   │  │ Keyword Stealer   │  │ Backlink       │ │
│  │                  │  │ Detector          │  │ Strategy       │ │
│  │ New pages        │  │                  │  │ Analyzer       │ │
│  │ Content updates  │  │ SERP overlap     │  │                │ │
│  │ Topic shifts     │  │ Position gains   │  │ New links      │ │
│  └──────────────────┘  └──────────────────┘  │ Link velocity  │ │
│                                               └────────────────┘ │
│  ┌──────────────────┐                                            │
│  │ Gap Identifier    │                                            │
│  │                  │                                            │
│  │ Content gaps     │                                            │
│  │ Keyword gaps     │                                            │
│  │ Backlink gaps    │                                            │
│  └──────────────────┘                                            │
│                                                                  │
│  State Machine:                                                  │
│  IDLE → MONITORING → ANALYZING → REPORTING → IDLE                │
└─────────────────────────────────────────────────────────────────┘
```

**Class Hierarchy:**

```python
class CompetitorAgent(BaseAgent):
    """Competitor intelligence — monitors, detects, and identifies gaps."""

    components: dict = {
        "content_monitor": CompetitorContentMonitor,
        "keyword_stealer": KeywordStealDetector,
        "backlink_analyzer": CompetitorBacklinkAnalyzer,
        "gap_identifier": GapIdentifier,
        "exa_client": ExaClient,
        "tavily_client": TavilyClient,
        "dataforseo_client": DataForSEOClient,
        "dataforseo_client": DataForSEOClient,
    }
```

### 7.2 Triggers

| Trigger Type | Condition | Priority |
|-------------|-----------|----------|
| **Scheduled** | Daily competitor content scan | P2 |
| **Scheduled** | Weekly backlink strategy analysis | P2 |
| **Event** | Competitor rank improvement detected by Scout | P1 |
| **Proactive** | Competitor publishes content targeting our top keywords | P1 |
| **Proactive** | Competitor gains high-DR backlink | P1 |
| **Proactive** | New competitor enters SERP for tracked keywords | P2 |

### 7.3 Workflows

#### 7.3.1 Content Monitoring

```pseudocode
FUNCTION monitor_competitor_content(competitors):
    FOR EACH competitor IN competitors:
        # Find new content via Exa
        new_content = exa_search(
            query=f"site:{competitor.domain}",
            num_results=20,
            type="keyword",  # Recent content
        )

        # Compare with last known content snapshot
        known = load_known_content(competitor.domain)
        new_pages = filter(new_content, lambda c: c.url NOT IN known)

        FOR EACH page IN new_pages:
            # Analyze content
            content_data = tavily_extract([page.url])

            # Check if targeting our keywords
            our_keywords = load_tracked_keywords()
            targeted_keywords = match_keywords(content_data.text, our_keywords)

            IF targeted_keywords:
                emit_event("competitor.keyword_threat", {
                    "competitor": competitor.domain,
                    "page": page.url,
                    "targeted_keywords": targeted_keywords,
                    "priority": "P1",
                })

            # Store for future comparison
            store_competitor_page(competitor.domain, page, content_data)
```

#### 7.3.2 Keyword Stealing Detection

```pseudocode
FUNCTION detect_keyword_stealing(competitors):
    """Detect when competitors overtake us for tracked keywords."""

    our_keywords = load_tracked_keywords()
    alerts = []

    FOR EACH keyword IN our_keywords:
        # Get current SERP data
        serp = dataforseo_serp_search(engine="google", keyword=keyword, depth=20)

        our_pos = find_position(serp, our_domain)

        FOR EACH competitor IN competitors:
            comp_pos = find_position(serp, competitor.domain)

            IF comp_pos AND (NOT our_pos OR comp_pos < our_pos):
                # Competitor outranks us
                previous = load_previous_snapshot(keyword, competitor.domain)

                IF previous AND previous.position > comp_pos:
                    # Competitor improved
                    alerts.append({
                        "type": "keyword_steal",
                        "keyword": keyword,
                        "competitor": competitor.domain,
                        "competitor_new_position": comp_pos,
                        "competitor_old_position": previous.position,
                        "our_position": our_pos.rank if our_pos else "not_ranking",
                    })

    IF alerts:
        emit_event("competitor.keyword_stealing", {"alerts": alerts})
```

#### 7.3.3 Backlink Strategy Analysis

```pseudocode
FUNCTION analyze_competitor_backlinks(competitors):
    FOR EACH competitor IN competitors:
        # Get new backlinks
        new_links = dataforseo_get_new_backlinks(
            target=competitor.domain,
            since=yesterday,
        )

        # Analyze link patterns
        patterns = {
            "total_new": len(new_links),
            "avg_dr": average([l.domain_rating for l in new_links]),
            "high_dr_count": count([l for l in new_links if l.domain_rating >= 50]),
            "link_types": categorize_links(new_links),  # guest_post, editorial, directory, etc.
            "anchor_distribution": analyze_anchors(new_links),
            "content_types": analyze_linked_content(new_links),
        }

        # Detect strategy shifts
        historical = load_historical_patterns(competitor.domain)
        strategy_change = detect_strategy_change(patterns, historical)

        IF strategy_change:
            emit_event("competitor.strategy_change", {
                "competitor": competitor.domain,
                "change": strategy_change,
                "patterns": patterns,
            })

        # Identify link opportunities (sites linking to competitor but not us)
        gap_links = find_link_gaps(competitor.domain, our_domain, new_links)

        IF gap_links:
            emit_event("competitor.link_opportunity", {
                "competitor": competitor.domain,
                "opportunities": gap_links[:20],  # Top 20
            })
```

### 7.4 Execution Layer

```python
class CompetitorExecutionLayer:
    """API calls for Competitor Agent — reuses Exa, Tavily, DataForSEO."""

    def exa_search(self, query: str, **kwargs) -> dict:
        """POST https://api.exa.ai/search"""
        response = httpx.post(
            "https://api.exa.ai/search",
            headers={"x-api-key": self.exa_api_key},
            json={"query": query, "numResults": kwargs.get("num_results", 20), "useAutoprompt": True},
            timeout=30,
        )
        return response.json()

    def tavily_extract(self, urls: list[str]) -> dict:
        """POST https://api.tavily.com/extract"""
        response = httpx.post(
            "https://api.tavily.com/extract",
            json={"api_key": self.tavily_api_key, "urls": urls},
            timeout=30,
        )
        return response.json()

    def dataforseo_get_new_backlinks(self, target: str, since: str) -> list:
        """POST https://api.dataforseo.com/v3/backlinks/backlinks/live"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/backlinks",
            params={
                "password": self.dataforseo_password,
                "target": target,
                "mode": "new-backlinks",
                "date": since,
                "limit": 500,
                "output": "json",
            },
            timeout=30,
        )
        return response.json().get("backlinks", [])

    def dataforseo_get_refdomains(self, target: str) -> list:
        """POST https://api.dataforseo.com/v3/backlinks/referring_domains/live"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/backlinks",
            params={
                "password": self.dataforseo_password,
                "target": target,
                "mode": "refdomains",
                "limit": 500,
                "output": "json",
            },
            timeout=30,
        )
        return response.json().get("refdomains", [])

    def dataforseo_serp_search(self, engine: str, q: str, **kwargs) -> dict:
        """POST https://api.dataforseo.com/v3/serp/{engine}/organic/live/regular"""
        response = httpx.get(
            "https://api.dataforseo.com/v3/serp/" + engine + "/organic/live/regular",
            params={"engine": engine, "q": q, "login": self.dataforseo_login, "num": kwargs.get("num", 20)},
            timeout=30,
        )
        return response.json()
```

### 7.5 Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| CPU | 2 cores | Analysis is API-heavy |
| Memory | 2 GB | Competitor data caches |
| Time | Full competitor scan: ≤1 hour | |
| API Quota | Exa/Tavily/DataForSEO shared with other agents | |

### 7.6 Error Handling

```python
class CompetitorErrorHandler:
    retry_policy = {
        "exa_error":     {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "dataforseo_quota":  {"backoff": "linear", "base_delay": 3600, "max_retries": 3},
        "dataforseo_quota": {"backoff": "linear", "base_delay": 3600, "max_retries": 3},
    }
    dead_letter_queue = {"queue_name": "competitor:dlq", "max_size": 2000, "ttl_days": 30}
```

### 7.7 Configuration

```yaml
competitor:
  monitoring:
    content_scan_cron: "0 6 * * *"           # Daily 06:00 UTC
    backlink_analysis_cron: "0 7 * * 1"      # Monday 07:00 UTC
    competitors:
      - domain: "competitor1.com"
        priority: "high"
      - domain: "competitor2.com"
        priority: "medium"
      - domain: "competitor3.com"
        priority: "low"
    max_competitors: 10

  alerts:
    new_content_alert: true
    keyword_steal_alert: true
    backlink_gain_alert: true
    strategy_change_alert: true
```

### 7.8 Monitoring

```yaml
competitor_metrics:
  counters:
    - competitor_pages_monitored_total
    - keyword_steal_events_total
    - backlink_opportunities_found_total
    - gap_reports_generated_total

  gauges:
    - competitors_tracked_count
    - avg_competitor_content_velocity
    - our_keyword_share_percent

  alerts:
    - name: "competitor_surge"
      condition: "keyword_steal_events_7d > 10"
      severity: "critical"
```

---

## 8. Agent 7: Decision Engine

### 8.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DECISION ENGINE                              │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ Priority Scorer   │  │ Resource Allocator│  │ Conflict       │ │
│  │                  │  │                  │  │ Resolver       │ │
│  │ Impact scoring   │  │ API budget       │  │                │ │
│  │ Effort scoring   │  │ Time budget      │  │ Deduplication  │ │
│  │ ROI ranking      │  │ Token budget     │  │ Prioritization │ │
│  └──────────────────┘  └──────────────────┘  │ Dependencies   │ │
│                                               └────────────────┘ │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │                  Proactive Trigger Rules                      ││
│  │                                                              ││
│  │  1. Rank drop ≥3 for top-10 keyword → immediate content audit││
│  │  2. CWV regression below "good" → auto-fix trigger           ││
│  │  3. Broken link rate >5% → crawl escalation                  ││
│  │  4. Competitor outranks for 3+ keywords → counter-strategy   ││
│  │  5. Backlink acquired → re-crawl + rank check                ││
│  │  6. Content published → schema inject + sitemap submit       ││
│  │  7. HARO deadline <2h → priority boost                       ││
│  │  8. Email reply received → immediate notification            ││
│  └──────────────────────────────────────────────────────────────┘│
│                                                                  │
│  State Machine:                                                  │
│  RECEIVING → SCORING → ALLOCATING → DISPATCHING → MONITORING    │
└─────────────────────────────────────────────────────────────────┘
```

**Class Hierarchy:**

```python
class DecisionEngine(BaseAgent):
    """Central orchestrator — scores, allocates, resolves, triggers."""

    components: dict = {
        "priority_scorer": PriorityScorer,
        "resource_allocator": ResourceAllocator,
        "conflict_resolver": ConflictResolver,
        "trigger_registry": ProactiveTriggerRegistry,
        "task_dispatcher": TaskDispatcher,
    }

    PROACTIVE_TRIGGERS = {
        "rank_drop_critical":     {"condition": "rank_drop >= 3 for top10_keyword", "action": "priority_content_audit"},
        "cwv_regression":         {"condition": "cwv_status == 'poor'", "action": "trigger_self_healing"},
        "broken_link_spike":      {"condition": "broken_link_rate > 0.05", "action": "escalate_crawl"},
        "competitor_overtake":    {"condition": "competitor_outanks >= 3 keywords", "action": "generate_counter_strategy"},
        "backlink_acquired":      {"condition": "new_backlink_verified", "action": "recrawl_and_rankcheck"},
        "content_published":      {"condition": "new_content_published", "action": "schema_inject_and_sitemap"},
        "haro_deadline":          {"condition": "haro_deadline < 2h", "action": "boost_haro_priority"},
        "outreach_reply":         {"condition": "email_reply_received", "action": "immediate_notification"},
    }
```

### 8.2 Priority Scoring Algorithm

```python
class PriorityScorer:
    """Score tasks on impact × urgency / effort."""

    def score_task(self, task: Task) -> float:
        """
        Priority = (Impact × Urgency × Confidence) / (Effort × Risk)

        Impact (0-10):     Expected SEO improvement
        Urgency (0-10):    Time sensitivity
        Confidence (0-1):  How certain we are this will work
        Effort (0-10):     Resources required (time, API, tokens)
        Risk (0-1):        Probability of negative outcome
        """
        impact = self.score_impact(task)
        urgency = self.score_urgency(task)
        confidence = self.score_confidence(task)
        effort = self.score_effort(task)
        risk = self.score_risk(task)

        raw_score = (impact * urgency * confidence) / (effort * max(risk, 0.1))

        # Normalize to 0-100
        normalized = min(raw_score * 10, 100)

        # Apply priority class
        if normalized >= 80:
            priority = "P0"
        elif normalized >= 60:
            priority = "P1"
        elif normalized >= 40:
            priority = "P2"
        else:
            priority = "P3"

        return PriorityScore(
            raw=raw_score,
            normalized=normalized,
            priority=priority,
            breakdown={
                "impact": impact,
                "urgency": urgency,
                "confidence": confidence,
                "effort": effort,
                "risk": risk,
            },
        )

    def score_impact(self, task: Task) -> float:
        """Score expected SEO impact."""
        factors = {
            "keyword_volume": task.keyword_monthly_volume / 10000,  # Normalize
            "current_position": (101 - task.current_position) / 100,  # Lower = more room
            "page_traffic_share": task.page_traffic_pct,
            "domain_authority_boost": task.expected_da_boost,
            "revenue_impact": task.estimated_revenue_impact / 10000,
        }
        return weighted_average(factors, weights=[0.3, 0.2, 0.2, 0.1, 0.2])

    def score_urgency(self, task: Task) -> float:
        """Score time sensitivity."""
        base = 5.0
        if task.type == "haro" and task.deadline_hours < 2:
            return 10.0
        if task.type == "rank_drop" and task.drop_amount >= 5:
            return 9.0
        if task.type == "cwv_critical":
            return 8.0
        if task.type == "broken_link_spike":
            return 7.0
        if task.created_hours_ago > 48:
            base += 2  # Aging boost
        return min(base, 10.0)
```

### 8.3 Resource Allocation

```python
class ResourceAllocator:
    """Allocate API budgets, compute time, and LLM tokens across agents."""

    daily_budgets = {
        "dataforseo_requests": 2000,          # 5000/month ÷ 30
        "gmail_sends": 50,
        "exa_requests": 1000,
        "tavily_requests": 1000,
        "dataforseo_requests": 2000,
        "pagespeed_requests": 1000,
        "gsc_requests": 5000,
        "llm_tokens": 100000,
    }

    agent_allocations = {
        "sentinel": {"dataforseo": 0.05, "gsc": 0.40, "pagespeed": 0.10},
        "forge":    {"dataforseo": 0.20, "exa": 0.40, "tavily": 0.50, "llm": 0.50, "gsc": 0.20},
        "technical":{"pagespeed": 0.80, "gsc": 0.20},
        "scout":    {"dataforseo": 0.60, "gsc": 0.10},
        "outreach": {"gmail": 1.00, "exa": 0.40, "tavily": 0.30, "dataforseo": 0.50, "llm": 0.30},
        "competitor":{"exa": 0.20, "tavily": 0.20, "dataforseo": 0.50, "dataforseo": 0.15},
    }

    def allocate(self, agent: str, api: str, requested: int) -> int:
        """Return how many requests the agent can make."""
        daily_total = self.daily_budgets.get(api, 0)
        agent_share = self.agent_allocations.get(agent, {}).get(api, 0)
        agent_budget = int(daily_total * agent_share)
        used = self.get_used_today(agent, api)
        remaining = max(0, agent_budget - used)

        # Allow burst from unallocated pool if available
        if remaining < requested:
            total_used = self.get_total_used_today(api)
            pool_remaining = max(0, daily_total - total_used)
            remaining = min(remaining + pool_remaining, requested)

        return min(requested, remaining)
```

### 8.4 Conflict Resolution

```python
class ConflictResolver:
    """Resolve conflicts when multiple agents want the same resource."""

    def resolve(self, conflicts: list[Conflict]) -> list[Resolution]:
        resolutions = []

        for conflict in conflicts:
            if conflict.type == "api_budget":
                # Higher priority agent wins
                winner = max(conflict.claimants, key=lambda c: c.priority_score)
                resolutions.append(Resolution(
                    conflict=conflict,
                    winner=winner,
                    losers=[c for c in conflict.claimants if c != winner],
                    action="grant_budget",
                ))

            elif conflict.type == "same_url_task":
                # Deduplicate — combine tasks if possible
                if can_combine(conflict.claimants):
                    combined = combine_tasks(conflict.claimants)
                    resolutions.append(Resolution(
                        conflict=conflict,
                        winner=combined,
                        action="merge_tasks",
                    ))
                else:
                    # Higher priority wins, others queued
                    winner = max(conflict.claimants, key=lambda c: c.priority_score)
                    resolutions.append(Resolution(
                        conflict=conflict,
                        winner=winner,
                        losers=[c for c in conflict.claimants if c != winner],
                        action="queue_losers",
                    ))

            elif conflict.type == "llm_contention":
                # Round-robin with priority weighting
                sorted_claimants = sorted(conflict.claimants, key=lambda c: -c.priority_score)
                remaining_tokens = conflict.available_tokens
                for claimant in sorted_claimants:
                    allocation = min(claimant.requested_tokens, remaining_tokens)
                    claimant.granted_tokens = allocation
                    remaining_tokens -= allocation

        return resolutions
```

### 8.5 Triggers

| Trigger Type | Condition | Action |
|-------------|-----------|--------|
| **Proactive 1** | Rank drop ≥3 for top-10 keyword | Dispatch content audit to Forge |
| **Proactive 2** | CWV regression below "good" | Dispatch self-healing to Technical |
| **Proactive 3** | Broken link rate >5% | Escalate crawl priority in Sentinel |
| **Proactive 4** | Competitor outranks for 3+ keywords | Generate counter-strategy via Competitor + Forge |
| **Proactive 5** | Backlink acquired (verified) | Trigger re-crawl + rank check |
| **Proactive 6** | Content published | Schema inject + sitemap submit |
| **Proactive 7** | HARO deadline <2h | Boost HARO response priority |
| **Proactive 8** | Email reply received | Immediate notification to user |

### 8.6 Configuration

```yaml
decision_engine:
  scoring:
    impact_weight: 0.30
    urgency_weight: 0.25
    confidence_weight: 0.20
    effort_weight: 0.15
    risk_weight: 0.10
    min_score_for_execution: 20

  resource_allocation:
    daily_budgets:
      dataforseo_requests: 167
      gmail_sends: 50
      exa_requests: 1000
      tavily_requests: 1000
      dataforseo_requests: 500
      pagespeed_requests: 1000
      gsc_requests: 5000
      llm_tokens: 100000

  triggers:
    rank_drop_threshold: 3
    cwv_regression_enabled: true
    broken_link_spike_threshold: 0.05
    competitor_overtake_threshold: 3
    haro_deadline_boost_hours: 2
    auto_dispatch_p0: true
    require_approval_p1: false
    require_approval_p2: true
```

### 8.7 Monitoring

```yaml
decision_metrics:
  counters:
    - tasks_scored_total
    - tasks_dispatched_total{priority="P0|P1|P2|P3"}
    - proactive_triggers_fired_total{trigger_type}
    - conflicts_resolved_total
    - budget_allocations_total

  gauges:
    - daily_budget_utilization_percent{api}
    - task_queue_depth{priority}
    - average_task_score
    - p0_tasks_pending_count

  alerts:
    - name: "p0_task_backlog"
      condition: "p0_tasks_pending > 5"
      severity: "critical"
    - name: "budget_exhausted"
      condition: "daily_budget_utilization > 95 for any api"
      severity: "warning"
```

---

## 9. Agent 8: Action Executor

### 9.1 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     ACTION EXECUTOR                              │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐ │
│  │ Auto-Fix Engine   │  │ Content Publisher │  │ Email Sender   │ │
│  │                  │  │                  │  │                │ │
│  │ 8 issue types    │  │ CMS integration  │  │ Gmail API      │ │
│  │ Rollback support │  │ Preview/staging  │  │ Templates      │ │
│  │ Git integration  │  │ Schedule publish │  │ Tracking       │ │
│  └──────────────────┘  └──────────────────┘  └────────────────┘ │
│                                                                  │
│  ┌──────────────────┐  ┌──────────────────┐                     │
│  │ Notification      │  │ Campaign Status  │                     │
│  │ Dispatcher        │  │ Updater          │                     │
│  │                  │  │                  │                     │
│  │ Slack            │  │ State transitions│                     │
│  │ Email            │  │ History logging  │                     │
│  │ Webhook          │  │ Audit trail      │                     │
│  └──────────────────┘  └──────────────────┘                     │
│                                                                  │
│  State Machine:                                                  │
│  RECEIVED → VALIDATING → EXECUTING → VERIFYING → DONE/FAILED     │
└─────────────────────────────────────────────────────────────────┘
```

**Class Hierarchy:**

```python
class ActionExecutor(BaseAgent):
    """Executes actions dispatched by the Decision Engine."""

    components: dict = {
        "auto_fix_engine": AutoFixEngine,          # Technical fixes
        "content_publisher": ContentPublisher,      # CMS publishing
        "email_sender": EmailSender,               # Gmail API wrapper
        "notification_dispatcher": NotificationDispatcher,  # Slack/email/webhook
        "campaign_updater": CampaignStatusUpdater,  # Outreach state management
        "rollback_manager": RollbackManager,        # Undo support
    }

    SUPPORTED_ACTIONS = [
        "fix_broken_link",          # Update internal link targets
        "inject_meta_tag",          # Add/update meta tags
        "inject_schema",            # Add JSON-LD schema
        "inject_h1",                # Add missing H1
        "inject_alt_text",          # Add image alt text
        "fix_canonical",            # Correct canonical URL
        "fix_redirect_chain",       # Simplify redirect chain
        "publish_content",          # Publish to CMS
        "send_email",               # Send via Gmail API
        "send_notification",        # Slack/email/webhook
        "update_campaign_status",   # Outreach state change
        "submit_sitemap",           # Submit to search engines
        "request_indexing",         # GSC indexing request
    ]
```

### 9.2 Triggers

| Trigger Type | Condition | Priority |
|-------------|-----------|----------|
| **Event** | `action.*` events from any agent | Inherited from event |
| **Event** | Decision Engine dispatches P0 task | P0 |
| **Event** | Decision Engine dispatches P1 task | P1 |
| **Event** | Human approval received for pending action | P1 |

### 9.3 Workflow

```pseudocode
FUNCTION execute_action(action):
    # 1. Validate
    validation = validate_action(action)
    IF NOT validation.valid:
        emit_event("action.validation_failed", {action: action, errors: validation.errors})
        RETURN {"status": "validation_failed"}

    # 2. Check approval requirements
    IF action.requires_approval AND NOT action.approved:
        emit_event("action.pending_approval", action.to_dict())
        RETURN {"status": "pending_approval"}

    # 3. Create rollback point
    rollback_data = create_rollback_point(action)

    # 4. Execute
    TRY:
        SWITCH action.type:
            CASE "fix_broken_link":
                result = cms_update_link(
                    page=action.referrer_url,
                    old_url=action.broken_url,
                    new_url=action.replacement_url,
                )
            CASE "inject_meta_tag":
                result = cms_inject_meta(
                    page=action.page_url,
                    tag=action.tag_name,
                    content=action.tag_content,
                )
            CASE "inject_schema":
                result = cms_inject_schema(
                    page=action.page_url,
                    schema_json=action.schema_json_ld,
                )
            CASE "publish_content":
                result = cms_publish(
                    content=action.content_package,
                    status="draft",  # Default to draft
                    scheduled_at=action.scheduled_at,
                )
            CASE "send_email":
                result = gmail_send(
                    to=action.to,
                    subject=action.subject,
                    body=action.body,
                )
            CASE "send_notification":
                result = dispatch_notification(
                    channels=action.channels,  # ["slack", "email", "webhook"]
                    title=action.title,
                    message=action.message,
                    severity=action.severity,
                )
            CASE "update_campaign_status":
                result = update_campaign(
                    campaign_id=action.campaign_id,
                    new_status=action.new_status,
                    metadata=action.metadata,
                )
            CASE "submit_sitemap":
                result = submit_sitemap_to_engines(
                    sitemap_url=action.sitemap_url,
                    engines=action.engines,
                )
            CASE "request_indexing":
                result = gsc_request_indexing(action.url)

        # 5. Verify execution
        verification = verify_execution(action, result)
        IF verification.success:
            emit_event("action.completed", {action: action, result: result})
            log_action_audit(action, result, "success")
        ELSE:
            emit_event("action.verification_failed", {action: action, result: result})
            rollback(rollback_data)
            log_action_audit(action, result, "verification_failed")

    CATCH Exception as e:
        # Rollback on error
        rollback(rollback_data)
        emit_event("action.failed", {action: action, error: str(e)})
        log_action_audit(action, None, "failed", error=str(e))

        # Re-queue if retryable
        IF is_retryable(e):
            requeue_action(action, delay=calculate_backoff(action.retry_count))
```

### 9.4 Execution Layer

```python
class ActionExecutorExecutionLayer:
    """Exact API calls for Action Executor."""

    # --- CMS Integration (generic — adapt to WordPress, Contentful, etc.) ---
    def cms_update_link(self, page_url: str, old_url: str, new_url: str) -> dict:
        """Update a link in CMS content."""
        # Implementation depends on CMS
        # WordPress: PUT /wp-json/wp/v2/posts/{id}
        # Contentful: PUT /spaces/{space}/entries/{id}
        page = self.cms_client.get_page(page_url)
        updated_content = page.content.replace(old_url, new_url)
        return self.cms_client.update_page(page.id, content=updated_content)

    def cms_inject_meta(self, page_url: str, tag: str, content: str) -> dict:
        """Inject or update meta tag in CMS."""
        page = self.cms_client.get_page(page_url)
        return self.cms_client.update_page_meta(page.id, tag, content)

    def cms_inject_schema(self, page_url: str, schema_json: str) -> dict:
        """Inject JSON-LD schema into page."""
        page = self.cms_client.get_page(page_url)
        return self.cms_client.update_page_schema(page.id, schema_json)

    def cms_publish(self, content: dict, status: str = "draft", scheduled_at: str = None) -> dict:
        """Publish content to CMS."""
        return self.cms_client.create_page(
            title=content["title"],
            body=content["body"],
            meta=content["meta"],
            schema=content["schema"],
            status=status,
            scheduled_at=scheduled_at,
        )

    # --- Gmail API (via Outreach Agent's client) ---
    def gmail_send(self, to: str, subject: str, body: str) -> dict:
        """POST https://gmail.googleapis.com/gmail/v1/users/me/messages/send"""
        return self.outreach_agent.gmail_client.send(to=to, subject=subject, body=body)

    # --- Notification Dispatch ---
    def dispatch_notification(self, channels: list, title: str, message: str, severity: str) -> dict:
        """Send notification to multiple channels."""
        results = {}
        for channel in channels:
            if channel == "slack":
                results["slack"] = self.slack_client.post_message(
                    channel=self.slack_channel,
                    blocks=[
                        {"type": "header", "text": {"type": "plain_text", "text": title}},
                        {"type": "section", "text": {"type": "mrkdwn", "text": message}},
                        {"type": "context", "elements": [
                            {"type": "mrkdwn", "text": f"Severity: {severity} | {datetime.now().isoformat()}"}
                        ]},
                    ],
                )
            elif channel == "email":
                results["email"] = self.gmail_send(
                    to=self.admin_email,
                    subject=f"[{severity.upper()}] {title}",
                    body=message,
                )
            elif channel == "webhook":
                results["webhook"] = httpx.post(
                    self.webhook_url,
                    json={"title": title, "message": message, "severity": severity, "timestamp": now()},
                    timeout=10,
                )
        return results

    # --- Sitemap Submission ---
    def submit_sitemap_to_engines(self, sitemap_url: str, engines: list) -> dict:
        """Submit sitemap to multiple search engines."""
        results = {}
        for engine in engines:
            if engine == "google":
                # GSC: ping
                results["google"] = httpx.get(
                    f"https://www.google.com/ping?sitemap={sitemap_url}",
                    timeout=10,
                ).status_code
            elif engine == "bing":
                # Bing: ping
                results["bing"] = httpx.get(
                    f"https://www.bing.com/ping?sitemap={sitemap_url}",
                    timeout=10,
                ).status_code
            elif engine == "yandex":
                results["yandex"] = httpx.get(
                    f"https://webmaster.yandex.com/ping?sitemap={sitemap_url}",
                    timeout=10,
                ).status_code
        return results

    # --- GSC Indexing Request ---
    def gsc_request_indexing(self, url: str) -> dict:
        """POST https://searchconsole.googleapis.com/webmasters/v3/sites/{siteUrl}/urlInspection/index:inspect"""
        response = self.gsc_client.post(
            f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(self.site_url, safe='')}/urlInspection/index:inspect",
            headers={"Authorization": f"Bearer {self.gsc_token}"},
            json={"inspectionUrl": url, "siteUrl": self.site_url},
        )
        return response.json()
```

### 9.5 Resource Budget

| Resource | Limit | Notes |
|----------|-------|-------|
| CPU | 2 cores | Mostly I/O bound |
| Memory | 2 GB | Action queue buffers |
| Time | Single action: ≤30s, Batch: ≤10 min | |
| API Quota | Inherits from parent agent's allocation | |

### 9.6 Error Handling

```python
class ActionExecutorErrorHandler:
    retry_policy = {
        "cms_error":        {"backoff": "exponential", "base_delay": 10, "max_retries": 3},
        "gmail_send_error": {"backoff": "exponential", "base_delay": 60, "max_retries": 3},
        "notification_error":{"backoff": "exponential", "base_delay": 5, "max_retries": 2},
        "verification_error":{"backoff": "linear", "base_delay": 30, "max_retries": 3},
    }

    fallback_strategies = {
        "cms_unavailable":       "queue_action + alert",
        "gmail_unavailable":     "queue_email + retry_later",
        "slack_unavailable":     "fallback_to_email_only",
        "verification_fails":    "rollback + alert + manual_review",
    }

    rollback_support = {
        "enabled": True,
        "max_rollback_history": 1000,
        "rollback_ttl_hours": 72,
    }
```

### 9.7 Configuration

```yaml
action_executor:
  auto_fix:
    enabled: true
    require_approval_above_confidence: 0.9  # Below this = auto-approve
    rollback_on_failure: true
    max_concurrent_fixes: 10

  publishing:
    default_status: "draft"
    auto_publish_enabled: false
    staging_preview: true

  notifications:
    channels: ["slack", "email"]
    slack_webhook_url: "${SLACK_WEBHOOK_URL}"
    slack_channel: "#seo-alerts"
    admin_email: "admin@company.com"
    severity_routing:
      critical: ["slack", "email"]
      warning: ["slack"]
      info: ["slack"]

  gmail:
    daily_limit: 50
    rate_limit_per_minute: 5

  auditing:
    log_all_actions: true
    retention_days: 365
    include_rollback_data: true
```

### 9.8 Monitoring

```yaml
action_metrics:
  counters:
    - actions_executed_total{type, status="success|failed|rolled_back"}
    - auto_fixes_applied_total{issue_type}
    - content_published_total
    - emails_sent_total
    - notifications_dispatched_total{channel}

  gauges:
    - action_queue_depth
    - pending_approvals_count
    - rollback_history_size

  histograms:
    - action_execution_duration_seconds
    - time_to_execute_p0_seconds

  alerts:
    - name: "action_failure_spike"
      condition: "action_failures_1h > 20"
      severity: "critical"
    - name: "p0_action_delayed"
      condition: "p0_action_age > 5 minutes"
      severity: "critical"
    - name: "rollback_triggered"
      condition: "any_rollback"
      severity: "warning"
```

---

## 10. Inter-Agent Communication Protocol

### 10.1 Event Types

| Event | Source | Target | Priority | Payload |
|-------|--------|--------|----------|---------|
| `crawl.complete` | Sentinel | Decision | P2 | Crawl report summary |
| `issue.broken_link` | Sentinel | Decision → Executor | P1 | URL, status, auto-fixable |
| `content.audit_complete` | Forge | Decision | P2 | Scores, recommendations |
| `content.generated` | Forge | Decision → Executor | P2 | Content package |
| `technical.cwv_issue` | Technical | Decision → Executor | P0 | URL, CWV metrics |
| `technical.self_heal` | Technical | Executor | P1 | Issue type, fix data |
| `alert.rank_drop` | Scout | Decision | P0 | Keyword, drop amount, engine |
| `alert.rank_gain` | Scout | Decision | P2 | Keyword, gain amount |
| `backlink.verified` | Outreach | Decision | P1 | Campaign, link details |
| `outreach.reply_received` | Outreach | Decision | P0 | Campaign, reply sentiment |
| `competitor.keyword_threat` | Competitor | Decision | P1 | Competitor, keywords, pages |
| `action.completed` | Executor | All | P2 | Action result |
| `action.failed` | Executor | Decision | P1 | Action error |

### 10.2 Redis Streams Configuration

```
Stream: seo:agent:events
Max Length: 100,000 messages
Consumer Groups:
  - sentinel     (reads: crawl.*, issue.*)
  - forge        (reads: content.*, rank_drop → trigger audit)
  - technical    (reads: cwv.*, technical.*)
  - scout        (reads: rank.*, serp.*)
  - outreach     (reads: backlink.*, outreach.*)
  - competitor   (reads: competitor.*)
  - decision     (reads: ALL events)
  - executor     (reads: action.*)
```

---

## 11. Shared Infrastructure

### 11.1 API Gateway & Rate Limiter

```python
class APIGateway:
    """Centralized API management with rate limiting, circuit breaking, and quota tracking."""

    def __init__(self):
        self.rate_limiters = {}  # Per-API token bucket rate limiters
        self.circuit_breakers = {}  # Per-API circuit breaker state
        self.quota_tracker = QuotaTracker()  # Tracks daily/monthly usage

    async def call(self, api: str, method: str, endpoint: str, **kwargs) -> dict:
        # 1. Check circuit breaker
        if self.circuit_breakers[api].is_open:
            raise CircuitOpenError(f"Circuit breaker open for {api}")

        # 2. Check rate limit
        await self.rate_limiters[api].acquire()

        # 3. Check quota
        if not self.quota_tracker.has_remaining(api):
            raise QuotaExhaustedError(f"Daily quota exhausted for {api}")

        # 4. Execute
        try:
            response = await self._execute(api, method, endpoint, **kwargs)
            self.quota_tracker.record(api)
            self.circuit_breakers[api].record_success()
            return response
        except Exception as e:
            self.circuit_breakers[api].record_failure()
            raise
```

### 11.2 Dead Letter Queue

```yaml
dead_letter_queues:
  sentinel:dlq:
    max_size: 10000
    ttl_days: 30
    reprocess_schedule: "every_6_hours"
    alert_threshold: 100

  forge:dlq:
    max_size: 5000
    ttl_days: 14
    reprocess_schedule: "every_12_hours"
    alert_threshold: 50

  technical:dlq:
    max_size: 5000
    ttl_days: 14
    reprocess_schedule: "every_6_hours"
    alert_threshold: 50

  scout:dlq:
    max_size: 5000
    ttl_days: 14
    reprocess_schedule: "every_12_hours"
    alert_threshold: 50

  outreach:dlq:
    max_size: 5000
    ttl_days: 90
    reprocess_schedule: "every_6_hours"
    alert_threshold: 50

  competitor:dlq:
    max_size: 2000
    ttl_days: 30
    reprocess_schedule: "daily"
    alert_threshold: 25

  executor:dlq:
    max_size: 5000
    ttl_days: 30
    reprocess_schedule: "every_6_hours"
    alert_threshold: 50
```

---

## 12. Deployment & Operations

### 12.1 Container Architecture

```yaml
# docker-compose.yml (production)
services:
  sentinel:
    image: seo-platform/sentinel:latest
    deploy:
      resources:
        limits: { cpus: "2.0", memory: "2G" }
    environment:
      - REDIS_URL=redis://redis:6379
      - POSTGRES_URL=postgresql://db:5432/seo
    restart: unless-stopped

  forge:
    image: seo-platform/forge:latest
    deploy:
      resources:
        limits: { cpus: "4.0", memory: "4G" }
    restart: unless-stopped

  technical:
    image: seo-platform/technical:latest
    deploy:
      resources:
        limits: { cpus: "2.0", memory: "2G" }
    restart: unless-stopped

  scout:
    image: seo-platform/scout:latest
    deploy:
      resources:
        limits: { cpus: "2.0", memory: "1G" }
    restart: unless-stopped

  outreach:
    image: seo-platform/outreach:latest
    deploy:
      resources:
        limits: { cpus: "4.0", memory: "4G" }
    restart: unless-stopped

  competitor:
    image: seo-platform/competitor:latest
    deploy:
      resources:
        limits: { cpus: "2.0", memory: "2G" }
    restart: unless-stopped

  decision:
    image: seo-platform/decision:latest
    deploy:
      resources:
        limits: { cpus: "2.0", memory: "2G" }
    restart: unless-stopped

  executor:
    image: seo-platform/executor:latest
    deploy:
      resources:
        limits: { cpus: "2.0", memory: "2G" }
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis-data:/data

  postgres:
    image: postgres:16-alpine
    volumes:
      - pg-data:/var/lib/postgresql/data
```

### 12.2 Health Checks

```yaml
health_checks:
  sentinel:
    endpoint: /health
    interval: 30s
    timeout: 5s
    checks:
      - redis_connected
      - gsc_auth_valid
      - crawl_queue_healthy

  outreach:
    endpoint: /health
    interval: 30s
    timeout: 5s
    checks:
      - redis_connected
      - gmail_oauth_valid
      - campaign_db_connected

  decision:
    endpoint: /health
    interval: 15s
    timeout: 5s
    checks:
      - redis_connected
      - all_agents_reachable
      - budget_tracker_healthy
```

### 12.3 Observability Stack

```yaml
observability:
  metrics:
    type: prometheus
    port: 9090
    path: /metrics

  logging:
    type: structured_json
    level: INFO
    outputs: [stdout, elasticsearch]
    format:
      timestamp: ISO-8601
      agent: string
      action: string
      duration_ms: integer
      status: string

  tracing:
    type: opentelemetry
    exporter: otlp
    endpoint: http://jaeger:4317
    sample_rate: 0.1  # 10% in production

  alerting:
    type: alertmanager
    channels:
      - slack: "#seo-critical"
      - email: "oncall@company.com"
      - pagerduty: "${PAGERDUTY_KEY}"
```

---

*End of Agent System Specification*
