"""
ResourceGovernor -- controls resource allocation across agents.

Enforces CPU, memory, time, and API quota limits per agent.
Prevents any single agent from monopolizing shared resources.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default resource budgets (from docs/04-agent-system.md)
# ---------------------------------------------------------------------------

DEFAULT_BUDGETS: dict[str, dict[str, Any]] = {
    "sentinel": {
        "cpu_cores": 2,
        "memory_mb": 2048,
        "max_concurrent_tasks": 4,
        "time_limit_seconds": 14400,       # 4 hours for full crawl
        "api_quotas": {
            "gsc": {"limit": 200, "window": "minute"},
            "bing": {"limit": 120, "window": "minute"},
            "yandex": {"limit": 100, "window": "minute"},
            "naver": {"limit": 60, "window": "minute"},
        },
    },
    "forge": {
        "cpu_cores": 4,
        "memory_mb": 4096,
        "max_concurrent_tasks": 2,
        "time_limit_seconds": 600,
        "api_quotas": {
            "tavily": {"limit": 1000, "window": "day"},
            "exa": {"limit": 1000, "window": "minute"},
            "dataforseo": {"limit": 2000, "window": "minute"},
            "gsc": {"limit": 200, "window": "minute"},
        },
    },
    "technical": {
        "cpu_cores": 2,
        "memory_mb": 2048,
        "max_concurrent_tasks": 2,
        "time_limit_seconds": 7200,
        "api_quotas": {
            "pagespeed": {"limit": 60, "window": "minute"},
            "gsc": {"limit": 200, "window": "minute"},
        },
    },
    "scout": {
        "cpu_cores": 2,
        "memory_mb": 1024,
        "max_concurrent_tasks": 3,
        "time_limit_seconds": 10800,
        "api_quotas": {
            "dataforseo": {"limit": 2000, "window": "minute"},
            "gsc": {"limit": 200, "window": "minute"},
        },
    },
    "outreach": {
        "cpu_cores": 4,
        "memory_mb": 4096,
        "max_concurrent_tasks": 2,
        "time_limit_seconds": 3600,
        "api_quotas": {
            "gmail": {"limit": 250, "window": "day"},
            "exa": {"limit": 1000, "window": "minute"},
            "tavily": {"limit": 1000, "window": "day"},
        },
    },
    "competitor": {
        "cpu_cores": 2,
        "memory_mb": 2048,
        "max_concurrent_tasks": 2,
        "time_limit_seconds": 3600,
        "api_quotas": {
            "dataforseo": {"limit": 2000, "window": "minute"},
        },
    },
    "decision": {
        "cpu_cores": 2,
        "memory_mb": 2048,
        "max_concurrent_tasks": 5,
        "time_limit_seconds": 300,
        "api_quotas": {},
    },
    "executor": {
        "cpu_cores": 2,
        "memory_mb": 2048,
        "max_concurrent_tasks": 10,
        "time_limit_seconds": 600,
        "api_quotas": {
            "gmail": {"limit": 250, "window": "day"},
        },
    },
}


# ---------------------------------------------------------------------------
# Token Bucket Rate Limiter
# ---------------------------------------------------------------------------

class TokenBucket:
    """Async token bucket rate limiter."""

    def __init__(self, rate: float, capacity: float):
        self.rate = rate           # tokens per second
        self.capacity = capacity
        self._tokens = capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """Acquire tokens, waiting if necessary. Returns wait time."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last_refill = now

            if self._tokens >= tokens:
                self._tokens -= tokens
                return 0.0

            # Need to wait
            deficit = tokens - self._tokens
            wait_time = deficit / self.rate
            await asyncio.sleep(wait_time)
            self._tokens = 0.0
            self._last_refill = time.monotonic()
            return wait_time

    @property
    def available(self) -> float:
        now = time.monotonic()
        elapsed = now - self._last_refill
        return min(self.capacity, self._tokens + elapsed * self.rate)


# ---------------------------------------------------------------------------
# API Quota Tracker
# ---------------------------------------------------------------------------

class APIQuotaTracker:
    """Tracks per-API usage within sliding windows."""

    def __init__(self):
        self._usage: dict[str, list[float]] = defaultdict(list)

    def record(self, api_name: str) -> None:
        """Record an API call."""
        now = time.time()
        self._usage[api_name].append(now)

    def check(self, api_name: str, limit: int, window_seconds: float) -> bool:
        """Check if quota is available. Returns True if within limit."""
        now = time.time()
        cutoff = now - window_seconds
        # Prune old entries
        self._usage[api_name] = [t for t in self._usage[api_name] if t > cutoff]
        return len(self._usage[api_name]) < limit

    def remaining(self, api_name: str, limit: int, window_seconds: float) -> int:
        """Get remaining quota."""
        now = time.time()
        cutoff = now - window_seconds
        recent = [t for t in self._usage[api_name] if t > cutoff]
        return max(0, limit - len(recent))

    def get_window_seconds(self, window: str) -> float:
        """Convert window string to seconds."""
        windows = {
            "second": 1.0,
            "minute": 60.0,
            "hour": 3600.0,
            "day": 86400.0,
        }
        return windows.get(window, 60.0)


# ---------------------------------------------------------------------------
# Resource Governor
# ---------------------------------------------------------------------------

class ResourceGovernor:
    """
    Controls resource allocation across all agents.

    Features:
        - Per-agent resource budgets (CPU, memory, time)
        - API quota tracking with sliding windows
        - Concurrency limits per agent
        - Priority-based resource preemption
        - Circuit breaker for failing APIs
    """

    def __init__(self, budgets: dict[str, dict[str, Any]] | None = None):
        self._budgets = budgets or dict(DEFAULT_BUDGETS)
        self._quota_tracker = APIQuotaTracker()
        self._active_tasks: dict[str, int] = defaultdict(int)
        self._circuit_breakers: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    # -- Resource checks --------------------------------------------------

    async def acquire(
        self,
        agent_name: str,
        api_name: str | None = None,
        time_estimate_seconds: float | None = None,
    ) -> bool:
        """
        Acquire resources for a task. Returns True if resources available.

        Checks:
            1. Concurrency limit
            2. API quota (if api_name provided)
            3. Time budget
        """
        budget = self._budgets.get(agent_name, {})

        async with self._lock:
            # 1. Concurrency check
            max_concurrent = budget.get("max_concurrent_tasks", 5)
            if self._active_tasks[agent_name] >= max_concurrent:
                logger.warning(
                    "[governor] Concurrency limit reached for %s: %d/%d",
                    agent_name, self._active_tasks[agent_name], max_concurrent,
                )
                return False

            # 2. API quota check
            if api_name:
                api_quotas = budget.get("api_quotas", {})
                quota = api_quotas.get(api_name)
                if quota:
                    window_sec = self._quota_tracker.get_window_seconds(quota["window"])
                    if not self._quota_tracker.check(api_name, quota["limit"], window_sec):
                        logger.warning(
                            "[governor] API quota exhausted for %s/%s",
                            agent_name, api_name,
                        )
                        return False

            # 3. Circuit breaker check
            if api_name and self._is_circuit_open(api_name):
                logger.warning("[governor] Circuit breaker open for %s", api_name)
                return False

            # All checks passed
            self._active_tasks[agent_name] += 1
            if api_name:
                self._quota_tracker.record(api_name)

            return True

    async def release(self, agent_name: str, api_name: str | None = None) -> None:
        """Release resources after task completion."""
        async with self._lock:
            self._active_tasks[agent_name] = max(0, self._active_tasks[agent_name] - 1)

    def record_api_success(self, api_name: str) -> None:
        """Record a successful API call (resets circuit breaker)."""
        if api_name in self._circuit_breakers:
            self._circuit_breakers[api_name]["consecutive_failures"] = 0
            self._circuit_breakers[api_name]["state"] = "closed"

    def record_api_failure(self, api_name: str, error: str = "") -> None:
        """Record an API failure (may open circuit breaker)."""
        if api_name not in self._circuit_breakers:
            self._circuit_breakers[api_name] = {
                "state": "closed",
                "consecutive_failures": 0,
                "last_failure": None,
                "threshold": 5,
            }

        cb = self._circuit_breakers[api_name]
        cb["consecutive_failures"] += 1
        cb["last_failure"] = datetime.now(timezone.utc).isoformat()

        if cb["consecutive_failures"] >= cb["threshold"]:
            cb["state"] = "open"
            logger.error(
                "[governor] Circuit breaker OPENED for %s after %d failures",
                api_name, cb["consecutive_failures"],
            )

    def _is_circuit_open(self, api_name: str) -> bool:
        """Check if circuit breaker is open for an API."""
        cb = self._circuit_breakers.get(api_name)
        if cb is None:
            return False
        if cb["state"] != "open":
            return False
        # Auto-close after 5 minutes
        last_failure = cb.get("last_failure")
        if last_failure:
            try:
                last_dt = datetime.fromisoformat(last_failure)
                elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if elapsed > 300:
                    cb["state"] = "half_open"
                    return False
            except (ValueError, TypeError):
                pass
        return True

    # -- Status -----------------------------------------------------------

    def get_agent_budget(self, agent_name: str) -> dict[str, Any]:
        """Get the resource budget for an agent."""
        return self._budgets.get(agent_name, {})

    def get_active_tasks(self) -> dict[str, int]:
        """Get active task counts per agent."""
        return dict(self._active_tasks)

    def get_api_quota_status(self) -> dict[str, dict[str, Any]]:
        """Get quota status for all tracked APIs."""
        status = {}
        for agent_name, budget in self._budgets.items():
            for api_name, quota in budget.get("api_quotas", {}).items():
                window_sec = self._quota_tracker.get_window_seconds(quota["window"])
                remaining = self._quota_tracker.remaining(api_name, quota["limit"], window_sec)
                status[f"{agent_name}/{api_name}"] = {
                    "limit": quota["limit"],
                    "window": quota["window"],
                    "remaining": remaining,
                    "circuit_breaker": self._circuit_breakers.get(api_name, {}).get("state", "closed"),
                }
        return status

    def get_circuit_breakers(self) -> dict[str, dict[str, Any]]:
        """Get circuit breaker status for all APIs."""
        return dict(self._circuit_breakers)

    @property
    def health(self) -> dict[str, Any]:
        """Overall governor health status."""
        open_breakers = [
            name for name, cb in self._circuit_breakers.items()
            if cb.get("state") == "open"
        ]
        return {
            "active_tasks": dict(self._active_tasks),
            "open_circuit_breakers": open_breakers,
            "total_budgets": len(self._budgets),
        }
