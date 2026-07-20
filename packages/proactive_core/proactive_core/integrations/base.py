"""Resilient async HTTP and provider adapter infrastructure."""

from __future__ import annotations

import asyncio
import random
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any

import httpx


class ProviderError(RuntimeError):
    """Normalized external-provider failure."""

    def __init__(self, provider: str, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.provider = provider
        self.code = code
        self.retryable = retryable


class CircuitOpenError(ProviderError):
    """Raised while a provider circuit is open."""


@dataclass(slots=True)
class CircuitBreaker:
    """Failure-count circuit breaker with a timed recovery probe."""

    provider: str
    threshold: int = 5
    recovery_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    def before_request(self) -> None:
        """Reject calls until the recovery period allows a probe."""
        if self.opened_at is None:
            return
        if time.monotonic() - self.opened_at >= self.recovery_seconds:
            self.opened_at = None
            self.failures = 0
            return
        raise CircuitOpenError(self.provider, "circuit_open", "Provider circuit is open", retryable=True)

    def success(self) -> None:
        """Close the circuit after a successful response."""
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        """Record a failure and open the circuit at the threshold."""
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = time.monotonic()


class LocalRateLimiter:
    """Async sliding-window limiter used by fakes and single-process development."""

    def __init__(self, requests: int, period_seconds: float) -> None:
        self.requests = requests
        self.period_seconds = period_seconds
        self._timestamps: deque[float] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until one request fits in the configured window."""
        async with self._lock:
            now = time.monotonic()
            while self._timestamps and self._timestamps[0] <= now - self.period_seconds:
                self._timestamps.popleft()
            if len(self._timestamps) >= self.requests:
                await asyncio.sleep(self.period_seconds - (now - self._timestamps[0]))
            self._timestamps.append(time.monotonic())


class ResilientHttpClient:
    """Shared client with rate limiting, retry jitter, and circuit breaking."""

    def __init__(
        self,
        provider: str,
        *,
        base_url: str,
        headers: dict[str, str] | None = None,
        auth: httpx.Auth | tuple[str, str] | None = None,
        requests_per_minute: int = 60,
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider = provider
        self.breaker = CircuitBreaker(provider)
        self.limiter = LocalRateLimiter(requests_per_minute, 60)
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            auth=auth,
            timeout=httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 10)),
            transport=transport,
        )

    async def request(self, method: str, path: str, *, max_attempts: int = 4, **kwargs: Any) -> dict[str, Any]:
        """Send a JSON request and normalize provider errors."""
        last_error: ProviderError | None = None
        for attempt in range(max_attempts):
            self.breaker.before_request()
            await self.limiter.acquire()
            try:
                response = await self.client.request(method, path, **kwargs)
                if response.status_code in {408, 425, 429} or response.status_code >= 500:
                    raise ProviderError(
                        self.provider,
                        f"http_{response.status_code}",
                        f"{self.provider} returned {response.status_code}",
                        retryable=True,
                    )
                if response.status_code >= 400:
                    raise ProviderError(
                        self.provider,
                        f"http_{response.status_code}",
                        f"{self.provider} rejected the request",
                        retryable=False,
                    )
                self.breaker.success()
                payload: Any = response.json() if response.content else {}
                return payload if isinstance(payload, dict) else {"items": payload}
            except ProviderError as exc:
                last_error = exc
                self.breaker.failure()
                if not exc.retryable or attempt == max_attempts - 1:
                    raise
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = ProviderError(self.provider, "network_error", str(exc), retryable=True)
                self.breaker.failure()
                if attempt == max_attempts - 1:
                    raise last_error from exc
            await asyncio.sleep(min(8.0, (2**attempt) + random.uniform(0, 0.5)))
        if last_error is None:
            raise ProviderError(self.provider, "unknown", "Provider request failed", retryable=False)
        raise last_error

    async def close(self) -> None:
        """Close the underlying connection pool."""
        await self.client.aclose()


class ProviderAdapter(ABC):
    """Uniform contract implemented by live and deterministic fake providers."""

    name: str

    @abstractmethod
    async def health(self) -> dict[str, Any]:
        """Return a side-effect-free provider health result."""


class FakeProvider(ProviderAdapter):
    """Credential-free provider used in development and CI."""

    def __init__(self, name: str, fixtures: dict[str, Any] | None = None) -> None:
        self.name = name
        self.fixtures = fixtures or {}
        self.calls: list[dict[str, Any]] = []

    async def health(self) -> dict[str, Any]:
        """Report deterministic fake availability."""
        return {"provider": self.name, "status": "fake", "configured": True}

    async def execute(self, operation: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Record a fake call and return the named fixture."""
        self.calls.append({"operation": operation, "payload": payload})
        result = self.fixtures.get(operation, {"accepted": True})
        return result if isinstance(result, dict) else {"items": result}
