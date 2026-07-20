"""Execution adapters for the agreed 13 SEO providers."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from proactive_core.integrations.base import ProviderAdapter, ResilientHttpClient


class DataForSEOAdapter(ProviderAdapter):
    """DataForSEO SERP, keyword, backlink, and on-page API client."""

    name = "dataforseo"

    def __init__(self, login: str, password: str) -> None:
        credentials = base64.b64encode(f"{login}:{password}".encode()).decode()
        self.http = ResilientHttpClient(
            self.name,
            base_url="https://api.dataforseo.com/v3",
            headers={"Authorization": f"Basic {credentials}"},
            requests_per_minute=200,
        )

    async def health(self) -> dict[str, Any]:
        """Check account status without creating a paid task."""
        return await self.http.request("GET", "/appendix/user_data")

    async def serp(
        self,
        keyword: str,
        *,
        engine: Literal["google", "bing", "yahoo", "youtube"] = "google",
        location_code: int = 2840,
        language_code: str = "en",
        device: Literal["desktop", "mobile"] = "desktop",
    ) -> dict[str, Any]:
        """Fetch one live advanced SERP result."""
        payload = [
            {
                "keyword": keyword,
                "location_code": location_code,
                "language_code": language_code,
                "device": device,
            }
        ]
        return await self.http.request("POST", f"/serp/{engine}/organic/live/advanced", json=payload)

    async def keyword_data(self, keywords: list[str]) -> dict[str, Any]:
        """Return normalized search-volume data for a bounded keyword batch."""
        return await self.http.request(
            "POST",
            "/keywords_data/google_ads/search_volume/live",
            json=[{"keywords": keywords[:1000], "location_code": 2840, "language_code": "en"}],
        )

    async def backlinks(self, target: str, limit: int = 100) -> dict[str, Any]:
        """Fetch backlinks for a domain or URL."""
        return await self.http.request("POST", "/backlinks/backlinks/live", json=[{"target": target, "limit": limit}])


class GoogleSearchConsoleAdapter(ProviderAdapter):
    """Google Search Console search analytics and URL inspection client."""

    name = "gsc"

    def __init__(self, access_token: str) -> None:
        self.http = ResilientHttpClient(
            self.name,
            base_url="https://searchconsole.googleapis.com",
            headers={"Authorization": f"Bearer {access_token}"},
            requests_per_minute=100,
        )

    async def health(self) -> dict[str, Any]:
        """List accessible sites as a connection check."""
        return await self.http.request("GET", "/webmasters/v3/sites")

    async def analytics(self, site_url: str, start_date: date, end_date: date, dimensions: list[str]) -> dict[str, Any]:
        """Query Search Analytics for a validated site property."""
        encoded_site = __import__("urllib.parse").parse.quote(site_url, safe="")
        return await self.http.request(
            "POST",
            f"/webmasters/v3/sites/{encoded_site}/searchAnalytics/query",
            json={
                "startDate": start_date.isoformat(),
                "endDate": end_date.isoformat(),
                "dimensions": dimensions,
                "rowLimit": 25_000,
            },
        )


class GmailAdapter(ProviderAdapter):
    """Gmail draft, thread, and approval-gated sending client."""

    name = "gmail"

    def __init__(self, access_token: str, *, live_actions_enabled: bool = False) -> None:
        self.live_actions_enabled = live_actions_enabled
        self.http = ResilientHttpClient(
            self.name,
            base_url="https://gmail.googleapis.com/gmail/v1/users/me",
            headers={"Authorization": f"Bearer {access_token}"},
            requests_per_minute=100,
        )

    async def health(self) -> dict[str, Any]:
        """Read the authenticated profile without sending mail."""
        return await self.http.request("GET", "/profile")

    async def create_draft(self, raw_mime_base64url: str, thread_id: str | None = None) -> dict[str, Any]:
        """Create an approval-ready Gmail draft."""
        message: dict[str, Any] = {"raw": raw_mime_base64url}
        if thread_id:
            message["threadId"] = thread_id
        return await self.http.request("POST", "/drafts", json={"message": message})

    async def send_draft(self, draft_id: str, *, approved: bool) -> dict[str, Any]:
        """Send only when both environment and per-action approval gates are open."""
        if not self.live_actions_enabled or not approved:
            return {"status": "approval_required", "draft_id": draft_id}
        return await self.http.request("POST", "/drafts/send", json={"id": draft_id})


class JsonApiAdapter(ProviderAdapter):
    """Configurable JSON API adapter for analytics, search, research, and CMS providers."""

    def __init__(
        self,
        name: str,
        base_url: str,
        *,
        headers: dict[str, str] | None = None,
        health_path: str = "/",
        live_actions_enabled: bool = False,
    ) -> None:
        self.name = name
        self.health_path = health_path
        self.live_actions_enabled = live_actions_enabled
        self.http = ResilientHttpClient(name, base_url=base_url, headers=headers)

    async def health(self) -> dict[str, Any]:
        """Execute the provider's configured read-only health request."""
        return await self.http.request("GET", self.health_path)

    async def read(self, path: str, **params: Any) -> dict[str, Any]:
        """Perform a normalized read operation."""
        return await self.http.request("GET", path, params=params)

    async def write(self, path: str, payload: dict[str, Any], *, approved: bool) -> dict[str, Any]:
        """Perform a provider mutation only when the execution gates allow it."""
        if not self.live_actions_enabled or not approved:
            return {"status": "approval_required", "provider": self.name, "path": path}
        return await self.http.request("POST", path, json=payload)


@dataclass(frozen=True, slots=True)
class ProviderDefinition:
    """Static connection metadata for one supported execution provider."""

    name: str
    auth: str
    base_url: str
    side_effecting: bool = False


PROVIDERS = {
    item.name: item
    for item in (
        ProviderDefinition("gsc", "oauth2", "https://searchconsole.googleapis.com"),
        ProviderDefinition("ga4", "oauth2", "https://analyticsdata.googleapis.com"),
        ProviderDefinition("bing", "oauth2", "https://ssl.bing.com/webmaster/api.svc/json"),
        ProviderDefinition("yandex", "oauth2", "https://api.webmaster.yandex.net/v4"),
        ProviderDefinition("naver", "oauth2", "https://searchadvisor.naver.com/api-console"),
        ProviderDefinition("gmail", "oauth2", "https://gmail.googleapis.com", True),
        ProviderDefinition("exa", "api_key", "https://api.exa.ai"),
        ProviderDefinition("tavily", "api_key", "https://api.tavily.com"),
        ProviderDefinition("dataforseo", "basic", "https://api.dataforseo.com/v3"),
        ProviderDefinition("pagespeed", "api_key", "https://www.googleapis.com/pagespeedonline/v5"),
        ProviderDefinition("wordpress", "oauth2_or_app_password", "https://example.invalid/wp-json/wp/v2", True),
        ProviderDefinition("webflow", "oauth2", "https://api.webflow.com/v2", True),
        ProviderDefinition("shopify", "oauth2", "https://example.invalid/admin/api", True),
    )
}
