"""
SentinelAgent (Crawler) -- Multi-engine crawl, broken link detection,
index status monitoring, sitemap parsing, and robots.txt analysis.

Spec: docs/04-agent-system.md section 2
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from app.agents.base import AgentPriority, AgentState, BaseAgent, RetryPolicy

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class CrawlResult:
    """Result of crawling a single URL."""
    url: str
    status_code: int = 0
    final_url: str = ""
    content_type: str = ""
    response_time_ms: int = 0
    page_title: str = ""
    meta_description: str = ""
    h1: str = ""
    canonical_url: str = ""
    robots_meta: str = ""
    redirect_chain: list[str] = field(default_factory=list)
    broken_links: list[dict[str, Any]] = field(default_factory=list)
    internal_links: list[str] = field(default_factory=list)
    external_links: list[str] = field(default_factory=list)
    images_without_alt: int = 0
    has_schema: bool = False
    has_sitemap_reference: bool = False
    parent_url: str = ""
    depth: int = 0
    error: str = ""
    robots_blocked: bool = False
    crawled_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status_code": self.status_code,
            "final_url": self.final_url,
            "content_type": self.content_type,
            "response_time_ms": self.response_time_ms,
            "page_title": self.page_title,
            "meta_description": self.meta_description,
            "h1": self.h1,
            "canonical_url": self.canonical_url,
            "redirect_chain": self.redirect_chain,
            "broken_links_count": len(self.broken_links),
            "internal_links_count": len(self.internal_links),
            "external_links_count": len(self.external_links),
            "images_without_alt": self.images_without_alt,
            "has_schema": self.has_schema,
            "robots_blocked": self.robots_blocked,
            "error": self.error,
            "crawled_at": self.crawled_at,
        }


@dataclass
class CrawlReport:
    """Aggregated crawl report for a full or incremental crawl."""
    domain: str
    crawl_type: str = "full"       # full | incremental
    total_urls: int = 0
    successful: int = 0
    broken_links: list[dict[str, Any]] = field(default_factory=list)
    not_indexed: list[str] = field(default_factory=list)
    new_urls: list[str] = field(default_factory=list)
    robots_blocked: list[str] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "crawl_type": self.crawl_type,
            "total_urls": self.total_urls,
            "successful": self.successful,
            "broken_links_count": len(self.broken_links),
            "broken_links": self.broken_links,
            "not_indexed_count": len(self.not_indexed),
            "robots_blocked_count": len(self.robots_blocked),
            "new_urls_count": len(self.new_urls),
            "errors_count": len(self.errors),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds,
        }


# ---------------------------------------------------------------------------
# URL Frontier (priority queue with dedup)
# ---------------------------------------------------------------------------

class URLFrontier:
    """Priority queue for URLs with deduplication and depth tracking."""

    def __init__(self, max_urls: int = 500_000):
        self._queue: list[tuple[int, str, int]] = []  # (priority, url, depth)
        self._seen: set[str] = set()
        self._max_urls = max_urls

    def add(self, url: str, depth: int = 0, priority: int = 5) -> bool:
        """Add URL to frontier. Returns False if already seen or limit reached."""
        normalized = self._normalize(url)
        if normalized in self._seen or len(self._seen) >= self._max_urls:
            return False
        self._seen.add(normalized)
        self._queue.append((priority, url, depth))
        self._queue.sort(key=lambda x: (x[0], x[2]))   # priority ASC, depth ASC
        return True

    def next_batch(self, size: int = 5) -> list[tuple[str, int]]:
        """Get next batch of (url, depth) tuples."""
        batch = []
        for _ in range(min(size, len(self._queue))):
            _, url, depth = self._queue.pop(0)
            batch.append((url, depth))
        return batch

    @property
    def has_next(self) -> bool:
        return len(self._queue) > 0

    @property
    def size(self) -> int:
        return len(self._queue)

    @staticmethod
    def _normalize(url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


# ---------------------------------------------------------------------------
# Domain Rate Limiter
# ---------------------------------------------------------------------------

class DomainRateLimiter:
    """Per-domain token-bucket rate limiter."""

    def __init__(self, default_rps: float = 2.0, default_burst: int = 5):
        self._default_rps = default_rps
        self._default_burst = default_burst
        self._buckets: dict[str, dict[str, Any]] = {}

    def _get_bucket(self, domain: str) -> dict[str, Any]:
        if domain not in self._buckets:
            self._buckets[domain] = {
                "tokens": float(self._default_burst),
                "max_tokens": float(self._default_burst),
                "rps": self._default_rps,
                "last_refill": time.monotonic(),
            }
        return self._buckets[domain]

    async def acquire(self, domain: str) -> float:
        """Wait until a token is available. Returns wait time in seconds."""
        bucket = self._get_bucket(domain)
        now = time.monotonic()
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            bucket["max_tokens"],
            bucket["tokens"] + elapsed * bucket["rps"],
        )
        bucket["last_refill"] = now

        if bucket["tokens"] < 1.0:
            wait_time = (1.0 - bucket["tokens"]) / bucket["rps"]
            await asyncio.sleep(wait_time)
            bucket["tokens"] = 0.0
            return wait_time

        bucket["tokens"] -= 1.0
        return 0.0


# ---------------------------------------------------------------------------
# Robots.txt Parser
# ---------------------------------------------------------------------------

class RobotsParser:
    """Parse and cache robots.txt for a domain."""

    def __init__(self):
        self._parsers: dict[str, RobotFileParser] = {}
        self._hashes: dict[str, str] = {}

    async def fetch_and_parse(self, domain: str, client: httpx.AsyncClient) -> dict[str, Any]:
        """Fetch and parse robots.txt. Returns analysis."""
        robots_url = f"https://{domain}/robots.txt"
        try:
            resp = await client.get(robots_url, timeout=15)
            content = resp.text if resp.status_code == 200 else ""
        except Exception:
            content = ""

        content_hash = hashlib.sha256(content.encode()).hexdigest()
        hash_changed = domain in self._hashes and self._hashes[domain] != content_hash
        self._hashes[domain] = content_hash

        parser = RobotFileParser()
        parser.parse(content.splitlines())
        self._parsers[domain] = parser

        sitemap_urls = re.findall(r"Sitemap:\s*(.+)", content, re.IGNORECASE)

        return {
            "domain": domain,
            "robots_url": robots_url,
            "content_hash": content_hash,
            "hash_changed": hash_changed,
            "sitemap_urls": sitemap_urls,
            "crawl_delay": self._extract_crawl_delay(content),
            "disallowed_paths": self._extract_disallowed(content),
        }

    def is_allowed(self, domain: str, url: str, user_agent: str = "*") -> bool:
        """Check if URL is allowed by robots.txt."""
        parser = self._parsers.get(domain)
        if parser is None:
            return True
        return parser.can_fetch(user_agent, url)

    @staticmethod
    def _extract_crawl_delay(content: str) -> float | None:
        match = re.search(r"Crawl-delay:\s*(\d+\.?\d*)", content, re.IGNORECASE)
        return float(match.group(1)) if match else None

    @staticmethod
    def _extract_disallowed(content: str) -> list[str]:
        return re.findall(r"Disallow:\s*(.+)", content, re.IGNORECASE)


# ---------------------------------------------------------------------------
# Sitemap Manager
# ---------------------------------------------------------------------------

class SitemapManager:
    """Parse XML sitemaps and extract URLs."""

    async def parse_sitemap(
        self, sitemap_url: str, client: httpx.AsyncClient, max_urls: int = 50_000
    ) -> list[dict[str, Any]]:
        """Parse a sitemap URL, handling sitemap indexes recursively."""
        urls: list[dict[str, Any]] = []
        try:
            resp = await client.get(sitemap_url, timeout=30)
            if resp.status_code != 200:
                return urls
            content = resp.text
        except Exception as exc:
            logger.warning("Failed to fetch sitemap %s: %s", sitemap_url, exc)
            return urls

        soup = BeautifulSoup(content, "lxml-xml")

        # Check if this is a sitemap index
        sitemap_tags = soup.find_all("sitemap")
        if sitemap_tags:
            for tag in sitemap_tags[:100]:   # Limit recursive depth
                loc = tag.find("loc")
                if loc and loc.text:
                    child_urls = await self.parse_sitemap(loc.text.strip(), client, max_urls - len(urls))
                    urls.extend(child_urls)
                    if len(urls) >= max_urls:
                        break
            return urls

        # Regular sitemap
        for url_tag in soup.find_all("url"):
            if len(urls) >= max_urls:
                break
            loc = url_tag.find("loc")
            if not loc or not loc.text:
                continue
            entry: dict[str, Any] = {"loc": loc.text.strip()}
            lastmod = url_tag.find("lastmod")
            if lastmod and lastmod.text:
                entry["lastmod"] = lastmod.text.strip()
            changefreq = url_tag.find("changefreq")
            if changefreq and changefreq.text:
                entry["changefreq"] = changefreq.text.strip()
            priority = url_tag.find("priority")
            if priority and priority.text:
                try:
                    entry["priority"] = float(priority.text.strip())
                except ValueError:
                    pass
            urls.append(entry)

        return urls


# ---------------------------------------------------------------------------
# Broken Link Detector
# ---------------------------------------------------------------------------

class BrokenLinkDetector:
    """Detect and classify broken links with redirect chain tracking."""

    async def check_url(
        self, url: str, client: httpx.AsyncClient, timeout: int = 10
    ) -> dict[str, Any]:
        """Check a single URL and return status details."""
        try:
            resp = await client.head(url, follow_redirects=True, timeout=timeout)
            return {
                "url": url,
                "status_code": resp.status_code,
                "final_url": str(resp.url),
                "redirect_chain": [str(r.url) for r in resp.history],
                "content_type": resp.headers.get("content-type", ""),
                "is_broken": resp.status_code >= 400,
            }
        except httpx.TimeoutException:
            return {"url": url, "status_code": 0, "error": "timeout", "is_broken": True}
        except httpx.TooManyRedirects:
            return {"url": url, "status_code": 0, "error": "too_many_redirects", "is_broken": True}
        except Exception as exc:
            return {"url": url, "status_code": 0, "error": str(exc), "is_broken": True}

    async def check_batch(
        self, urls: list[str], client: httpx.AsyncClient, concurrency: int = 10
    ) -> list[dict[str, Any]]:
        """Check a batch of URLs concurrently."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _check(url: str) -> dict[str, Any]:
            async with semaphore:
                return await self.check_url(url, client)

        tasks = [_check(url) for url in urls]
        return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Index Status Monitor
# ---------------------------------------------------------------------------

class IndexStatusMonitor:
    """Check URL index status across Google, Bing, Yandex, Naver."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    async def check_google_index(
        self, site_url: str, url: str, client: httpx.AsyncClient, token: str
    ) -> dict[str, Any]:
        """POST GSC URL Inspection API."""
        encoded_site = site_url.replace("/", "%2F")
        endpoint = (
            f"https://searchconsole.googleapis.com/webmasters/v3/"
            f"sites/{encoded_site}/urlInspection/index:inspect"
        )
        try:
            resp = await client.post(
                endpoint,
                headers={"Authorization": f"Bearer {token}"},
                json={"inspectionUrl": url, "siteUrl": site_url},
                timeout=30,
            )
            data = resp.json()
            result = data.get("inspectionResult", {}).get("indexStatusResult", {})
            return {
                "engine": "google",
                "url": url,
                "verdict": result.get("verdict", "UNKNOWN"),
                "coverage_state": result.get("coverageState", ""),
                "last_crawl_time": result.get("lastCrawlTime", ""),
                "indexed": result.get("verdict") == "PASS",
            }
        except Exception as exc:
            return {"engine": "google", "url": url, "error": str(exc), "indexed": None}

    async def check_bing_index(
        self, site_url: str, url: str, client: httpx.AsyncClient, api_key: str
    ) -> dict[str, Any]:
        """GET Bing Webmaster API GetUrlDetails."""
        try:
            resp = await client.get(
                "https://ssl.bing.com/webmaster/api.svc/json/GetUrlDetails",
                params={"apikey": api_key, "siteUrl": site_url, "url": url},
                timeout=15,
            )
            data = resp.json().get("d", {})
            return {
                "engine": "bing",
                "url": url,
                "indexed": data.get("IsIndexed", False),
                "last_crawl": data.get("LastCrawled", ""),
            }
        except Exception as exc:
            return {"engine": "bing", "url": url, "error": str(exc), "indexed": None}

    async def check_yandex_index(
        self, host_id: str, url: str, client: httpx.AsyncClient, token: str, user_id: str
    ) -> dict[str, Any]:
        """GET Yandex Webmaster API URL info."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()
        try:
            resp = await client.get(
                f"https://api.webmaster.yandex.net/v4/user/{user_id}/hosts/{host_id}/urls/{url_hash}/",
                headers={"Authorization": f"OAuth {token}"},
                timeout=15,
            )
            return {"engine": "yandex", "url": url, "data": resp.json()}
        except Exception as exc:
            return {"engine": "yandex", "url": url, "error": str(exc), "indexed": None}

    async def check_naver_index(
        self, site_id: str, url: str, client: httpx.AsyncClient, token: str
    ) -> dict[str, Any]:
        """GET Naver SearchAdvisor URL inspection."""
        try:
            resp = await client.get(
                f"https://searchadvisor.naver.com/api/v1/sites/{site_id}/urls/inspect",
                params={"url": url},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15,
            )
            return {"engine": "naver", "url": url, "data": resp.json()}
        except Exception as exc:
            return {"engine": "naver", "url": url, "error": str(exc), "indexed": None}

    async def check_all_engines(
        self, site_url: str, urls: list[str], client: httpx.AsyncClient, engine_config: dict[str, Any]
    ) -> dict[str, list[dict[str, Any]]]:
        """Check index status across all enabled engines."""
        results: dict[str, list[dict[str, Any]]] = {}

        engines = engine_config.get("engines", {})
        tasks = []

        for url in urls:
            if engines.get("google", {}).get("enabled"):
                tasks.append(self.check_google_index(
                    site_url, url, client, engine_config.get("gsc_token", "")
                ))
            if engines.get("bing", {}).get("enabled"):
                tasks.append(self.check_bing_index(
                    site_url, url, client, engine_config.get("bing_api_key", "")
                ))
            if engines.get("yandex", {}).get("enabled"):
                tasks.append(self.check_yandex_index(
                    engine_config.get("yandex_host_id", ""),
                    url, client,
                    engine_config.get("yandex_token", ""),
                    engine_config.get("yandex_user_id", ""),
                ))
            if engines.get("naver", {}).get("enabled"):
                tasks.append(self.check_naver_index(
                    engine_config.get("naver_site_id", ""),
                    url, client,
                    engine_config.get("naver_token", ""),
                ))

        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in all_results:
            if isinstance(result, Exception):
                logger.warning("Index check exception: %s", result)
                continue
            engine = result.get("engine", "unknown")
            results.setdefault(engine, []).append(result)

        return results


# ---------------------------------------------------------------------------
# HTML Analysis Utilities
# ---------------------------------------------------------------------------

def extract_page_data(html: str, url: str) -> dict[str, Any]:
    """Extract SEO-relevant data from HTML content."""
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_desc = meta_desc_tag.get("content", "") if meta_desc_tag else ""

    # H1
    h1_tag = soup.find("h1")
    h1 = h1_tag.get_text(strip=True) if h1_tag else ""

    # Canonical
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical = canonical_tag.get("href", "") if canonical_tag else ""

    # Robots meta
    robots_tag = soup.find("meta", attrs={"name": "robots"})
    robots_meta = robots_tag.get("content", "") if robots_tag else ""

    # Schema markup detection
    schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    has_schema = len(schema_scripts) > 0

    # Links
    internal_links = []
    external_links = []
    parsed_base = urlparse(url)
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full_url = urljoin(url, href)
        parsed_link = urlparse(full_url)
        if parsed_link.netloc == parsed_base.netloc:
            internal_links.append(full_url)
        elif parsed_link.scheme in ("http", "https"):
            external_links.append(full_url)

    # Images without alt
    images = soup.find_all("img")
    images_without_alt = sum(1 for img in images if not img.get("alt", "").strip())

    return {
        "title": title,
        "meta_description": meta_desc,
        "h1": h1,
        "canonical_url": canonical,
        "robots_meta": robots_meta,
        "has_schema": has_schema,
        "internal_links": internal_links,
        "external_links": external_links,
        "images_without_alt": images_without_alt,
    }


# ---------------------------------------------------------------------------
# Sentinel Agent (Crawler)
# ---------------------------------------------------------------------------

class SentinelAgent(BaseAgent):
    """
    Crawl Agent (Sentinel) -- monitors indexability, broken links, sitemaps.

    State machine: IDLE -> CRAWLING -> ANALYZING -> REPORTING -> WAITING -> IDLE
    """

    agent_name: str = "sentinel"

    transitions: dict[AgentState, dict[str, AgentState]] = {
        AgentState.IDLE:        {"start_crawl": AgentState.WORKING},
        AgentState.WORKING:     {"crawl_complete": AgentState.ANALYZING, "crawl_failed": AgentState.ERROR},
        AgentState.ANALYZING:   {"analysis_complete": AgentState.REPORTING},
        AgentState.REPORTING:   {"report_sent": AgentState.WAITING},
        AgentState.WAITING:     {"interval_elapsed": AgentState.IDLE, "priority_override": AgentState.WORKING},
        AgentState.ERROR:       {"retry": AgentState.WORKING, "max_retries": AgentState.DEAD_LETTER},
    }

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.frontier = URLFrontier(max_urls=self.config.get("max_urls_per_domain", 500_000))
        self.rate_limiter = DomainRateLimiter(
            default_rps=self.config.get("default_rps", 2.0),
            default_burst=self.config.get("default_burst", 5),
        )
        self.robots_parser = RobotsParser()
        self.sitemap_mgr = SitemapManager()
        self.link_checker = BrokenLinkDetector()
        self.index_monitor = IndexStatusMonitor(self.config)

    def get_triggers(self) -> list[dict[str, Any]]:
        return [
            {"type": "scheduled", "condition": "full_site_crawl", "priority": "P2", "cron": "0 2 * * *"},
            {"type": "scheduled", "condition": "incremental_crawl", "priority": "P2", "cron": "0 */6 * * *"},
            {"type": "event", "condition": "sitemap_change_detected", "priority": "P1"},
            {"type": "event", "condition": "sitemap_submission_requested", "priority": "P1"},
            {"type": "proactive", "condition": "404_rate_exceeds_5_percent", "priority": "P0"},
            {"type": "proactive", "condition": "gsc_crawl_errors_spike", "priority": "P0"},
            {"type": "proactive", "condition": "robots_txt_hash_changed", "priority": "P1"},
        ]

    async def execute(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Execute a crawl task.

        task_payload keys:
            domain: str             -- target domain (required)
            crawl_type: str         -- "full" | "incremental" (default: "full")
            max_urls: int           -- max URLs to crawl (default: 50000)
            urls: list[str]         -- specific URLs for incremental crawl
        """
        domain = task_payload["domain"]
        crawl_type = task_payload.get("crawl_type", "full")
        max_urls = task_payload.get("max_urls", 50_000)

        self.transition("start_crawl")
        started_at = datetime.now(timezone.utc)

        report = CrawlReport(domain=domain, crawl_type=crawl_type, started_at=started_at.isoformat())

        async with httpx.AsyncClient(
            headers={"User-Agent": self.config.get("user_agent", "ProActiveSEO-Sentinel/1.0")},
            follow_redirects=False,
            timeout=30,
        ) as client:
            # 1. Robots.txt analysis
            robots_info = await self.robots_parser.fetch_and_parse(domain, client)
            logger.info("[%s] Robots.txt parsed: %d sitemaps found", self.agent_name, len(robots_info["sitemap_urls"]))

            if robots_info["hash_changed"]:
                await self.emit_event(
                    "sentinel.robots_txt_changed",
                    robots_info,
                    priority=AgentPriority.P1,
                )

            # 2. Sitemap discovery
            sitemap_urls = robots_info.get("sitemap_urls", [])
            all_urls: list[dict[str, Any]] = []
            for sitemap_url in sitemap_urls:
                urls = await self.sitemap_mgr.parse_sitemap(sitemap_url, client, max_urls=max_urls)
                all_urls.extend(urls)

            logger.info("[%s] Discovered %d URLs from sitemaps", self.agent_name, len(all_urls))

            # 3. URL frontier setup
            if crawl_type == "full":
                for entry in all_urls:
                    self.frontier.add(entry["loc"], depth=0, priority=2)
            else:
                # Incremental: only provided URLs or recent changes
                urls_to_crawl = task_payload.get("urls", [])
                if not urls_to_crawl:
                    urls_to_crawl = [
                        e["loc"] for e in all_urls
                        if e.get("lastmod", "") >= (datetime.now(timezone.utc).strftime("%Y-%m-%d"))
                    ]
                for url in urls_to_crawl:
                    self.frontier.add(url, depth=0, priority=1)

            # Also add homepage
            self.frontier.add(f"https://{domain}/", depth=0, priority=0)

            # 4. Crawl loop
            results: list[CrawlResult] = []
            burst = self.config.get("default_burst", 5)
            known_urls: set[str] = {e["loc"] for e in all_urls}

            while self.frontier.has_next and len(results) < max_urls:
                batch = self.frontier.next_batch(size=burst)

                for url, depth in batch:
                    # Rate limiting
                    parsed = urlparse(url)
                    await self.rate_limiter.acquire(parsed.netloc)

                    # Robots check
                    if not self.robots_parser.is_allowed(domain, url):
                        result = CrawlResult(
                            url=url, robots_blocked=True,
                            crawled_at=datetime.now(timezone.utc).isoformat(),
                        )
                        results.append(result)
                        report.robots_blocked.append(url)
                        continue

                    # Crawl
                    result = await self._crawl_url(url, depth, client)
                    results.append(result)

                    # Broken link detection
                    if result.status_code >= 400:
                        report.broken_links.append({
                            "url": url,
                            "status_code": result.status_code,
                            "parent_url": result.parent_url,
                            "auto_fixable": result.status_code == 404,
                        })
                        await self.emit_event(
                            "sentinel.broken_link_detected",
                            {
                                "url": url,
                                "status": result.status_code,
                                "referrer": result.parent_url,
                                "auto_fixable": result.status_code == 404,
                            },
                            priority=AgentPriority.P1,
                        )

                    # New URL discovery
                    if url not in known_urls:
                        report.new_urls.append(url)
                        known_urls.add(url)

                    # Add internal links to frontier
                    if depth < self.config.get("max_depth", 10):
                        for link in result.internal_links:
                            self.frontier.add(link, depth=depth + 1, priority=depth + 3)

            report.total_urls = len(results)
            report.successful = sum(1 for r in results if 200 <= r.status_code < 400)

        # 5. Index status check
        engine_config = self.config.get("engines", {})
        top_urls = [r.url for r in results if r.status_code == 200][:100]

        if top_urls:
            async with httpx.AsyncClient(timeout=30) as idx_client:
                index_results = await self.index_monitor.check_all_engines(
                    f"https://{domain}", top_urls, idx_client, engine_config
                )
                for engine, checks in index_results.items():
                    for check in checks:
                        if check.get("indexed") is False:
                            report.not_indexed.append(check["url"])

        self.transition("crawl_complete")
        self.transition("analysis_complete")

        # 6. Finalize report
        finished_at = datetime.now(timezone.utc)
        report.finished_at = finished_at.isoformat()
        report.duration_seconds = (finished_at - started_at).total_seconds()
        report.errors = [{"url": r.url, "error": r.error} for r in results if r.error]

        self.transition("report_sent")

        logger.info(
            "[%s] Crawl complete: %d URLs, %d broken, %d not indexed, %.1fs",
            self.agent_name, report.total_urls, len(report.broken_links),
            len(report.not_indexed), report.duration_seconds,
        )

        return report.to_dict()

    # -- Internal helpers -------------------------------------------------

    async def _crawl_url(
        self, url: str, depth: int, client: httpx.AsyncClient
    ) -> CrawlResult:
        """Crawl a single URL and extract page data."""
        start = time.monotonic()
        result = CrawlResult(
            url=url,
            depth=depth,
            crawled_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            resp = await client.get(url, timeout=self.config.get("request_timeout", 30))
            elapsed_ms = int((time.monotonic() - start) * 1000)

            result.status_code = resp.status_code
            result.final_url = str(resp.url)
            result.content_type = resp.headers.get("content-type", "")
            result.response_time_ms = elapsed_ms
            result.redirect_chain = [str(r.url) for r in resp.history]

            # Parse HTML for 2xx responses with text/html content
            if 200 <= resp.status_code < 400 and "text/html" in result.content_type:
                page_data = extract_page_data(resp.text, url)
                result.page_title = page_data["title"]
                result.meta_description = page_data["meta_description"]
                result.h1 = page_data["h1"]
                result.canonical_url = page_data["canonical_url"]
                result.robots_meta = page_data["robots_meta"]
                result.has_schema = page_data["has_schema"]
                result.internal_links = page_data["internal_links"]
                result.external_links = page_data["external_links"]
                result.images_without_alt = page_data["images_without_alt"]

        except httpx.TimeoutException:
            result.error = "timeout"
        except Exception as exc:
            result.error = str(exc)[:200]

        return result
