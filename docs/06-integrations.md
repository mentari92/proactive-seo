# 06 — Integration Layer Specification

> Enterprise-grade SEO platform: every external API integration with auth, rate limiting, error handling, caching, retries, and production-ready Python code.

---

## Table of Contents

1. [Integration Architecture Overview](#1-integration-architecture-overview)
2. [Shared Infrastructure](#2-shared-infrastructure)
3. [Google Search Console](#3-google-search-console)
4. [Google Analytics 4](#4-google-analytics-4)
5. [Bing Webmaster Tools](#5-bing-webmaster-tools)
6. [Yandex Webmaster](#6-yandex-webmaster)
7. [Naver Webmaster](#7-naver-webmaster)
8. [Gmail API (Outreach Execution)](#8-gmail-api-outreach-execution)
9. [Exa AI](#9-exa-ai)
10. [Tavily](#10-tavily)
11. [SerpAPI](#11-serpapi)
12. [Ahrefs API](#12-ahrefs-api)
13. [PageSpeed Insights API](#13-pagespeed-insights-api)
14. [CMS Integrations](#14-cms-integrations)
15. [Notification Integrations](#15-notification-integrations)

---

## 1. Integration Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTEGRATION LAYER                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  Auth Manager │  │ Rate Limiter │  │ Cache Layer  │              │
│  │  - OAuth 2.0  │  │  - Token     │  │  - Redis     │              │
│  │  - API Keys   │  │  - Sliding   │  │  - TTL-based │              │
│  │  - App Pass   │  │  - Per-API   │  │  - Invalidation│            │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘              │
│         │                  │                  │                      │
│  ┌──────▼──────────────────▼──────────────────▼───────┐             │
│  │              HTTP Client (httpx + retries)          │             │
│  └──────┬──────┬──────┬──────┬──────┬──────┬──────────┘             │
│         │      │      │      │      │      │                        │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐          │
│  │GSC│ │GA4│ │BWT│ │Ynd│ │Nvr│ │Gml│ │Exa│ │Tvl│ │Srp│          │
│  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘          │
│  ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐ ┌───┐                      │
│  │Ahr│ │PSI│ │WP │ │WF │ │Shp│ │Slk│ │Dsc│                      │
│  └───┘ └───┘ └───┘ └───┘ └───┘ └───┘ └───┘                      │
│  ┌───┐ ┌───┐                                                      │
│  │SMT│ │Tgm│                                                      │
│  └───┘ └───┘                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Single HTTP Client** | All integrations share one `httpx.AsyncClient` with connection pooling |
| **Uniform Auth** | `AuthManager` handles OAuth tokens, API keys, application passwords |
| **Rate Limiting** | Per-provider token bucket with sliding window |
| **Caching** | Redis-backed with TTL per endpoint; stale-while-revalidate for read-heavy endpoints |
| **Retries** | Exponential backoff with jitter on 429/5xx; configurable per provider |
| **Circuit Breaker** | Trip after N consecutive failures; half-open probe after cooldown |
| **Observability** | Structured logging, Prometheus metrics, OpenTelemetry tracing |

---

## 2. Shared Infrastructure

### 2.1 Base HTTP Client

```python
"""
integrations/base/client.py
Shared HTTP client with retries, circuit breaker, and metrics.
"""

import asyncio
import time
import random
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# --- Metrics ---
REQUEST_COUNT = Counter(
    "integration_requests_total",
    "Total API requests",
    ["provider", "endpoint", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "integration_request_duration_seconds",
    "Request latency",
    ["provider", "endpoint"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)
RETRY_COUNT = Counter(
    "integration_retries_total",
    "Total retries",
    ["provider", "endpoint", "attempt"],
)
CIRCUIT_STATE = Counter(
    "integration_circuit_state_changes_total",
    "Circuit breaker state changes",
    ["provider", "from_state", "to_state"],
)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _half_open_calls: int = field(default=0, repr=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time > self.recovery_timeout:
                self._transition(CircuitState.HALF_OPEN)
        return self._state

    def _transition(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        CIRCUIT_STATE.labels(provider="*", from_state=old.value, to_state=new_state.value).inc()
        logger.info("Circuit breaker: %s -> %s", old.value, new_state.value)

    def record_success(self) -> None:
        if self._state == CircuitState.HALF_OPEN:
            self._transition(CircuitState.CLOSED)
        self._failure_count = 0

    def record_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._transition(CircuitState.OPEN)

    def allow_request(self) -> bool:
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False
        return False


@dataclass
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    retryable_status_codes: tuple = (429, 500, 502, 503, 504)


class IntegrationHTTPClient:
    """Base HTTP client shared by all integrations."""

    def __init__(
        self,
        provider: str,
        base_url: str,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
        timeout: float = 30.0,
    ):
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.retry_config = retry_config or RetryConfig()
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30,
            ),
        )

    async def request(
        self,
        method: str,
        path: str,
        *,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
        data: Optional[dict] = None,
        cache_ttl: Optional[int] = None,
    ) -> httpx.Response:
        """Execute an HTTP request with retries and circuit breaker."""

        if not self.circuit_breaker.allow_request():
            raise CircuitOpenError(f"Circuit breaker OPEN for {self.provider}")

        retry = self.retry_config
        last_exc: Optional[Exception] = None

        for attempt in range(retry.max_retries + 1):
            try:
                start = time.monotonic()
                resp = await self._client.request(
                    method, path, headers=headers, params=params, json=json, data=data,
                )
                latency = time.monotonic() - start

                REQUEST_LATENCY.labels(provider=self.provider, endpoint=path).observe(latency)
                REQUEST_COUNT.labels(
                    provider=self.provider, endpoint=path, status_code=str(resp.status_code),
                ).inc()

                if resp.status_code in retry.retryable_status_codes:
                    if attempt < retry.max_retries:
                        delay = self._compute_delay(attempt, resp)
                        RETRY_COUNT.labels(
                            provider=self.provider, endpoint=path, attempt=str(attempt + 1),
                        ).inc()
                        logger.warning(
                            "%s %s returned %d, retry %d/%d in %.1fs",
                            method, path, resp.status_code, attempt + 1, retry.max_retries, delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        self.circuit_breaker.record_failure()
                        resp.raise_for_status()

                self.circuit_breaker.record_success()
                return resp

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_exc = exc
                if attempt < retry.max_retries:
                    delay = self._compute_delay(attempt)
                    RETRY_COUNT.labels(
                        provider=self.provider, endpoint=path, attempt=str(attempt + 1),
                    ).inc()
                    await asyncio.sleep(delay)
                    continue
                self.circuit_breaker.record_failure()
                raise

        raise IntegrationError(f"All {retry.max_retries} retries exhausted for {self.provider}") from last_exc

    def _compute_delay(self, attempt: int, resp: Optional[httpx.Response] = None) -> float:
        """Exponential backoff with jitter. Respects Retry-After header."""
        if resp is not None:
            retry_after = resp.headers.get("Retry-After")
            if retry_after:
                try:
                    return min(float(retry_after), self.retry_config.max_delay)
                except ValueError:
                    pass

        delay = min(
            self.retry_config.base_delay * (self.retry_config.backoff_factor ** attempt),
            self.retry_config.max_delay,
        )
        if self.retry_config.jitter:
            delay *= 0.5 + random.random() * 0.5
        return delay

    async def close(self) -> None:
        await self._client.aclose()


class IntegrationError(Exception):
    """Base exception for all integration errors."""

class CircuitOpenError(IntegrationError):
    """Circuit breaker is open."""

class AuthError(IntegrationError):
    """Authentication/authorization failure."""

class RateLimitError(IntegrationError):
    """Rate limit exceeded and retries exhausted."""

class DataNotFoundError(IntegrationError):
    """Requested data does not exist."""
```

### 2.2 Auth Manager

```python
"""
integrations/base/auth.py
Centralized authentication manager.
"""

import json
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class AuthType(Enum):
    OAUTH2 = "oauth2"
    API_KEY = "api_key"
    APPLICATION_PASSWORD = "application_password"
    BEARER_TOKEN = "bearer_token"


@dataclass
class OAuth2Config:
    client_id: str
    client_secret: str
    token_url: str
    auth_url: str
    scopes: list[str]
    redirect_uri: str = "http://localhost:8080/callback"


@dataclass
class TokenStore:
    """Persistent token storage with refresh."""
    storage_path: Path
    _tokens: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.storage_path.exists():
            self._tokens = json.loads(self.storage_path.read_text())

    def get(self, provider: str) -> Optional[dict]:
        return self._tokens.get(provider)

    def save(self, provider: str, token_data: dict) -> None:
        self._tokens[provider] = token_data
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(json.dumps(self._tokens, indent=2))

    def is_expired(self, provider: str) -> bool:
        token = self.get(provider)
        if not token:
            return True
        return token.get("expires_at", 0) < time.time() + 300  # 5 min buffer


class AuthManager:
    """Central auth manager supporting OAuth2, API keys, and application passwords."""

    def __init__(self, token_store: TokenStore):
        self.token_store = token_store
        self._configs: dict[str, OAuth2Config] = {}

    def register_oauth2(self, provider: str, config: OAuth2Config) -> None:
        self._configs[provider] = config

    def get_authorization_url(self, provider: str, state: str) -> str:
        """Generate OAuth2 authorization URL for user consent."""
        cfg = self._configs[provider]
        params = {
            "client_id": cfg.client_id,
            "redirect_uri": cfg.redirect_uri,
            "response_type": "code",
            "scope": " ".join(cfg.scopes),
            "state": state,
            "access_type": "offline",
            "prompt": "consent",
        }
        from urllib.parse import urlencode
        return f"{cfg.auth_url}?{urlencode(params)}"

    async def exchange_code(self, provider: str, code: str) -> dict:
        """Exchange authorization code for tokens."""
        cfg = self._configs[provider]
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                cfg.token_url,
                data={
                    "code": code,
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                    "redirect_uri": cfg.redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
            resp.raise_for_status()
            token_data = resp.json()
            token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
            self.token_store.save(provider, token_data)
            return token_data

    async def get_access_token(self, provider: str) -> str:
        """Get a valid access token, refreshing if needed."""
        if self.token_store.is_expired(provider):
            await self._refresh_token(provider)
        token = self.token_store.get(provider)
        if not token:
            raise AuthError(f"No token found for {provider}")
        return token["access_token"]

    async def _refresh_token(self, provider: str) -> None:
        """Refresh an expired OAuth2 token."""
        cfg = self._configs[provider]
        token = self.token_store.get(provider)
        if not token or "refresh_token" not in token:
            raise AuthError(f"No refresh token for {provider}; re-authorization required")

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                cfg.token_url,
                data={
                    "refresh_token": token["refresh_token"],
                    "client_id": cfg.client_id,
                    "client_secret": cfg.client_secret,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            new_token = resp.json()
            # Preserve refresh_token if not returned
            if "refresh_token" not in new_token:
                new_token["refresh_token"] = token["refresh_token"]
            new_token["expires_at"] = time.time() + new_token.get("expires_in", 3600)
            self.token_store.save(provider, new_token)
            logger.info("Refreshed token for %s", provider)
```

### 2.3 Rate Limiter

```python
"""
integrations/base/rate_limiter.py
Per-provider sliding window rate limiter backed by Redis.
"""

import time
import asyncio
from dataclasses import dataclass
from typing import Optional

import redis.asyncio as aioredis


@dataclass
class RateLimit:
    requests: int
    window_seconds: int


class SlidingWindowRateLimiter:
    """Redis-backed sliding window rate limiter."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self._limits: dict[str, list[RateLimit]] = {}

    def register(self, provider: str, limits: list[RateLimit]) -> None:
        self._limits[provider] = limits

    async def acquire(self, provider: str) -> None:
        """Block until a request slot is available."""
        limits = self._limits.get(provider, [])
        if not limits:
            return

        while True:
            now = time.time()
            allowed = True

            for limit in limits:
                key = f"ratelimit:{provider}:{limit.window_seconds}"
                window_start = now - limit.window_seconds

                pipe = self.redis.pipeline()
                pipe.zremrangebyscore(key, 0, window_start)
                pipe.zadd(key, {str(now): now})
                pipe.zcard(key)
                pipe.expire(key, limit.window_seconds)
                results = await pipe.execute()

                count = results[2]
                if count > limit.requests:
                    allowed = False
                    # Calculate sleep until oldest entry expires
                    oldest = await self.redis.zrange(key, 0, 0, withscores=True)
                    if oldest:
                        sleep_time = oldest[0][1] + limit.window_seconds - now + 0.1
                        await asyncio.sleep(max(sleep_time, 0.1))
                    break

            if allowed:
                return

    async def get_remaining(self, provider: str) -> dict[str, int]:
        """Get remaining request quota per window."""
        limits = self._limits.get(provider, [])
        result = {}
        for limit in limits:
            key = f"ratelimit:{provider}:{limit.window_seconds}"
            now = time.time()
            await self.redis.zremrangebyscore(key, 0, now - limit.window_seconds)
            count = await self.redis.zcard(key)
            result[f"{limit.window_seconds}s"] = max(0, limit.requests - count)
        return result
```

### 2.4 Cache Layer

```python
"""
integrations/base/cache.py
Redis-backed response cache with TTL and stale-while-revalidate.
"""

import json
import time
import hashlib
import logging
from typing import Optional, Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class ResponseCache:
    """Cache API responses in Redis with TTL and optional stale-while-revalidate."""

    def __init__(self, redis_url: str = "redis://localhost:6379/1", prefix: str = "cache"):
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.prefix = prefix

    def _key(self, provider: str, endpoint: str, params: Optional[dict] = None) -> str:
        param_str = json.dumps(params or {}, sort_keys=True)
        h = hashlib.sha256(f"{provider}:{endpoint}:{param_str}".encode()).hexdigest()[:16]
        return f"{self.prefix}:{provider}:{h}"

    async def get(self, provider: str, endpoint: str, params: Optional[dict] = None) -> Optional[Any]:
        key = self._key(provider, endpoint, params)
        raw = await self.redis.get(key)
        if raw is None:
            return None
        try:
            entry = json.loads(raw)
            return entry.get("data")
        except (json.JSONDecodeError, KeyError):
            return None

    async def set(
        self,
        provider: str,
        endpoint: str,
        data: Any,
        ttl: int = 3600,
        params: Optional[dict] = None,
    ) -> None:
        key = self._key(provider, endpoint, params)
        entry = {
            "data": data,
            "cached_at": time.time(),
            "ttl": ttl,
        }
        await self.redis.set(key, json.dumps(entry), ex=ttl)

    async def invalidate(self, provider: str, endpoint: str, params: Optional[dict] = None) -> None:
        key = self._key(provider, endpoint, params)
        await self.redis.delete(key)

    async def invalidate_provider(self, provider: str) -> int:
        """Invalidate all cached data for a provider."""
        pattern = f"{self.prefix}:{provider}:*"
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        if keys:
            return await self.redis.delete(*keys)
        return 0
```

---

## 3. Google Search Console

### 3.1 Auth Method & Setup

**OAuth 2.0 (Authorization Code Flow)**

| Field | Value |
|-------|-------|
| **Scopes** | `https://www.googleapis.com/auth/webmasters.readonly` (read) or `webmasters` (read/write) |
| **Token URL** | `https://oauth2.googleapis.com/token` |
| **Auth URL** | `https://accounts.google.com/o/oauth2/v2/auth` |
| **Credentials** | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client ID |
| **Consent Screen** | Must be configured; "External" for production, "Internal" for Workspace |

### 3.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /webmasters/v3/sites` | GET | List all verified sites |
| `GET /webmasters/v3/sites/{siteUrl}` | GET | Get site metadata |
| `POST /webmasters/v3/sites/{siteUrl}/searchAnalytics/query` | POST | Search performance data |
| `GET /webmasters/v3/sites/{siteUrl}/sitemaps` | GET | List submitted sitemaps |
| `GET /webmasters/v3/sites/{siteUrl}/sitemaps/{feedpath}` | GET | Get sitemap details |
| `GET /webmasters/v3/sites/{siteUrl}/urlInspection/index:inspect` | POST | Inspect URL index status |

### 3.3 Data Schema

```python
from dataclasses import dataclass
from datetime import date
from typing import Optional


@dataclass
class SearchAnalyticsRow:
    """Row from GSC search analytics query."""
    keys: list[str]              # [query, page, country, device, date]
    clicks: int
    impressions: float
    ctr: float                   # 0.0-1.0
    position: float              # Average position

    @property
    def query(self) -> Optional[str]:
        return self.keys[0] if len(self.keys) > 0 else None

    @property
    def page(self) -> Optional[str]:
        return self.keys[1] if len(self.keys) > 1 else None

    @property
    def country(self) -> Optional[str]:
        return self.keys[2] if len(self.keys) > 2 else None

    @property
    def device(self) -> Optional[str]:
        return self.keys[3] if len(self.keys) > 3 else None

    @property
    def date(self) -> Optional[str]:
        return self.keys[4] if len(self.keys) > 4 else None


@dataclass
class SitemapInfo:
    path: str
    lastSubmitted: Optional[str]
    isPending: bool
    isSitemapsIndex: bool
    type: str                     # "sitemap" or "sitemapIndex"
    lastDownloaded: Optional[str]
    warnings: int
    errors: int


@dataclass
class IndexStatus:
    inspectionResult: dict
    verdict: str                  # "PASS", "FAIL", "NEUTRAL"
    coverageState: str
    robotsTxtState: str
    indexingState: str
    lastCrawlTime: Optional[str]
    pageFetchState: str
    referringUrls: list[str]
```

### 3.4 Rate Limits & Quotas

| Limit | Value |
|-------|-------|
| **Queries per day** | 2,000 (default), can request increase |
| **Queries per minute** | ~10 (unofficial, enforced by 429s) |
| **Rows per query** | 25,000 (default), 100,000 with `rowLimit` |
| **Date range** | Max 16 months of data |
| **Data freshness** | ~2-3 days lag |
| **Bulk export** | Use `startRow` + `rowLimit` pagination |

### 3.5 Error Handling

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| 400 | Invalid request (bad dates, dimensions) | Log + raise `ValidationError` |
| 401 | Token expired/invalid | Trigger token refresh, retry once |
| 403 | Insufficient permissions | Raise `AuthError`, prompt re-consent |
| 404 | Site not found / not verified | Raise `DataNotFoundError` |
| 429 | Rate limit exceeded | Respect `Retry-After`, exponential backoff |
| 500/503 | Server error | Retry with backoff |

### 3.6 Retry Strategy

- **429**: Honor `Retry-After` header; if absent, wait `2^attempt + jitter` seconds
- **5xx**: Exponential backoff, max 3 retries
- **401**: Refresh token, retry once
- **Network errors**: Retry up to 3 times with jitter

### 3.7 Caching Strategy

| Data Type | TTL | Rationale |
|-----------|-----|-----------|
| Search analytics | 6 hours | Data has 2-3 day lag; no real-time benefit |
| Site list | 24 hours | Rarely changes |
| Sitemap list | 12 hours | Changes on sitemap submission |
| Index status | 1 hour | More volatile; recent crawl data |

### 3.8 Python Implementation

```python
"""
integrations/gsc/client.py
Google Search Console API integration.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

import httpx

from integrations.base.client import IntegrationHTTPClient, RetryConfig, IntegrationError
from integrations.base.auth import AuthManager, OAuth2Config, TokenStore
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class GoogleSearchConsoleClient:
    """Production-grade Google Search Console API client."""

    PROVIDER = "gsc"
    BASE_URL = "https://www.googleapis.com/webmasters/v3"

    def __init__(
        self,
        auth_manager: AuthManager,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.auth = auth_manager
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3, base_delay=2.0),
        )

        # Register rate limits
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=10, window_seconds=60),   # ~10/min
            RateLimit(requests=2000, window_seconds=86400),  # 2000/day
        ])

    async def _auth_headers(self) -> dict[str, str]:
        token = await self.auth.get_access_token(self.PROVIDER)
        return {"Authorization": f"Bearer {token}"}

    async def list_sites(self) -> list[dict]:
        """List all verified sites in GSC."""
        cached = await self.cache.get(self.PROVIDER, "sites")
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._auth_headers()
        resp = await self.client.request("GET", "/sites", headers=headers)
        data = resp.json()
        sites = data.get("siteEntry", [])

        await self.cache.set(self.PROVIDER, "sites", sites, ttl=86400)
        return sites

    async def query_search_analytics(
        self,
        site_url: str,
        start_date: date,
        end_date: date,
        dimensions: Optional[list[str]] = None,
        search_type: str = "web",
        row_limit: int = 25000,
        start_row: int = 0,
        aggregation_type: str = "auto",
    ) -> list[dict]:
        """
        Query search analytics data.

        Args:
            site_url: Site URL as registered in GSC (e.g., "sc-domain:example.com")
            start_date: Start date (inclusive). Max 16 months ago.
            end_date: End date (inclusive). Must be at least 3 days ago.
            dimensions: Group by: query, page, country, device, date, searchAppearance
            search_type: web, image, video, news, discover, googleNews
            row_limit: Max 25000 per request
            start_row: Offset for pagination
            aggregation_type: auto, byPage, byProperty

        Returns:
            List of search analytics rows.
        """
        if dimensions is None:
            dimensions = ["query", "page"]

        cache_params = {
            "site": site_url, "start": str(start_date), "end": str(end_date),
            "dims": dimensions, "type": search_type, "limit": row_limit, "offset": start_row,
        }
        cached = await self.cache.get(self.PROVIDER, "search_analytics", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._auth_headers()

        payload = {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "dimensions": dimensions,
            "searchType": search_type,
            "rowLimit": min(row_limit, 25000),
            "startRow": start_row,
            "aggregationType": aggregation_type,
        }

        encoded_site = site_url.replace(":", "%3A")
        resp = await self.client.request(
            "POST",
            f"/sites/{encoded_site}/searchAnalytics/query",
            headers=headers,
            json=payload,
        )
        data = resp.json()
        rows = data.get("rows", [])

        await self.cache.set(self.PROVIDER, "search_analytics", rows, ttl=21600, params=cache_params)
        return rows

    async def get_all_search_analytics(
        self,
        site_url: str,
        start_date: date,
        end_date: date,
        dimensions: Optional[list[str]] = None,
        search_type: str = "web",
        batch_size: int = 25000,
    ) -> list[dict]:
        """Paginate through all search analytics data."""
        all_rows = []
        start_row = 0

        while True:
            rows = await self.query_search_analytics(
                site_url, start_date, end_date,
                dimensions=dimensions,
                search_type=search_type,
                row_limit=batch_size,
                start_row=start_row,
            )
            if not rows:
                break
            all_rows.extend(rows)
            if len(rows) < batch_size:
                break
            start_row += batch_size
            await asyncio.sleep(0.5)  # Gentle pacing

        return all_rows

    async def get_sitemaps(self, site_url: str) -> list[dict]:
        """List all sitemaps for a site."""
        cached = await self.cache.get(self.PROVIDER, "sitemaps", {"site": site_url})
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._auth_headers()
        encoded_site = site_url.replace(":", "%3A")
        resp = await self.client.request("GET", f"/sites/{encoded_site}/sitemaps", headers=headers)
        data = resp.json()
        sitemaps = data.get("sitemap", [])

        await self.cache.set(self.PROVIDER, "sitemaps", sitemaps, ttl=43200, params={"site": site_url})
        return sitemaps

    async def inspect_url(self, site_url: str, inspection_url: str) -> dict:
        """Inspect a URL's index status."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._auth_headers()
        encoded_site = site_url.replace(":", "%3A")

        payload = {
            "inspectionUrl": inspection_url,
            "siteUrl": site_url,
        }
        resp = await self.client.request(
            "POST",
            f"/sites/{encoded_site}/urlInspection/index:inspect",
            headers=headers,
            json=payload,
        )
        return resp.json()

    async def get_crawl_errors(self, site_url: str) -> dict:
        """Get crawl error counts (uses search analytics with page filter)."""
        # GSC API doesn't have a direct crawl-errors endpoint anymore;
        # we approximate via pages with 0 impressions + known error patterns.
        # For comprehensive crawl error data, use the URL Inspection API.
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._auth_headers()
        encoded_site = site_url.replace(":", "%3A")

        resp = await self.client.request("GET", f"/sites/{encoded_site}", headers=headers)
        return resp.json()

    async def close(self) -> None:
        await self.client.close()
```

---

## 4. Google Analytics 4

### 4.1 Auth Method & Setup

**OAuth 2.0 (Authorization Code Flow)**

| Field | Value |
|-------|-------|
| **Scopes** | `https://www.googleapis.com/auth/analytics.readonly` |
| **Token URL** | `https://oauth2.googleapis.com/token` |
| **Auth URL** | `https://accounts.google.com/o/oauth2/v2/auth` |
| **Credentials** | Google Cloud Console → Enable GA4 Data API + Admin API |
| **Property ID** | Numeric GA4 property ID (e.g., `properties/123456789`) |

### 4.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /v1beta/{property}:runReport` | POST | Run a custom report |
| `POST /v1beta/{property}:runRealtimeReport` | POST | Real-time data |
| `GET /v1beta/{property}/metadata` | GET | Available dimensions & metrics |
| `POST /v1beta/{property}:batchRunReports` | POST | Multiple reports in one call |
| `GET /v1beta/accounts` | GET | List accounts |
| `GET /v1beta/{property}/customDimensions` | GET | List custom dimensions |

### 4.3 Data Schema

```python
@dataclass
class GA4Dimension:
    name: str                    # e.g., "sessionSource", "pagePath"
    value: str

@dataclass
class GA4Metric:
    name: str                    # e.g., "sessions", "totalRevenue"
    value: str                   # Always string in API response

@dataclass
class GA4Row:
    dimensions: list[GA4Dimension]
    metrics: list[GA4Metric]

@dataclass
class GA4Report:
    dimension_headers: list[dict]
    metric_headers: list[dict]
    rows: list[GA4Row]
    totals: list[dict]
    row_count: int
    metadata: dict
```

### 4.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Core Reporting API** | 10,000 requests per project per day (default) |
| **Realtime API** | 1,000 requests per project per day |
| **Concurrent requests** | ~10 per property (unofficial) |
| **Rows per request** | 100,000 (with `limit` param) |
| **Date ranges** | Up to 2 date ranges per report |

### 4.5 Python Implementation

```python
"""
integrations/ga4/client.py
Google Analytics 4 Data API integration.
"""

import logging
from datetime import date, timedelta
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.auth import AuthManager
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class GoogleAnalytics4Client:
    """GA4 Data API client."""

    PROVIDER = "ga4"
    BASE_URL = "https://analyticsdata.googleapis.com"

    def __init__(
        self,
        auth_manager: AuthManager,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
        property_id: str,
    ):
        self.auth = auth_manager
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.property_id = property_id  # e.g., "properties/123456789"
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=100, window_seconds=60),
            RateLimit(requests=10000, window_seconds=86400),
        ])

    async def _headers(self) -> dict:
        token = await self.auth.get_access_token(self.PROVIDER)
        return {"Authorization": f"Bearer {token}"}

    async def run_report(
        self,
        dimensions: list[str],
        metrics: list[str],
        start_date: date,
        end_date: date,
        limit: int = 10000,
        offset: int = 0,
        dimension_filter: Optional[dict] = None,
        metric_filter: Optional[dict] = None,
        order_bys: Optional[list[dict]] = None,
    ) -> dict:
        """Run a GA4 report."""

        cache_params = {
            "dims": dimensions, "metrics": metrics,
            "start": str(start_date), "end": str(end_date),
            "limit": limit, "offset": offset,
        }
        cached = await self.cache.get(self.PROVIDER, "report", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        payload = {
            "dateRanges": [{
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
            }],
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "limit": limit,
            "offset": offset,
        }
        if dimension_filter:
            payload["dimensionFilter"] = dimension_filter
        if metric_filter:
            payload["metricFilter"] = metric_filter
        if order_bys:
            payload["orderBys"] = order_bys

        resp = await self.client.request(
            "POST", f"/v1beta/{self.property_id}:runReport",
            headers=headers, json=payload,
        )
        data = resp.json()

        await self.cache.set(self.PROVIDER, "report", data, ttl=3600, params=cache_params)
        return data

    async def run_realtime_report(
        self,
        dimensions: list[str],
        metrics: list[str],
        limit: int = 10000,
    ) -> dict:
        """Get real-time data (last 30 minutes)."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        payload = {
            "dimensions": [{"name": d} for d in dimensions],
            "metrics": [{"name": m} for m in metrics],
            "limit": limit,
        }

        resp = await self.client.request(
            "POST", f"/v1beta/{self.property_id}:runRealtimeReport",
            headers=headers, json=payload,
        )
        return resp.json()

    async def get_seo_traffic_report(
        self,
        start_date: date,
        end_date: date,
    ) -> dict:
        """Pre-built SEO traffic report: source/medium + landing page + conversions."""
        return await self.run_report(
            dimensions=["sessionSource", "sessionMedium", "landingPage"],
            metrics=["sessions", "totalUsers", "newUsers", "conversions",
                     "totalRevenue", "engagementRate", "averageSessionDuration"],
            start_date=start_date,
            end_date=end_date,
        )

    async def get_content_performance(
        self,
        start_date: date,
        end_date: date,
    ) -> dict:
        """Content performance: page path + engagement metrics."""
        return await self.run_report(
            dimensions=["pagePath", "pageTitle"],
            metrics=["screenPageViews", "totalUsers", "averageSessionDuration",
                     "bounceRate", "engagementRate", "eventCount"],
            start_date=start_date,
            end_date=end_date,
            order_bys=[{"metric": {"metricName": "screenPageViews"}, "desc": True}],
        )

    async def close(self) -> None:
        await self.client.close()
```

---

## 5. Bing Webmaster Tools

### 5.1 Auth Method & Setup

**API Key (passed as query parameter)**

| Field | Value |
|-------|-------|
| **Key Location** | Bing Webmaster Tools → Settings → API Access → API Key |
| **Auth Method** | Query parameter `apiKey` on every request |
| **Base URL** | `https://ssl.bing.com/webmaster/api.svc/json` |

### 5.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GetUserSites` | GET | List all verified sites |
| `GetQueryStats` | GET | Search query performance |
| `GetCrawlStats` | GET | Crawl statistics |
| `GetPageStats` | GET | Page-level statistics |
| `GetSitemaps` | GET | Submitted sitemaps |
| `GetUrlSubmissionQuota` | GET | URL submission quota |
| `SubmitUrl` | POST | Submit URL for indexing |
| `SubmitSitemap` | POST | Submit sitemap |

### 5.3 Data Schema

```python
@dataclass
class BingQueryStat:
    Query: str
    Impressions: int
    Clicks: int
    CTR: float
    AvgPosition: float

@dataclass
class BingCrawlStats:
    CrawledUrls: int
    Pages Crawled: int
    CrawlErrors: int
    AverageResponseTime: float

@dataclass
class BingSitemap:
    Url: str
    Type: str              # "Sitemap" or "RSS"
    Submitted: str
    LastChecked: str
    Status: str
    Warnings: int
    Errors: int
```

### 5.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Daily queries** | ~1,000 (undocumented, enforced by 429) |
| **URL submissions** | 10,000/month per site (free tier) |
| **Batch size** | 500 URLs per submission call |

### 5.5 Python Implementation

```python
"""
integrations/bing_webmaster/client.py
Bing Webmaster Tools API integration.
"""

import logging
from datetime import date
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class BingWebmasterClient:
    """Bing Webmaster Tools API client."""

    PROVIDER = "bing_wm"
    BASE_URL = "https://ssl.bing.com/webmaster/api.svc/json"

    def __init__(
        self,
        api_key: str,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=20, window_seconds=60),
            RateLimit(requests=1000, window_seconds=86400),
        ])

    def _params(self, extra: Optional[dict] = None) -> dict:
        p = {"apikey": self.api_key}
        if extra:
            p.update(extra)
        return p

    async def get_user_sites(self) -> list[dict]:
        cached = await self.cache.get(self.PROVIDER, "sites")
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request("GET", "/GetUserSites", params=self._params())
        data = resp.json()
        sites = data.get("d", {}).get("Sites", [])

        await self.cache.set(self.PROVIDER, "sites", sites, ttl=86400)
        return sites

    async def get_query_stats(
        self,
        site_url: str,
        start_date: date,
        end_date: date,
    ) -> list[dict]:
        cached = await self.cache.get(
            self.PROVIDER, "query_stats",
            {"site": site_url, "start": str(start_date), "end": str(end_date)},
        )
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/GetQueryStats",
            params=self._params({
                "siteUrl": site_url,
                "startDate": start_date.strftime("%Y-%m-%dT00:00:00"),
                "endDate": end_date.strftime("%Y-%m-%dT00:00:00"),
            }),
        )
        data = resp.json()
        queries = data.get("d", {}).get("SearchData", [])

        await self.cache.set(
            self.PROVIDER, "query_stats", queries, ttl=21600,
            params={"site": site_url, "start": str(start_date), "end": str(end_date)},
        )
        return queries

    async def get_crawl_stats(self, site_url: str) -> dict:
        cached = await self.cache.get(self.PROVIDER, "crawl_stats", {"site": site_url})
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/GetCrawlStats",
            params=self._params({"siteUrl": site_url}),
        )
        data = resp.json()

        await self.cache.set(self.PROVIDER, "crawl_stats", data, ttl=43200, params={"site": site_url})
        return data

    async def submit_url(self, site_url: str, url: str) -> dict:
        """Submit a single URL for crawling."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/SubmitUrl",
            params=self._params({"siteUrl": site_url, "url": url}),
        )
        return resp.json()

    async def submit_sitemap(self, site_url: str, sitemap_url: str) -> dict:
        """Submit a sitemap."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/SubmitSitemap",
            params=self._params({"siteUrl": site_url, "feedUrl": sitemap_url}),
        )
        return resp.json()

    async def close(self) -> None:
        await self.client.close()
```

---

## 6. Yandex Webmaster

### 6.1 Auth Method & Setup

**OAuth 2.0 (Authorization Code Flow)**

| Field | Value |
|-------|-------|
| **Scopes** | `login:info login:email webmaster:read webmaster:write` |
| **Token URL** | `https://oauth.yandex.com/token` |
| **Auth URL** | `https://oauth.yandex.com/authorize` |
| **Client ID** | Register at `https://oauth.yandex.com/client` |
| **Callback** | Must match registered redirect URI exactly |

### 6.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /v2/user` | GET | Get user info |
| `GET /v2/hosts` | GET | List all hosts |
| `GET /v2/hosts/{hostId}` | GET | Host details |
| `GET /v2/hosts/{hostId}/search/queries` | GET | Search queries |
| `GET /v2/hosts/{hostId}/search/queries/keys/{queryId}/stats` | GET | Query statistics |
| `GET /v2/hosts/{hostId}/crawling` | GET | Crawling statistics |
| `GET /v2/hosts/{hostId}/sitemap` | GET | Sitemap info |
| `POST /v2/hosts/{hostId}/sitemap` | POST | Add sitemap |

### 6.3 Data Schema

```python
@dataclass
class YandexSearchQuery:
    queryId: str
    queryText: str
    impressions: int
    clicks: int
    ctr: float
    position: float

@dataclass
class YandexHost:
    hostId: str
    unicodeUrl: str
    host: str
    verified: bool
```

### 6.4 Rate Limits

| Limit | Value |
|-------|-------|
| **General API** | ~10 requests/second (undocumented) |
| **Search queries** | Max 1000 query IDs per request |
| **Daily requests** | Not published; 429 on excessive use |

### 6.5 Python Implementation

```python
"""
integrations/yandex_webmaster/client.py
Yandex Webmaster API integration.
"""

import logging
from datetime import date
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.auth import AuthManager
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class YandexWebmasterClient:
    """Yandex Webmaster API client."""

    PROVIDER = "yandex_wm"
    BASE_URL = "https://api.webmaster.yandex.net"

    def __init__(
        self,
        auth_manager: AuthManager,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.auth = auth_manager
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=10, window_seconds=1),
        ])

    async def _headers(self) -> dict:
        token = await self.auth.get_access_token(self.PROVIDER)
        return {"Authorization": f"OAuth {token}"}

    async def get_user(self) -> dict:
        """Get current user information."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()
        resp = await self.client.request("GET", "/v2/user", headers=headers)
        return resp.json()

    async def list_hosts(self, user_id: str) -> list[dict]:
        """List all hosts for a user."""
        cached = await self.cache.get(self.PROVIDER, "hosts", {"user": user_id})
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()
        resp = await self.client.request("GET", f"/v2/user/{user_id}/hosts", headers=headers)
        data = resp.json()
        hosts = data.get("hosts", [])

        await self.cache.set(self.PROVIDER, "hosts", hosts, ttl=86400, params={"user": user_id})
        return hosts

    async def get_search_queries(
        self,
        user_id: str,
        host_id: str,
        start_date: date,
        end_date: date,
        query_types: list[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get search queries for a host."""
        if query_types is None:
            query_types = ["SEARCH"]

        cache_params = {
            "host": host_id, "start": str(start_date), "end": str(end_date),
            "limit": limit, "offset": offset,
        }
        cached = await self.cache.get(self.PROVIDER, "queries", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        params = {
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
            "query_indicator_types": ",".join(query_types),
            "limit": limit,
            "offset": offset,
        }

        resp = await self.client.request(
            "GET",
            f"/v2/user/{user_id}/hosts/{host_id}/search/queries",
            headers=headers,
            params=params,
        )
        data = resp.json()
        queries = data.get("queries", [])

        await self.cache.set(self.PROVIDER, "queries", queries, ttl=21600, params=cache_params)
        return queries

    async def get_query_stats(
        self,
        user_id: str,
        host_id: str,
        query_ids: list[str],
        start_date: date,
        end_date: date,
    ) -> dict:
        """Get statistics for specific query IDs."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()
        params = {
            "query_ids": ",".join(query_ids),
            "date_from": start_date.isoformat(),
            "date_to": end_date.isoformat(),
        }
        resp = await self.client.request(
            "GET",
            f"/v2/user/{user_id}/hosts/{host_id}/search/queries/keys/stats",
            headers=headers,
            params=params,
        )
        return resp.json()

    async def add_sitemap(self, user_id: str, host_id: str, sitemap_url: str) -> dict:
        """Submit a sitemap."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()
        resp = await self.client.request(
            "POST",
            f"/v2/user/{user_id}/hosts/{host_id}/sitemap",
            headers=headers,
            json={"url": sitemap_url},
        )
        return resp.json()

    async def close(self) -> None:
        await self.client.close()
```

---

## 7. Naver Webmaster

### 7.1 Auth Method & Setup

**API Key (Header-based)**

| Field | Value |
|-------|-------|
| **Key Location** | Naver Webmaster Tools → Settings → API Key |
| **Auth Method** | Header `X-Naver-Client-Id` + `X-Naver-Client-Secret` |
| **Base URL** | `https://openapi.naver.com/v1` |
| **Registration** | Naver Developers → Application Registration → Enable "Webmaster" API |

### 7.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /search/webkr.json` | GET | Web search results |
| `GET /search/blog.json` | GET | Blog search results |
| `GET /search/news.json` | GET | News search results |
| `GET /search/site.json` | GET | Site search results |
| Webmaster Tools Web UI | — | Crawl errors, index status (no public API yet) |

> **Note**: Naver does not expose a public Webmaster API equivalent to GSC. Integration is limited to the Naver Search API for SERP monitoring and manual Webmaster Tools data export.

### 7.3 Data Schema

```python
@dataclass
class NaverSearchResult:
    title: str
    link: str
    description: str
    bloggername: str           # For blog results
    bloggerlink: str           # For blog results
    postdate: str              # For blog/news results

@dataclass
class NaverSearchResponse:
    lastBuildDate: str
    total: int
    start: int
    display: int
    items: list[NaverSearchResult]
```

### 7.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Requests/day** | 25,000 (default per app) |
| **Requests/second** | 10 |
| **Results per request** | 100 max |

### 7.5 Python Implementation

```python
"""
integrations/naver/client.py
Naver Search API integration for SERP monitoring.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class NaverSearchClient:
    """Naver Search API client for SERP monitoring."""

    PROVIDER = "naver"
    BASE_URL = "https://openapi.naver.com/v1"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=10, window_seconds=1),
            RateLimit(requests=25000, window_seconds=86400),
        ])

    def _headers(self) -> dict:
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

    async def search(
        self,
        query: str,
        search_type: str = "webkr",
        display: int = 10,
        start: int = 1,
        sort: str = "sim",
    ) -> dict:
        """
        Search Naver.

        Args:
            query: Search query
            search_type: webkr, blog, news, site
            display: Results per page (1-100)
            start: Start index (1-1000)
            sort: sim (similarity) or date
        """
        cache_params = {"q": query, "type": search_type, "display": display, "start": start, "sort": sort}
        cached = await self.cache.get(self.PROVIDER, "search", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)

        resp = await self.client.request(
            "GET", f"/search/{search_type}.json",
            headers=self._headers(),
            params={
                "query": query,
                "display": min(display, 100),
                "start": start,
                "sort": sort,
            },
        )
        data = resp.json()

        await self.cache.set(self.PROVIDER, "search", data, ttl=3600, params=cache_params)
        return data

    async def monitor_serp_position(
        self,
        query: str,
        target_domain: str,
        search_type: str = "webkr",
        max_pages: int = 10,
    ) -> Optional[dict]:
        """Find position of target domain in Naver SERP."""
        for page in range(1, max_pages + 1):
            data = await self.search(query, search_type=search_type, display=100, start=(page - 1) * 100 + 1)
            items = data.get("items", [])
            if not items:
                break
            for i, item in enumerate(items):
                link = item.get("link", "")
                if target_domain in link:
                    return {
                        "position": (page - 1) * 100 + i + 1,
                        "page": page,
                        "title": item.get("title", ""),
                        "link": link,
                    }
        return None

    async def close(self) -> None:
        await self.client.close()
```

---

## 8. Gmail API (Outreach Execution)

### 8.1 Auth Method & Setup

**OAuth 2.0 (Authorization Code Flow with Send Scope)**

| Field | Value |
|-------|-------|
| **Scopes** | `https://www.googleapis.com/auth/gmail.send`, `gmail.readonly`, `gmail.modify`, `gmail.compose` |
| **Token URL** | `https://oauth2.googleapis.com/token` |
| **Auth URL** | `https://accounts.google.com/o/oauth2/v2/auth` |
| **Credentials** | Google Cloud Console → Enable Gmail API → OAuth 2.0 Client ID |
| **Consent** | `gmail.send` scope requires app verification for external use |

### 8.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /gmail/v1/users/{userId}/messages/send` | POST | Send email |
| `POST /gmail/v1/users/{userId}/drafts` | POST | Create draft |
| `GET /gmail/v1/users/{userId}/drafts` | GET | List drafts |
| `POST /gmail/v1/users/{userId}/drafts/{id}/send` | POST | Send draft |
| `GET /gmail/v1/users/{userId}/messages` | GET | List messages (for reply detection) |
| `GET /gmail/v1/users/{userId}/messages/{id}` | GET | Get message |
| `GET /gmail/v1/users/{userId}/messages/{id}/thread` | GET | Get thread |
| `POST /gmail/v1/users/{userId}/messages/{id}/modify` | POST | Add/remove labels |
| `GET /gmail/v1/users/{userId}/labels` | GET | List labels |
| `POST /gmail/v1/users/{userId}/labels` | POST | Create label |
| `POST /gmail/v1/users/{userId}/watch` | POST | Enable push notifications |
| `POST /gmail/v1/users/{userId}/stop` | POST | Stop push notifications |

### 8.3 Data Schema

```python
@dataclass
class OutreachEmail:
    to: str
    subject: str
    body_html: str
    body_text: str
    from_name: Optional[str] = None
    reply_to: Optional[str] = None
    in_reply_to: Optional[str] = None    # Message-ID for threading
    references: Optional[str] = None     # References header for threading
    tracking_id: Optional[str] = None    # Internal tracking

@dataclass
class SentMessage:
    id: str
    threadId: str
    labelIds: list[str]
    snippet: str
    internalDate: str

@dataclass
class Draft:
    id: str
    message: dict
```

### 8.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Daily sending quota** | 2,000 messages/day (Google Workspace), 500 (consumer) |
| **Per-user rate limit** | ~25 messages/second (burst), sustained ~5/sec |
| **API quota** | 250 quota units/second/user |
| **Message send cost** | 100 units per send |
| **Draft cost** | 10 units |
| **Push notifications** | Requires domain verification for Pub/Sub |

### 8.5 Retry Strategy

- **429**: Exponential backoff with `Retry-After`
- **Daily quota exceeded**: Queue remaining emails for next day
- **401**: Refresh token, retry once
- **Network errors**: 3 retries with jitter

### 8.6 Python Implementation

```python
"""
integrations/gmail/client.py
Gmail API integration for SEO outreach execution.
"""

import asyncio
import base64
import json
import logging
import time
import uuid
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx

from integrations.base.client import IntegrationHTTPClient, RetryConfig, IntegrationError
from integrations.base.auth import AuthManager
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class GmailOutreachClient:
    """Gmail API client for SEO outreach emails."""

    PROVIDER = "gmail"
    BASE_URL = "https://gmail.googleapis.com"

    def __init__(
        self,
        auth_manager: AuthManager,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.auth = auth_manager
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3, base_delay=2.0),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=5, window_seconds=1),     # ~5/sec sustained
            RateLimit(requests=25, window_seconds=1),    # burst
            RateLimit(requests=2000, window_seconds=86400),  # daily quota
        ])

    async def _headers(self) -> dict:
        token = await self.auth.get_access_token(self.PROVIDER)
        return {"Authorization": f"Bearer {token}"}

    # ---- Sending ----

    async def send_email(self, email: 'OutreachEmail') -> dict:
        """Send an email immediately."""
        raw_message = self._build_raw_message(email)

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "POST",
            "/gmail/v1/users/me/messages/send",
            headers=headers,
            json={"raw": raw_message},
        )
        data = resp.json()
        logger.info("Sent email to %s, message_id=%s", email.to, data.get("id"))
        return data

    async def send_batch(
        self,
        emails: list['OutreachEmail'],
        delay_seconds: float = 1.0,
        max_per_day: int = 100,
    ) -> list[dict]:
        """Send a batch of outreach emails with rate limiting."""
        results = []
        sent_today = 0

        for email in emails:
            if sent_today >= max_per_day:
                logger.warning("Daily limit reached (%d), stopping batch", max_per_day)
                break

            try:
                result = await self.send_email(email)
                results.append({"email": email.to, "status": "sent", "result": result})
                sent_today += 1
                await asyncio.sleep(delay_seconds)
            except Exception as e:
                logger.error("Failed to send to %s: %s", email.to, e)
                results.append({"email": email.to, "status": "failed", "error": str(e)})

        return results

    # ---- Drafts ----

    async def create_draft(self, email: 'OutreachEmail') -> dict:
        """Create a draft email."""
        raw_message = self._build_raw_message(email)

        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "POST",
            "/gmail/v1/users/me/drafts",
            headers=headers,
            json={"message": {"raw": raw_message}},
        )
        return resp.json()

    async def list_drafts(self, max_results: int = 100) -> list[dict]:
        """List all drafts."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "GET",
            "/gmail/v1/users/me/drafts",
            headers=headers,
            params={"maxResults": max_results},
        )
        return resp.json().get("drafts", [])

    async def send_draft(self, draft_id: str) -> dict:
        """Send an existing draft."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "POST",
            f"/gmail/v1/users/me/drafts/{draft_id}/send",
            headers=headers,
        )
        return resp.json()

    # ---- Reply Monitoring ----

    async def get_messages(
        self,
        query: str,
        max_results: int = 100,
        page_token: Optional[str] = None,
    ) -> dict:
        """Search messages (e.g., to detect replies)."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        params = {"q": query, "maxResults": max_results}
        if page_token:
            params["pageToken"] = page_token

        resp = await self.client.request(
            "GET", "/gmail/v1/users/me/messages",
            headers=headers, params=params,
        )
        return resp.json()

    async def get_message(self, message_id: str) -> dict:
        """Get a full message by ID."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "GET", f"/gmail/v1/users/me/messages/{message_id}",
            headers=headers,
            params={"format": "full"},
        )
        return resp.json()

    async def get_thread(self, thread_id: str) -> dict:
        """Get full thread (for reply context)."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "GET", f"/gmail/v1/users/me/threads/{thread_id}",
            headers=headers,
        )
        return resp.json()

    async def check_replies(
        self,
        since: datetime,
        tracking_label: str = "SEO-Outreach",
    ) -> list[dict]:
        """Check for replies to outreach emails since a given time."""
        query = f"label:{tracking_label} is:inbox after:{int(since.timestamp())}"
        data = await self.get_messages(query)
        messages = data.get("messages", [])

        replies = []
        for msg_stub in messages:
            msg = await self.get_message(msg_stub["id"])
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            replies.append({
                "id": msg["id"],
                "threadId": msg["threadId"],
                "from": headers.get("from", ""),
                "to": headers.get("to", ""),
                "subject": headers.get("subject", ""),
                "date": headers.get("date", ""),
                "snippet": msg.get("snippet", ""),
            })
        return replies

    # ---- Labels ----

    async def create_label(self, name: str) -> dict:
        """Create a Gmail label for tracking outreach."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "POST", "/gmail/v1/users/me/labels",
            headers=headers,
            json={
                "name": name,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        return resp.json()

    async def add_label(self, message_id: str, label_id: str) -> dict:
        """Add a label to a message."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        resp = await self.client.request(
            "POST", f"/gmail/v1/users/me/messages/{message_id}/modify",
            headers=headers,
            json={"addLabelIds": [label_id]},
        )
        return resp.json()

    # ---- Push Notifications (Pub/Sub) ----

    async def enable_push_notifications(
        self,
        topic_name: str,
        label_ids: Optional[list[str]] = None,
    ) -> dict:
        """
        Enable Gmail push notifications via Google Pub/Sub.

        Prerequisites:
        1. Create Pub/Sub topic: gcloud pubsub topics create gmail-notifications
        2. Grant gmail-api-push@system.gserviceaccount.com publish rights
        3. Verify domain ownership in Search Console

        Args:
            topic_name: Full Pub/Sub topic name (projects/myproject/topics/gmail-notifications)
            label_ids: Optional filter for specific labels
        """
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()

        payload = {"topicName": topic_name}
        if label_ids:
            label_filter_behavior = {"includeLabelIds": label_ids}
            payload["labelFilterBehavior"] = label_filter_behavior

        resp = await self.client.request(
            "POST", "/gmail/v1/users/me/watch",
            headers=headers,
            json=payload,
        )
        return resp.json()

    async def stop_push_notifications(self) -> None:
        """Stop push notifications."""
        await self.rate_limiter.acquire(self.PROVIDER)
        headers = await self._headers()
        await self.client.request("POST", "/gmail/v1/users/me/stop", headers=headers)

    # ---- Template System ----

    def render_template(
        self,
        template: str,
        variables: dict,
    ) -> str:
        """Render a template with variables. Simple {{var}} replacement."""
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    # ---- Internal Helpers ----

    def _build_raw_message(self, email: 'OutreachEmail') -> str:
        """Build a base64url-encoded raw email message."""
        msg = MIMEMultipart("alternative")
        msg["to"] = email.to
        msg["subject"] = email.subject
        if email.from_name:
            msg["from"] = email.from_name
        if email.reply_to:
            msg["reply-to"] = email.reply_to
        if email.in_reply_to:
            msg["In-Reply-To"] = email.in_reply_to
            msg["References"] = email.references or email.in_reply_to

        msg.attach(MIMEText(email.body_text, "plain"))
        msg.attach(MIMEText(email.body_html, "html"))

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        return raw

    async def close(self) -> None:
        await self.client.close()
```

---

## 9. Exa AI

### 9.1 Auth Method & Setup

**API Key (Bearer Token)**

| Field | Value |
|-------|-------|
| **Key Location** | Exa Dashboard → API Keys |
| **Auth Method** | `Authorization: Bearer <api_key>` |
| **Base URL** | `https://api.exa.ai` |
| **Docs** | `https://docs.exa.ai` |

### 9.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /search` | POST | Neural/keyword search |
| `POST /contents` | POST | Extract full content from URLs |
| `POST /findSimilar` | POST | Find similar pages |
| `POST /search` (type=keyword) | POST | Traditional keyword search |
| `GET /usage` | GET | API usage stats |

### 9.3 Data Schema

```python
@dataclass
class ExaResult:
    id: str                      # Exa internal ID
    url: str
    title: str
    score: float                 # Relevance score 0-1
    publishedDate: Optional[str]
    author: Optional[str]
    image: Optional[str]
    favicon: Optional[str]
    text: Optional[str]          # Full text (if contents requested)
    highlights: list[str]
    highlightScores: list[float]

@dataclass
class ExaSearchResponse:
    results: list[ExaResult]
    context: Optional[str]       # LLM-ready context string
```

### 9.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Requests/second** | 5 (starter), 20 (growth), custom (enterprise) |
| **Monthly requests** | Plan-dependent |
| **Content extraction** | 1000 URLs per request |
| **Max results** | 100 per search |

### 9.5 Python Implementation

```python
"""
integrations/exa/client.py
Exa AI API integration for semantic search and content extraction.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class ExaAIClient:
    """Exa AI API client for semantic search, content extraction, and link discovery."""

    PROVIDER = "exa"
    BASE_URL = "https://api.exa.ai"

    def __init__(
        self,
        api_key: str,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=5, window_seconds=1),
        ])

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def search(
        self,
        query: str,
        num_results: int = 10,
        use_autoprompt: bool = True,
        type: str = "neural",
        category: Optional[str] = None,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        start_published_date: Optional[str] = None,
        end_published_date: Optional[str] = None,
        include_text: bool = False,
    ) -> dict:
        """
        Search the web using Exa's neural or keyword search.

        Args:
            query: Natural language or keyword query
            num_results: Number of results (1-100)
            use_autoprompt: Let Exa optimize the query
            type: "neural" (semantic) or "keyword" (traditional)
            category: Filter by category (company, research_paper, news, etc.)
            include_domains: Limit to specific domains
            exclude_domains: Exclude specific domains
            start_published_date: ISO date filter
            end_published_date: ISO date filter
            include_text: Include full page text
        """
        cache_params = {
            "q": query, "n": num_results, "type": type,
            "cat": category, "inc": include_domains,
        }
        cached = await self.cache.get(self.PROVIDER, "search", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)

        payload = {
            "query": query,
            "numResults": num_results,
            "useAutoprompt": use_autoprompt,
            "type": type,
            "contents": {"text": include_text},
        }
        if category:
            payload["category"] = category
        if include_domains:
            payload["includeDomains"] = include_domains
        if exclude_domains:
            payload["excludeDomains"] = exclude_domains
        if start_published_date:
            payload["startPublishedDate"] = start_published_date
        if end_published_date:
            payload["endPublishedDate"] = end_published_date

        resp = await self.client.request("POST", "/search", headers=self._headers(), json=payload)
        data = resp.json()

        await self.cache.set(self.PROVIDER, "search", data, ttl=3600, params=cache_params)
        return data

    async def get_contents(
        self,
        urls: list[str],
        text: bool = True,
        highlights: bool = False,
        summary: bool = False,
    ) -> dict:
        """
        Extract full content from URLs.

        Args:
            urls: List of URLs to extract (max 1000)
            text: Include full text
            highlights: Include relevant highlights
            summary: Include AI-generated summary
        """
        await self.rate_limiter.acquire(self.PROVIDER)

        payload = {
            "urls": urls[:1000],
            "contents": {
                "text": text,
                "highlights": {"numHighlights": 3, "highlightsPerUrl": True} if highlights else {},
                "summary": True if summary else False,
            },
        }

        resp = await self.client.request("POST", "/contents", headers=self._headers(), json=payload)
        return resp.json()

    async def find_similar(
        self,
        url: str,
        num_results: int = 10,
    ) -> dict:
        """Find pages similar to a given URL."""
        cache_params = {"url": url, "n": num_results}
        cached = await self.cache.get(self.PROVIDER, "similar", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)

        payload = {"url": url, "numResults": num_results}
        resp = await self.client.request("POST", "/findSimilar", headers=self._headers(), json=payload)
        data = resp.json()

        await self.cache.set(self.PROVIDER, "similar", data, ttl=7200, params=cache_params)
        return data

    async def find_journalists(
        self,
        topic: str,
        num_results: int = 20,
    ) -> list[dict]:
        """Find journalists who write about a topic (for link building outreach)."""
        data = await self.search(
            query=f"journalist reporter writer {topic}",
            num_results=num_results,
            type="neural",
            category="news",
        )
        results = data.get("results", [])
        return [
            {
                "name": r.get("author", ""),
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "published_date": r.get("publishedDate", ""),
                "score": r.get("score", 0),
            }
            for r in results
            if r.get("author")
        ]

    async def get_usage(self) -> dict:
        """Get current API usage."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request("GET", "/usage", headers=self._headers())
        return resp.json()

    async def close(self) -> None:
        await self.client.close()
```

---

## 10. Tavily

### 10.1 Auth Method & Setup

**API Key (Header or Body)**

| Field | Value |
|-------|-------|
| **Key Location** | Tavily Dashboard → API Keys |
| **Auth Method** | `api_key` field in request body (or Bearer header) |
| **Base URL** | `https://api.tavily.com` |
| **Docs** | `https://docs.tavily.com` |

### 10.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /search` | POST | AI-optimized web search |
| `POST /extract` | POST | Extract content from URLs |
| `POST /search` (with `include_raw_content`) | POST | Full page content via search |

### 10.3 Data Schema

```python
@dataclass
class TavilyResult:
    title: str
    url: str
    content: str                 # Extracted snippet/content
    score: float                 # Relevance score
    raw_content: Optional[str]   # Full page content if requested
    published_date: Optional[str]

@dataclass
class TavilySearchResponse:
    query: str
    answer: Optional[str]        # AI-generated answer
    results: list[TavilyResult]
    images: list[str]            # Related images
    follow_up_questions: Optional[list[str]]
```

### 10.4 Rate Limits

| Limit | Value |
|-------|-------|
| **API calls** | 1,000/month (free), 10,000/month (paid) |
| **Search depth** | "basic" (fast) or "deep" (thorough, slower) |
| **Max results** | 20 per search |
| **Extract** | 20 URLs per request |

### 10.5 Python Implementation

```python
"""
integrations/tavily/client.py
Tavily API integration for AI-optimized research.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class TavilyClient:
    """Tavily API client for AI-optimized web search and content extraction."""

    PROVIDER = "tavily"
    BASE_URL = "https://api.tavily.com"

    def __init__(
        self,
        api_key: str,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=5, window_seconds=1),
        ])

    async def search(
        self,
        query: str,
        search_depth: str = "basic",
        max_results: int = 10,
        include_answer: bool = True,
        include_raw_content: bool = False,
        include_domains: Optional[list[str]] = None,
        exclude_domains: Optional[list[str]] = None,
        topic: str = "general",
    ) -> dict:
        """
        Search with Tavily's AI-optimized engine.

        Args:
            query: Search query
            search_depth: "basic" (fast) or "deep" (thorough)
            max_results: Number of results (1-20)
            include_answer: Generate AI answer from results
            include_raw_content: Include full page content
            include_domains: Limit to specific domains
            exclude_domains: Exclude domains
            topic: "general" or "news"
        """
        cache_params = {
            "q": query, "depth": search_depth, "n": max_results,
            "inc": include_domains, "topic": topic,
        }
        cached = await self.cache.get(self.PROVIDER, "search", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)

        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": search_depth,
            "max_results": max_results,
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "topic": topic,
        }
        if include_domains:
            payload["include_domains"] = include_domains
        if exclude_domains:
            payload["exclude_domains"] = exclude_domains

        resp = await self.client.request("POST", "/search", json=payload)
        data = resp.json()

        await self.cache.set(self.PROVIDER, "search", data, ttl=3600, params=cache_params)
        return data

    async def extract(
        self,
        urls: list[str],
        include_images: bool = False,
    ) -> dict:
        """Extract content from URLs."""
        await self.rate_limiter.acquire(self.PROVIDER)

        payload = {
            "api_key": self.api_key,
            "urls": urls[:20],
            "include_images": include_images,
        }

        resp = await self.client.request("POST", "/extract", json=payload)
        return resp.json()

    async def research_topic(
        self,
        topic: str,
        depth: int = 2,
    ) -> dict:
        """
        Deep research on a topic: search + extract top results.

        Args:
            topic: Research topic
            depth: 1=basic search, 2=deep search + extract
        """
        search_depth = "deep" if depth >= 2 else "basic"
        results = await self.search(
            topic,
            search_depth=search_depth,
            max_results=10,
            include_answer=True,
            include_raw_content=(depth >= 2),
        )

        if depth >= 2 and results.get("results"):
            top_urls = [r["url"] for r in results["results"][:5]]
            extracted = await self.extract(top_urls)
            results["extracted_content"] = extracted

        return results

    async def close(self) -> None:
        await self.client.close()
```

---

## 11. SerpAPI

### 11.1 Auth Method & Setup

**API Key (Query Parameter)**

| Field | Value |
|-------|-------|
| **Key Location** | SerpAPI Dashboard → API Key |
| **Auth Method** | `api_key` query parameter |
| **Base URL** | `https://serpapi.com` |
| **Docs** | `https://serpapi.com/search-api` |

### 11.2 Endpoints Used

| Endpoint | Engine | Purpose |
|----------|--------|---------|
| `GET /search?engine=google` | Google | Google SERP |
| `GET /search?engine=google_maps` | Google Maps | Local pack |
| `GET /search?engine=bing` | Bing | Bing SERP |
| `GET /search?engine=yandex` | Yandex | Yandex SERP |
| `GET /search?engine=naver` | Naver | Naver SERP |
| `GET /search?engine=google_scholar` | Scholar | Academic search |
| `GET /search?engine=google_trends` | Trends | Search trends |
| `GET /search?engine=google_autocomplete` | Autocomplete | Query suggestions |

### 11.3 Data Schema

```python
@dataclass
class SerpResult:
    position: int
    title: str
    link: str
    snippet: str
    displayed_link: Optional[str]
    cached_page_link: Optional[str]
    related_pages_link: Optional[str]

@dataclass
class SerpResponse:
    search_metadata: dict        # id, status, created_at, processed_at
    search_parameters: dict      # engine, q, location, etc.
    search_information: dict     # total_results, time_taken, etc.
    organic_results: list[dict]
    answer_box: Optional[dict]
    knowledge_graph: Optional[dict]
    people_also_ask: Optional[list[dict]]
    related_searches: Optional[list[dict]]
    local_results: Optional[list[dict]]
    inline_images: Optional[list[dict]]
    pagination: Optional[dict]
```

### 11.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Searches/month** | Plan-dependent (100 free, 5,000+ paid) |
| **Rate** | No hard per-second limit, but 429 on burst |
| **Concurrent** | Varies by plan |
| **Cost per search** | 1 search credit (some engines cost more) |

### 11.5 Python Implementation

```python
"""
integrations/serpapi/client.py
SerpAPI integration for multi-engine SERP monitoring.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class SerpAPIClient:
    """SerpAPI client for Google, Bing, Yandex, and Naver SERP data."""

    PROVIDER = "serpapi"
    BASE_URL = "https://serpapi.com"

    def __init__(
        self,
        api_key: str,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=10, window_seconds=60),
        ])

    async def search(
        self,
        query: str,
        engine: str = "google",
        location: Optional[str] = None,
        country: Optional[str] = None,
        language: Optional[str] = None,
        num: int = 10,
        start: int = 0,
        device: str = "desktop",
        **kwargs,
    ) -> dict:
        """
        Execute a SERP search.

        Args:
            query: Search query
            engine: google, bing, yandex, naver, google_maps, google_scholar, etc.
            location: Location (e.g., "Austin, Texas, United States")
            country: Country code (e.g., "us")
            language: Language code (e.g., "en")
            num: Number of results
            start: Offset
            device: desktop or mobile
            **kwargs: Additional engine-specific parameters
        """
        cache_params = {
            "q": query, "engine": engine, "loc": location,
            "country": country, "lang": language, "num": num, "start": start,
        }
        cached = await self.cache.get(self.PROVIDER, "search", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)

        params = {
            "api_key": self.api_key,
            "q": query,
            "engine": engine,
            "num": num,
            "start": start,
            "device": device,
        }
        if location:
            params["location"] = location
        if country:
            params["gl"] = country
        if language:
            params["hl"] = language
        params.update(kwargs)

        resp = await self.client.request("GET", "/search", params=params)
        data = resp.json()

        await self.cache.set(self.PROVIDER, "search", data, ttl=7200, params=cache_params)
        return data

    async def google_serp(
        self,
        query: str,
        location: Optional[str] = None,
        num: int = 10,
    ) -> dict:
        """Google SERP with all features (PAA, featured snippets, knowledge panel)."""
        return await self.search(
            query=query, engine="google", location=location, num=num,
        )

    async def bing_serp(self, query: str, num: int = 10) -> dict:
        """Bing SERP."""
        return await self.search(query=query, engine="bing", num=num)

    async def yandex_serp(self, query: str, num: int = 10) -> dict:
        """Yandex SERP."""
        return await self.search(query=query, engine="yandex", num=num)

    async def naver_serp(self, query: str, num: int = 10) -> dict:
        """Naver SERP."""
        return await self.search(query=query, engine="naver", num=num)

    async def extract_serp_features(self, serp_data: dict) -> dict:
        """Extract SERP features from raw response."""
        return {
            "answer_box": serp_data.get("answer_box"),
            "knowledge_graph": serp_data.get("knowledge_graph"),
            "people_also_ask": [
                q.get("question", "")
                for q in serp_data.get("people_also_ask", [])
            ],
            "featured_snippet": self._extract_featured_snippet(serp_data),
            "local_pack": serp_data.get("local_results", []),
            "related_searches": [
                r.get("query", "")
                for r in serp_data.get("related_searches", [])
            ],
            "sitelinks": self._extract_sitelinks(serp_data),
            "top_stories": serp_data.get("top_stories", []),
            "shopping_results": serp_data.get("shopping_results", []),
            "inline_images": serp_data.get("inline_images", []),
        }

    def _extract_featured_snippet(self, data: dict) -> Optional[dict]:
        """Extract featured snippet from various locations in response."""
        ab = data.get("answer_box", {})
        if ab and ab.get("type") == "featured_snippet":
            return {
                "title": ab.get("title", ""),
                "snippet": ab.get("snippet", ""),
                "link": ab.get("link", ""),
                "source": ab.get("displayed_link", ""),
            }
        return None

    def _extract_sitelinks(self, data: dict) -> list[dict]:
        """Extract sitelinks from organic results."""
        sitelinks = []
        for result in data.get("organic_results", []):
            sl = result.get("sitelinks", {})
            if sl:
                for inline in sl.get("inline", []):
                    sitelinks.append({
                        "title": inline.get("title", ""),
                        "link": inline.get("link", ""),
                    })
        return sitelinks

    async def close(self) -> None:
        await self.client.close()
```

---

## 12. Ahrefs API

### 12.1 Auth Method & Setup

**API Key (Bearer Token)**

| Field | Value |
|-------|-------|
| **Key Location** | Ahrefs Account → API → Generate Token |
| **Auth Method** | `Authorization: Bearer <api_key>` |
| **Base URL** | `https://api.ahrefs.com/v3` |
| **Docs** | `https://ahrefs.com/api/v3/doc` |

### 12.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /site-explorer/overview` | GET | Domain/url overview |
| `GET /site-explorer/backlinks` | GET | Backlink profile |
| `GET /site-explorer/referring-domains` | GET | Referring domains |
| `GET /site-explorer/organic-keywords` | GET | Ranking keywords |
| `GET /site-explorer/organic-traffic` | GET | Traffic estimates |
| `GET /site-explorer/best-by-links` | GET | Top pages by backlinks |
| `GET /site-explorer/top-pages` | GET | Top pages by traffic |
| `GET /keywords-explorer/overview` | GET | Keyword metrics |
| `GET /keywords-explorer/keyword-difficulty` | GET | KD score |
| `GET /keywords-explorer/search-volume` | GET | Volume history |

### 12.3 Data Schema

```python
@dataclass
class AhrefsBacklink:
    url_from: str
    url_to: str
    anchor: str
    first_seen: str
    last_seen: str
    nofollow: bool
    domain_rating: float
    url_rating: float
    traffic: int
    referring_domains: int

@dataclass
class AhrefsKeyword:
    keyword: str
    volume: int
    keyword_difficulty: float
    cpc: float
    traffic_potential: int
    parent_topic: str
    position: Optional[int]
    url: Optional[str]

@dataclass
class AhrefsOverview:
    domain_rating: float
    ahrefs_rank: int
    referring_domains: int
    backlinks: int
    organic_keywords: int
    organic_traffic: int
    traffic_value: float
```

### 12.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Requests/second** | 10 (standard), 100 (enterprise) |
| **Monthly credits** | Plan-dependent |
| **Credit cost** | Varies by endpoint (1-10 credits per call) |

### 12.5 Python Implementation

```python
"""
integrations/ahrefs/client.py
Ahrefs API integration for backlink and keyword data.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class AhrefsClient:
    """Ahrefs API client."""

    PROVIDER = "ahrefs"
    BASE_URL = "https://api.ahrefs.com/v3"

    def __init__(
        self,
        api_key: str,
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=10, window_seconds=1),
        ])

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def get_site_overview(
        self,
        target: str,
        protocol: str = "https",
        mode: str = "subdomains",
    ) -> dict:
        """
        Get site overview (domain rating, traffic, backlinks, etc.).

        Args:
            target: Domain or URL
            protocol: http or https
            mode: subdomains, domain, prefix, exact
        """
        cache_params = {"target": target, "mode": mode}
        cached = await self.cache.get(self.PROVIDER, "overview", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/site-explorer/overview",
            headers=self._headers(),
            params={"target": target, "protocol": protocol, "mode": mode},
        )
        data = resp.json()

        await self.cache.set(self.PROVIDER, "overview", data, ttl=43200, params=cache_params)
        return data

    async def get_backlinks(
        self,
        target: str,
        mode: str = "subdomains",
        limit: int = 100,
        offset: int = 0,
        protocol: str = "https",
    ) -> dict:
        """Get backlinks for a target."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/site-explorer/backlinks",
            headers=self._headers(),
            params={
                "target": target, "mode": mode, "protocol": protocol,
                "limit": limit, "offset": offset,
            },
        )
        return resp.json()

    async def get_referring_domains(
        self,
        target: str,
        mode: str = "subdomains",
        limit: int = 100,
    ) -> dict:
        """Get referring domains."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/site-explorer/referring-domains",
            headers=self._headers(),
            params={"target": target, "mode": mode, "limit": limit},
        )
        return resp.json()

    async def get_organic_keywords(
        self,
        target: str,
        mode: str = "subdomains",
        limit: int = 100,
        country: str = "us",
    ) -> dict:
        """Get organic keywords a domain ranks for."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/site-explorer/organic-keywords",
            headers=self._headers(),
            params={"target": target, "mode": mode, "limit": limit, "country": country},
        )
        return resp.json()

    async def get_keyword_metrics(
        self,
        keywords: list[str],
        country: str = "us",
    ) -> dict:
        """
        Get keyword metrics (volume, KD, CPC).

        Args:
            keywords: List of keywords to look up
            country: Country code
        """
        cache_params = {"keywords": keywords, "country": country}
        cached = await self.cache.get(self.PROVIDER, "keyword_metrics", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/keywords-explorer/overview",
            headers=self._headers(),
            params={"keywords": ",".join(keywords), "country": country},
        )
        data = resp.json()

        await self.cache.set(self.PROVIDER, "keyword_metrics", data, ttl=86400, params=cache_params)
        return data

    async def get_top_pages(
        self,
        target: str,
        mode: str = "subdomains",
        limit: int = 100,
        country: str = "us",
    ) -> dict:
        """Get top pages by traffic."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/site-explorer/top-pages",
            headers=self._headers(),
            params={"target": target, "mode": mode, "limit": limit, "country": country},
        )
        return resp.json()

    async def get_best_by_links(
        self,
        target: str,
        mode: str = "subdomains",
        limit: int = 100,
    ) -> dict:
        """Get pages with the most backlinks."""
        await self.rate_limiter.acquire(self.PROVIDER)
        resp = await self.client.request(
            "GET", "/site-explorer/best-by-links",
            headers=self._headers(),
            params={"target": target, "mode": mode, "limit": limit},
        )
        return resp.json()

    async def close(self) -> None:
        await self.client.close()
```

---

## 13. PageSpeed Insights API

### 13.1 Auth Method & Setup

**API Key (Query Parameter) or Unauthenticated**

| Field | Value |
|-------|-------|
| **Key Location** | Google Cloud Console → APIs & Services → PageSpeed Insights API → Credentials |
| **Auth Method** | `key` query parameter (optional but recommended for higher quotas) |
| **Base URL** | `https://www.googleapis.com/pagespeedonline/v5` |
| **Free tier** | Works without API key but with lower quotas |

### 13.2 Endpoints Used

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /runPagespeed?url={url}` | GET | Full PageSpeed report |
| `GET /runPagespeed?url={url}&category=performance` | GET | Performance only |
| `GET /runPagespeed?url={url}&strategy=mobile` | GET | Mobile analysis |

### 13.3 Data Schema

```python
@dataclass
class CoreWebVitals:
    lcp: float               # Largest Contentful Paint (ms)
    fid: Optional[float]     # First Input Delay (ms) - lab: uses TBT
    cls: float               # Cumulative Layout Shift
    inp: Optional[float]     # Interaction to Next Paint (ms)
    fcp: float               # First Contentful Paint (ms)
    ttfb: float              # Time to First Byte (ms)
    tbt: float               # Total Blocking Time (ms)
    si: float                # Speed Index (ms)
    tti: Optional[float]     # Time to Interactive (ms)

@dataclass
class PageSpeedResult:
    url: str
    strategy: str            # mobile or desktop
    performance_score: float # 0-1
    accessibility_score: float
    best_practices_score: float
    seo_score: float
    cwv: CoreWebVitals
    audits: dict             # Full Lighthouse audit details
    loading_experience: dict # Real-user CrUX data if available
```

### 13.4 Rate Limits

| Limit | Value |
|-------|-------|
| **Without API key** | ~25 queries/100 seconds per IP |
| **With API key** | 25,000 queries/day (default quota) |
| **Concurrent** | Not strictly limited; batches recommended |

### 13.5 Python Implementation

```python
"""
integrations/pagespeed/client.py
PageSpeed Insights API integration for Core Web Vitals monitoring.
"""

import asyncio
import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit
from integrations.base.cache import ResponseCache

logger = logging.getLogger(__name__)


class PageSpeedInsightsClient:
    """PageSpeed Insights API client."""

    PROVIDER = "pagespeed"
    BASE_URL = "https://www.googleapis.com/pagespeedonline/v5"

    def __init__(
        self,
        api_key: Optional[str],
        rate_limiter: SlidingWindowRateLimiter,
        cache: ResponseCache,
    ):
        self.api_key = api_key
        self.rate_limiter = rate_limiter
        self.cache = cache
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=2, base_delay=5.0),
            timeout=120.0,  # PSI can be slow
        )
        self.rate_limiter.register(self.PROVIDER, [
            RateLimit(requests=25, window_seconds=100),
            RateLimit(requests=25000, window_seconds=86400),
        ])

    async def analyze(
        self,
        url: str,
        strategy: str = "mobile",
        categories: Optional[list[str]] = None,
        locale: str = "en",
        utm_source: str = "seo_platform",
    ) -> dict:
        """
        Run PageSpeed analysis on a URL.

        Args:
            url: Page URL to analyze
            strategy: "mobile" or "desktop"
            categories: ["performance", "accessibility", "best-practices", "seo"]
            locale: Locale for report
        """
        if categories is None:
            categories = ["performance", "accessibility", "best-practices", "seo"]

        cache_params = {"url": url, "strategy": strategy, "categories": categories}
        cached = await self.cache.get(self.PROVIDER, "analyze", cache_params)
        if cached:
            return cached

        await self.rate_limiter.acquire(self.PROVIDER)

        params = {
            "url": url,
            "strategy": strategy,
            "category": categories,
            "locale": locale,
            "utm_source": utm_source,
        }
        if self.api_key:
            params["key"] = self.api_key

        resp = await self.client.request("GET", "/runPagespeed", params=params)
        data = resp.json()

        # Cache for 6 hours (CWV don't change minute-to-minute)
        await self.cache.set(self.PROVIDER, "analyze", data, ttl=21600, params=cache_params)
        return data

    async def get_cwv(self, url: str, strategy: str = "mobile") -> dict:
        """Extract Core Web Vitals from PageSpeed result."""
        data = await self.analyze(url, strategy=strategy, categories=["performance"])
        lhr = data.get("lighthouseResult", {})
        audits = lhr.get("audits", {})

        return {
            "url": url,
            "strategy": strategy,
            "performance_score": lhr.get("categories", {}).get("performance", {}).get("score", 0),
            "core_web_vitals": {
                "lcp": audits.get("largest-contentful-paint", {}).get("numericValue"),
                "cls": audits.get("cumulative-layout-shift", {}).get("numericValue"),
                "tbt": audits.get("total-blocking-time", {}).get("numericValue"),
                "fcp": audits.get("first-contentful-paint", {}).get("numericValue"),
                "ttfb": audits.get("server-response-time", {}).get("numericValue"),
                "si": audits.get("speed-index", {}).get("numericValue"),
                "tti": audits.get("interactive", {}).get("numericValue"),
                "inp": audits.get("experimental-interaction-to-next-paint", {}).get("numericValue"),
            },
            "crux": data.get("loadingExperience", {}).get("metrics", {}),
            "origin_fallback": data.get("originLoadingExperience", {}).get("metrics", {}),
        }

    async def audit_multiple(
        self,
        urls: list[str],
        strategy: str = "mobile",
        concurrency: int = 5,
    ) -> list[dict]:
        """Audit multiple URLs with concurrency control."""
        semaphore = asyncio.Semaphore(concurrency)

        async def _audit(url: str) -> dict:
            async with semaphore:
                try:
                    return await self.get_cwv(url, strategy)
                except Exception as e:
                    logger.error("PSI failed for %s: %s", url, e)
                    return {"url": url, "error": str(e)}

        tasks = [_audit(url) for url in urls]
        return await asyncio.gather(*tasks)

    async def close(self) -> None:
        await self.client.close()
```

---

## 14. CMS Integrations

### 14.1 WordPress REST API

#### Auth: Application Passwords

| Field | Value |
|-------|-------|
| **Auth Method** | HTTP Basic Auth with Application Password |
| **Setup** | Users → Profile → Application Passwords → Add New |
| **Base URL** | `{site_url}/wp-json/wp/v2` |
| **Requirements** | WordPress 5.6+, REST API enabled, pretty permalinks |

#### Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /posts` | GET | List posts |
| `POST /posts` | POST | Create post |
| `PUT /posts/{id}` | PUT | Update post |
| `DELETE /posts/{id}` | DELETE | Delete post |
| `GET /pages` | GET | List pages |
| `POST /pages` | POST | Create page |
| `PUT /pages/{id}` | PUT | Update page |
| `GET /categories` | GET | List categories |
| `GET /tags` | GET | List tags |
| `POST /media` | POST | Upload media |
| `GET /users` | GET | List users |
| `GET /taxonomies` | GET | List taxonomies |

#### Python Implementation

```python
"""
integrations/cms/wordpress.py
WordPress REST API integration.
"""

import logging
from typing import Optional
from base64 import b64encode

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit

logger = logging.getLogger(__name__)


class WordPressClient:
    """WordPress REST API client using Application Passwords."""

    def __init__(
        self,
        site_url: str,
        username: str,
        app_password: str,
        rate_limiter: SlidingWindowRateLimiter,
    ):
        self.site_url = site_url.rstrip("/")
        self.rate_limiter = rate_limiter
        self._auth_header = "Basic " + b64encode(
            f"{username}:{app_password}".encode()
        ).decode()

        self.client = IntegrationHTTPClient(
            provider=f"wp:{site_url}",
            base_url=f"{self.site_url}/wp-json/wp/v2",
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register(f"wp:{site_url}", [
            RateLimit(requests=30, window_seconds=60),
        ])

    def _headers(self) -> dict:
        return {
            "Authorization": self._auth_header,
            "Content-Type": "application/json",
        }

    async def list_posts(
        self,
        status: str = "publish",
        per_page: int = 100,
        page: int = 1,
        search: Optional[str] = None,
        categories: Optional[list[int]] = None,
        orderby: str = "date",
        order: str = "desc",
    ) -> dict:
        """List posts with filters."""
        await self.rate_limiter.acquire(f"wp:{self.site_url}")

        params = {
            "status": status,
            "per_page": per_page,
            "page": page,
            "orderby": orderby,
            "order": order,
        }
        if search:
            params["search"] = search
        if categories:
            params["categories"] = ",".join(str(c) for c in categories)

        resp = await self.client.request("GET", "/posts", headers=self._headers(), params=params)
        total_pages = int(resp.headers.get("X-WP-TotalPages", 1))
        total = int(resp.headers.get("X-WP-Total", 0))

        return {
            "posts": resp.json(),
            "total": total,
            "total_pages": total_pages,
            "current_page": page,
        }

    async def create_post(
        self,
        title: str,
        content: str,
        status: str = "draft",
        slug: Optional[str] = None,
        excerpt: Optional[str] = None,
        categories: Optional[list[int]] = None,
        tags: Optional[list[int]] = None,
        featured_media: Optional[int] = None,
        meta: Optional[dict] = None,
    ) -> dict:
        """Create a new post with SEO metadata."""
        await self.rate_limiter.acquire(f"wp:{self.site_url}")

        payload = {
            "title": title,
            "content": content,
            "status": status,
        }
        if slug:
            payload["slug"] = slug
        if excerpt:
            payload["excerpt"] = excerpt
        if categories:
            payload["categories"] = categories
        if tags:
            payload["tags"] = tags
        if featured_media:
            payload["featured_media"] = featured_media
        if meta:
            payload["meta"] = meta

        resp = await self.client.request("POST", "/posts", headers=self._headers(), json=payload)
        data = resp.json()
        logger.info("Created WP post: %s (ID: %s)", title, data.get("id"))
        return data

    async def update_post(
        self,
        post_id: int,
        **kwargs,
    ) -> dict:
        """Update an existing post."""
        await self.rate_limiter.acquire(f"wp:{self.site_url}")

        resp = await self.client.request(
            "PUT", f"/posts/{post_id}",
            headers=self._headers(), json=kwargs,
        )
        return resp.json()

    async def update_post_seo(
        self,
        post_id: int,
        seo_title: Optional[str] = None,
        meta_description: Optional[str] = None,
        canonical_url: Optional[str] = None,
        focus_keyword: Optional[str] = None,
        og_title: Optional[str] = None,
        og_description: Optional[str] = None,
        schema_markup: Optional[dict] = None,
    ) -> dict:
        """Update SEO metadata (Yoast/RankMath/SEOPress custom fields)."""
        meta = {}
        if seo_title is not None:
            meta["_yoast_wpseo_title"] = seo_title
            meta["rank_math_title"] = seo_title
        if meta_description is not None:
            meta["_yoast_wpseo_metadesc"] = meta_description
            meta["rank_math_description"] = meta_description
        if canonical_url is not None:
            meta["_yoast_wpseo_canonical"] = canonical_url
            meta["rank_math_canonical_url"] = canonical_url
        if focus_keyword is not None:
            meta["_yoast_wpseo_focuskw"] = focus_keyword
            meta["rank_math_focus_keyword"] = focus_keyword
        if og_title is not None:
            meta["_yoast_wpseo_opengraph-title"] = og_title
        if og_description is not None:
            meta["_yoast_wpseo_opengraph-description"] = og_description

        return await self.update_post(post_id, meta=meta)

    async def upload_media(
        self,
        file_path: str,
        alt_text: Optional[str] = None,
        title: Optional[str] = None,
    ) -> dict:
        """Upload media file."""
        import aiofiles

        await self.rate_limiter.acquire(f"wp:{self.site_url}")

        async with aiofiles.open(file_path, "rb") as f:
            file_data = await f.read()

        import os
        filename = os.path.basename(file_path)
        content_type = self._guess_content_type(filename)

        headers = {
            "Authorization": self._auth_header,
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": content_type,
        }

        resp = await self.client.client.post(
            f"{self.site_url}/wp-json/wp/v2/media",
            headers=headers,
            content=file_data,
        )
        resp.raise_for_status()
        data = resp.json()

        if alt_text:
            await self.client.request(
                "POST", f"/media/{data['id']}",
                headers=self._headers(),
                json={"alt_text": alt_text},
            )

        return data

    async def list_all_posts(self, status: str = "publish") -> list[dict]:
        """Paginate through all posts."""
        all_posts = []
        page = 1
        while True:
            result = await self.list_posts(status=status, per_page=100, page=page)
            all_posts.extend(result["posts"])
            if page >= result["total_pages"]:
                break
            page += 1
        return all_posts

    def _guess_content_type(self, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        return {
            "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp", "svg": "image/svg+xml",
            "pdf": "application/pdf", "mp4": "video/mp4",
        }.get(ext, "application/octet-stream")

    async def close(self) -> None:
        await self.client.close()
```

### 14.2 Webflow CMS API

```python
"""
integrations/cms/webflow.py
Webflow CMS API integration.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit

logger = logging.getLogger(__name__)


class WebflowClient:
    """Webflow CMS API client."""

    BASE_URL = "https://api.webflow.com/v2"

    def __init__(
        self,
        api_token: str,
        rate_limiter: SlidingWindowRateLimiter,
    ):
        self.api_token = api_token
        self.rate_limiter = rate_limiter
        self.client = IntegrationHTTPClient(
            provider="webflow",
            base_url=self.BASE_URL,
            retry_config=RetryConfig(max_retries=3),
        )
        self.rate_limiter.register("webflow", [
            RateLimit(requests=60, window_seconds=60),
        ])

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def list_sites(self) -> list[dict]:
        """List all sites."""
        await self.rate_limiter.acquire("webflow")
        resp = await self.client.request("GET", "/sites", headers=self._headers())
        return resp.json().get("sites", [])

    async def list_collections(self, site_id: str) -> list[dict]:
        """List CMS collections for a site."""
        await self.rate_limiter.acquire("webflow")
        resp = await self.client.request(
            "GET", f"/sites/{site_id}/collections",
            headers=self._headers(),
        )
        return resp.json().get("collections", [])

    async def list_items(
        self,
        collection_id: str,
        offset: int = 0,
        limit: int = 100,
    ) -> dict:
        """List CMS items in a collection."""
        await self.rate_limiter.acquire("webflow")
        resp = await self.client.request(
            "GET", f"/collections/{collection_id}/items",
            headers=self._headers(),
            params={"offset": offset, "limit": limit},
        )
        return resp.json()

    async def create_item(
        self,
        collection_id: str,
        field_data: dict,
        is_archived: bool = False,
        is_draft: bool = False,
    ) -> dict:
        """Create a CMS item."""
        await self.rate_limiter.acquire("webflow")
        resp = await self.client.request(
            "POST", f"/collections/{collection_id}/items",
            headers=self._headers(),
            json={
                "fieldData": field_data,
                "isArchived": is_archived,
                "isDraft": is_draft,
            },
        )
        return resp.json()

    async def update_item(
        self,
        collection_id: str,
        item_id: str,
        field_data: dict,
    ) -> dict:
        """Update a CMS item."""
        await self.rate_limiter.acquire("webflow")
        resp = await self.client.request(
            "PATCH", f"/collections/{collection_id}/items/{item_id}",
            headers=self._headers(),
            json={"fieldData": field_data},
        )
        return resp.json()

    async def publish_item(self, collection_id: str, item_id: str) -> dict:
        """Publish a draft item."""
        await self.rate_limiter.acquire("webflow")
        resp = await self.client.request(
            "POST", f"/collections/{collection_id}/items/publish",
            headers=self._headers(),
            json={"itemIds": [item_id]},
        )
        return resp.json()

    async def close(self) -> None:
        await self.client.close()
```

### 14.3 Shopify Admin API

```python
"""
integrations/cms/shopify.py
Shopify Admin REST API integration.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit

logger = logging.getLogger(__name__)


class ShopifyClient:
    """Shopify Admin API client."""

    def __init__(
        self,
        shop_domain: str,
        access_token: str,
        rate_limiter: SlidingWindowRateLimiter,
        api_version: str = "2024-01",
    ):
        self.shop_domain = shop_domain.replace(".myshopify.com", "")
        self.access_token = access_token
        self.api_version = api_version
        base_url = f"https://{self.shop_domain}.myshopify.com/admin/api/{api_version}"
        self.rate_limiter = rate_limiter

        self.client = IntegrationHTTPClient(
            provider=f"shopify:{self.shop_domain}",
            base_url=base_url,
            retry_config=RetryConfig(max_retries=3),
        )
        # Shopify: 2 requests/second, bucket-based
        self.rate_limiter.register(f"shopify:{self.shop_domain}", [
            RateLimit(requests=2, window_seconds=1),
            RateLimit(requests=40, window_seconds=60),  # bucket refill
        ])

    def _headers(self) -> dict:
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
        }

    async def list_products(
        self,
        limit: int = 250,
        page_info: Optional[str] = None,
        status: str = "active",
    ) -> dict:
        """List products."""
        await self.rate_limiter.acquire(f"shopify:{self.shop_domain}")

        params = {"limit": limit, "status": status}
        if page_info:
            params["page_info"] = page_info

        resp = await self.client.request("GET", "/products.json", headers=self._headers(), params=params)
        return resp.json()

    async def update_product(self, product_id: int, data: dict) -> dict:
        """Update a product (for SEO fields: title, body_html, metafields)."""
        await self.rate_limiter.acquire(f"shopify:{self.shop_domain}")

        resp = await self.client.request(
            "PUT", f"/products/{product_id}.json",
            headers=self._headers(),
            json={"product": data},
        )
        return resp.json()

    async def list_metafields(
        self,
        resource: str,
        resource_id: int,
    ) -> list[dict]:
        """List metafields for a resource (product, page, article)."""
        await self.rate_limiter.acquire(f"shopify:{self.shop_domain}")

        resp = await self.client.request(
            "GET", f"/{resource}s/{resource_id}/metafields.json",
            headers=self._headers(),
        )
        return resp.json().get("metafields", [])

    async def set_metafield(
        self,
        resource: str,
        resource_id: int,
        namespace: str,
        key: str,
        value: str,
        value_type: str = "string",
    ) -> dict:
        """Set a metafield (for SEO title, description, canonical, etc.)."""
        await self.rate_limiter.acquire(f"shopify:{self.shop_domain}")

        resp = await self.client.request(
            "POST", f"/{resource}s/{resource_id}/metafields.json",
            headers=self._headers(),
            json={
                "metafield": {
                    "namespace": namespace,
                    "key": key,
                    "value": value,
                    "type": value_type,
                },
            },
        )
        return resp.json()

    async def list_pages(self, limit: int = 250) -> dict:
        """List pages."""
        await self.rate_limiter.acquire(f"shopify:{self.shop_domain}")
        resp = await self.client.request(
            "GET", "/pages.json",
            headers=self._headers(),
            params={"limit": limit},
        )
        return resp.json()

    async def update_page_seo(
        self,
        page_id: int,
        title_tag: Optional[str] = None,
        meta_description: Optional[str] = None,
    ) -> None:
        """Update SEO metadata for a page via metafields."""
        if title_tag:
            await self.set_metafield("page", page_id, "global", "title_tag", title_tag)
        if meta_description:
            await self.set_metafield("page", page_id, "global", "description_tag", meta_description)

    async def list_blogs(self) -> dict:
        """List blogs."""
        await self.rate_limiter.acquire(f"shopify:{self.shop_domain}")
        resp = await self.client.request("GET", "/blogs.json", headers=self._headers())
        return resp.json()

    async def list_articles(self, blog_id: int, limit: int = 250) -> dict:
        """List articles in a blog."""
        await self.rate_limiter.acquire(f"shopify:{self.shop_domain}")
        resp = await self.client.request(
            "GET", f"/blogs/{blog_id}/articles.json",
            headers=self._headers(),
            params={"limit": limit},
        )
        return resp.json()

    async def get_sitemap(self) -> str:
        """Fetch the Shopify sitemap XML."""
        resp = await self.client.client.get(
            f"https://{self.shop_domain}.myshopify.com/sitemap.xml",
        )
        return resp.text

    async def close(self) -> None:
        await self.client.close()
```

### 14.4 Generic REST API Connector

```python
"""
integrations/cms/generic.py
Generic REST API connector for any CMS.
"""

import logging
from typing import Optional, Any
from dataclasses import dataclass

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit

logger = logging.getLogger(__name__)


@dataclass
class CMSEndpoint:
    """Configuration for a CMS endpoint."""
    name: str
    method: str                    # GET, POST, PUT, PATCH, DELETE
    path: str
    auth_type: str = "header"      # header, query, basic
    auth_key: str = "Authorization"
    auth_value: str = ""
    rate_limit_rps: int = 10
    rate_limit_daily: int = 10000


class GenericCMSClient:
    """Generic REST API connector for any CMS."""

    def __init__(
        self,
        provider_name: str,
        base_url: str,
        auth_header: dict[str, str],
        rate_limiter: SlidingWindowRateLimiter,
        endpoints: Optional[list[CMSEndpoint]] = None,
    ):
        self.provider_name = provider_name
        self.rate_limiter = rate_limiter
        self.client = IntegrationHTTPClient(
            provider=provider_name,
            base_url=base_url,
            retry_config=RetryConfig(max_retries=3),
        )
        self._auth_header = auth_header
        self._endpoints: dict[str, CMSEndpoint] = {}
        if endpoints:
            for ep in endpoints:
                self._endpoints[ep.name] = ep
                self.rate_limiter.register(f"{provider_name}:{ep.name}", [
                    RateLimit(requests=ep.rate_limit_rps, window_seconds=1),
                    RateLimit(requests=ep.rate_limit_daily, window_seconds=86400),
                ])

    async def call(
        self,
        endpoint_name: str,
        path_params: Optional[dict] = None,
        query_params: Optional[dict] = None,
        body: Optional[dict] = None,
    ) -> Any:
        """Execute a configured endpoint."""
        ep = self._endpoints.get(endpoint_name)
        if not ep:
            raise ValueError(f"Unknown endpoint: {endpoint_name}")

        path = ep.path
        if path_params:
            path = path.format(**path_params)

        await self.rate_limiter.acquire(f"{self.provider_name}:{endpoint_name}")

        resp = await self.client.request(
            ep.method, path,
            headers=self._auth_header,
            params=query_params,
            json=body,
        )

        if resp.status_code == 204:
            return None
        return resp.json()

    async def close(self) -> None:
        await self.client.close()
```

---

## 15. Notification Integrations

### 15.1 Slack API

```python
"""
integrations/notifications/slack.py
Slack integration via Webhooks and Bot API.
"""

import logging
from typing import Optional

import httpx

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit

logger = logging.getLogger(__name__)


class SlackClient:
    """Slack notification client (webhook + bot API)."""

    PROVIDER = "slack"

    def __init__(
        self,
        webhook_url: Optional[str] = None,
        bot_token: Optional[str] = None,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
    ):
        self.webhook_url = webhook_url
        self.bot_token = bot_token
        self.rate_limiter = rate_limiter

        if bot_token:
            self.client = IntegrationHTTPClient(
                provider=self.PROVIDER,
                base_url="https://slack.com/api",
                retry_config=RetryConfig(max_retries=3),
            )
        else:
            self.client = None

        if rate_limiter:
            rate_limiter.register(self.PROVIDER, [
                RateLimit(requests=1, window_seconds=1),  # Webhook: 1/sec
                RateLimit(requests=50, window_seconds=60),  # Bot: 50/min
            ])

    async def send_webhook(
        self,
        text: str,
        channel: Optional[str] = None,
        username: str = "SEO Platform",
        icon_emoji: str = ":chart_with_upwards_trend:",
        blocks: Optional[list[dict]] = None,
    ) -> bool:
        """Send message via incoming webhook."""
        if not self.webhook_url:
            raise ValueError("Webhook URL not configured")

        if self.rate_limiter:
            await self.rate_limiter.acquire(self.PROVIDER)

        payload = {
            "text": text,
            "username": username,
            "icon_emoji": icon_emoji,
        }
        if channel:
            payload["channel"] = channel
        if blocks:
            payload["blocks"] = blocks

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.webhook_url, json=payload)
            return resp.status_code == 200 and resp.text == "ok"

    async def send_bot_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[list[dict]] = None,
        thread_ts: Optional[str] = None,
    ) -> dict:
        """Send message via Bot API."""
        if not self.bot_token or not self.client:
            raise ValueError("Bot token not configured")

        if self.rate_limiter:
            await self.rate_limiter.acquire(self.PROVIDER)

        payload = {"channel": channel, "text": text}
        if blocks:
            payload["blocks"] = blocks
        if thread_ts:
            payload["thread_ts"] = thread_ts

        headers = {"Authorization": f"Bearer {self.bot_token}"}
        resp = await self.client.request("POST", "/chat.postMessage", headers=headers, json=payload)
        return resp.json()

    async def send_seo_alert(
        self,
        channel: str,
        title: str,
        message: str,
        severity: str = "info",
        fields: Optional[list[dict]] = None,
    ) -> dict:
        """Send a formatted SEO alert with severity coloring."""
        color_map = {
            "critical": "#FF0000",
            "warning": "#FFA500",
            "info": "#36A64F",
            "success": "#2ECC71",
        }

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🔍 {title}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
        ]

        if fields:
            field_blocks = []
            for f in fields[:10]:
                field_blocks.append({
                    "type": "mrkdwn",
                    "text": f"*{f['title']}*\n{f['value']}",
                })
            blocks.append({
                "type": "section",
                "fields": field_blocks,
            })

        blocks.append({"type": "divider"})

        if self.bot_token:
            return await self.send_bot_message(channel, message, blocks=blocks)
        else:
            await self.send_webhook(message, channel=channel, blocks=blocks)
            return {"ok": True}

    async def close(self) -> None:
        if self.client:
            await self.client.close()
```

### 15.2 Discord API

```python
"""
integrations/notifications/discord.py
Discord webhook integration.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class DiscordClient:
    """Discord webhook notification client."""

    def __init__(
        self,
        webhook_url: str,
        rate_limiter=None,
    ):
        self.webhook_url = webhook_url
        self.rate_limiter = rate_limiter

    async def send(
        self,
        content: str,
        username: str = "SEO Platform",
        avatar_url: Optional[str] = None,
        embeds: Optional[list[dict]] = None,
    ) -> bool:
        """Send a Discord webhook message."""
        if self.rate_limiter:
            await self.rate_limiter.acquire("discord")

        payload = {"content": content, "username": username}
        if avatar_url:
            payload["avatar_url"] = avatar_url
        if embeds:
            payload["embeds"] = embeds

        async with httpx.AsyncClient() as client:
            resp = await client.post(self.webhook_url, json=payload)
            return resp.status_code in (200, 204)

    async def send_seo_alert(
        self,
        title: str,
        description: str,
        severity: str = "info",
        fields: Optional[list[dict]] = None,
        url: Optional[str] = None,
    ) -> bool:
        """Send a rich embed SEO alert."""
        color_map = {
            "critical": 0xFF0000,
            "warning": 0xFFA500,
            "info": 0x36A64F,
            "success": 0x2ECC71,
        }

        embed = {
            "title": f"🔍 {title}",
            "description": description,
            "color": color_map.get(severity, 0x36A64F),
        }
        if url:
            embed["url"] = url
        if fields:
            embed["fields"] = [
                {"name": f["title"], "value": f["value"], "inline": f.get("inline", False)}
                for f in fields[:25]
            ]

        return await self.send(content="", embeds=[embed])
```

### 15.3 Email (SMTP)

```python
"""
integrations/notifications/email.py
SMTP email notification client.
"""

import asyncio
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class EmailNotificationClient:
    """SMTP email client for notifications and reports."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_email: str,
        use_tls: bool = True,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    async def send(
        self,
        to: list[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        cc: Optional[list[str]] = None,
        bcc: Optional[list[str]] = None,
        reply_to: Optional[str] = None,
    ) -> bool:
        """Send an email notification."""
        msg = MIMEMultipart("alternative")
        msg["From"] = self.from_email
        msg["To"] = ", ".join(to)
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = ", ".join(cc)
        if reply_to:
            msg["Reply-To"] = reply_to

        if body_text:
            msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        all_recipients = to + (cc or []) + (bcc or [])

        # Run SMTP in thread pool since it's blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._send_smtp, msg, all_recipients)
        return True

    def _send_smtp(self, msg: MIMEMultipart, recipients: list[str]) -> None:
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            if self.use_tls:
                server.starttls()
            server.login(self.username, self.password)
            server.sendmail(self.from_email, recipients, msg.as_string())
        logger.info("Sent email to %s: %s", recipients, msg["Subject"])

    async def send_report(
        self,
        to: list[str],
        subject: str,
        report_html: str,
        report_name: str = "SEO Report",
    ) -> bool:
        """Send a formatted report email."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="utf-8"></head>
        <body style="font-family: -apple-system, sans-serif; max-width: 800px; margin: 0 auto;">
            <div style="background: #1a1a2e; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">🔍 {report_name}</h1>
                <p style="color: #888; margin: 5px 0 0;">{subject}</p>
            </div>
            <div style="padding: 20px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
                {report_html}
            </div>
            <p style="color: #888; font-size: 12px; text-align: center; margin-top: 20px;">
                Sent by SEO Platform • {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}
            </p>
        </body>
        </html>
        """
        return await self.send(to=to, subject=subject, body_html=html)
```

### 15.4 Telegram Bot API

```python
"""
integrations/notifications/telegram.py
Telegram Bot API integration.
"""

import logging
from typing import Optional

from integrations.base.client import IntegrationHTTPClient, RetryConfig
from integrations.base.rate_limiter import SlidingWindowRateLimiter, RateLimit

logger = logging.getLogger(__name__)


class TelegramBotClient:
    """Telegram Bot API client for notifications."""

    PROVIDER = "telegram"
    BASE_URL = "https://api.telegram.org"

    def __init__(
        self,
        bot_token: str,
        rate_limiter: Optional[SlidingWindowRateLimiter] = None,
    ):
        self.bot_token = bot_token
        self.rate_limiter = rate_limiter
        self.client = IntegrationHTTPClient(
            provider=self.PROVIDER,
            base_url=f"{self.BASE_URL}/bot{bot_token}",
            retry_config=RetryConfig(max_retries=3),
        )
        if rate_limiter:
            rate_limiter.register(self.PROVIDER, [
                RateLimit(requests=30, window_seconds=1),      # 30 msgs/sec global
                RateLimit(requests=20, window_seconds=60),     # 20 msgs/min per chat
            ])

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str = "HTML",
        disable_web_page_preview: bool = True,
        disable_notification: bool = False,
    ) -> dict:
        """Send a message."""
        if self.rate_limiter:
            await self.rate_limiter.acquire(self.PROVIDER)

        resp = await self.client.request(
            "POST", "/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
                "disable_notification": disable_notification,
            },
        )
        return resp.json()

    async def send_seo_alert(
        self,
        chat_id: str,
        title: str,
        message: str,
        severity: str = "info",
        url: Optional[str] = None,
    ) -> dict:
        """Send a formatted SEO alert."""
        emoji_map = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵",
            "success": "🟢",
        }
        emoji = emoji_map.get(severity, "🔵")

        text = f"{emoji} <b>{title}</b>\n\n{message}"
        if url:
            text += f'\n\n<a href="{url}">View Details →</a>'

        return await self.send_message(chat_id, text)

    async def send_report_summary(
        self,
        chat_id: str,
        report_name: str,
        metrics: list[dict],
        period: str = "Last 7 days",
    ) -> dict:
        """Send a formatted metrics summary."""
        lines = [f"📊 <b>{report_name}</b>", f"📅 {period}", ""]

        for m in metrics:
            direction = "📈" if m.get("trend", 0) > 0 else "📉" if m.get("trend", 0) < 0 else "➡️"
            lines.append(f"{direction} <b>{m['name']}</b>: {m['value']}")
            if "change" in m:
                lines.append(f"   Change: {m['change']}")

        text = "\n".join(lines)
        return await self.send_message(chat_id, text)

    async def get_updates(self, offset: Optional[int] = None, limit: int = 100) -> list[dict]:
        """Get pending updates (for command handling)."""
        params = {"limit": limit}
        if offset:
            params["offset"] = offset
        resp = await self.client.request("POST", "/getUpdates", json=params)
        return resp.json().get("result", [])

    async def close(self) -> None:
        await self.client.close()
```

---

## Summary of Integrations

| # | Integration | Auth | Rate Limit | Cache TTL | Primary Use |
|---|------------|------|-----------|-----------|-------------|
| 1 | Google Search Console | OAuth 2.0 | 10/min, 2K/day | 6h | Search performance data |
| 2 | Google Analytics 4 | OAuth 2.0 | 100/min, 10K/day | 1h | Traffic & conversions |
| 3 | Bing Webmaster Tools | API Key | 20/min, 1K/day | 6h | Bing search data |
| 4 | Yandex Webmaster | OAuth 2.0 | 10/sec | 6h | Yandex search data |
| 5 | Naver Search | API Key | 10/sec, 25K/day | 1h | Naver SERP monitoring |
| 6 | Gmail API | OAuth 2.0 | 5/sec, 2K/day | — | Outreach execution |
| 7 | Exa AI | Bearer Token | 5/sec | 1h | Semantic search & extraction |
| 8 | Tavily | API Key | 5/sec | 1h | AI-optimized research |
| 9 | SerpAPI | API Key | 10/min | 2h | Multi-engine SERP data |
| 10 | Ahrefs API | Bearer Token | 10/sec | 12h | Backlinks & keywords |
| 11 | PageSpeed Insights | API Key | 25/100s | 6h | Core Web Vitals |
| 12 | WordPress | App Password | 30/min | — | Content publishing |
| 13 | Webflow | Bearer Token | 60/min | — | Content publishing |
| 14 | Shopify | Access Token | 2/sec | — | Product/SEO management |
| 15 | Slack | Webhook/Bot | 1/sec | — | Notifications |
| 16 | Discord | Webhook | 5/sec | — | Notifications |
| 17 | Email | SMTP/TLS | Per SMTP | — | Report delivery |
| 18 | Telegram | Bot Token | 30/sec | — | Notifications |

---

## Dependency Requirements

```txt
# requirements-integrations.txt
httpx>=0.27.0
redis>=5.0.0
aiofiles>=23.0.0
prometheus-client>=0.19.0
```

---

## Environment Variables

```bash
# .env.integration
# Google OAuth (shared for GSC, GA4, Gmail)
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
GOOGLE_REDIRECT_URI=http://localhost:8080/callback

# GSC
GSC_PROPERTY=sc-domain:example.com

# GA4
GA4_PROPERTY_ID=properties/123456789

# Bing Webmaster
BING_WEBMASTER_API_KEY=...

# Yandex
YANDEX_CLIENT_ID=...
YANDEX_CLIENT_SECRET=...

# Naver
NAVER_CLIENT_ID=...
NAVER_CLIENT_SECRET=...

# Exa AI
EXA_API_KEY=...

# Tavily
TAVILY_API_KEY=...

# SerpAPI
SERPAPI_API_KEY=...

# Ahrefs
AHREFS_API_KEY=...

# PageSpeed Insights
PAGESPEED_API_KEY=...

# WordPress
WP_SITE_URL=https://example.com
WP_USERNAME=admin
WP_APP_PASSWORD=xxxx xxxx xxxx xxxx

# Webflow
WEBFLOW_API_TOKEN=...

# Shopify
SHOPIFY_SHOP_DOMAIN=mystore
SHOPIFY_ACCESS_TOKEN=shpca_...

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
SLACK_BOT_TOKEN=xoxb-...

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Email (SMTP)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_FROM=seo@example.com

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Redis (for rate limiter + cache)
REDIS_URL=redis://localhost:6379/0
```
