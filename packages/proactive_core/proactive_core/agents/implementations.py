"""Eight canonical SEO agents and their deterministic decision logic."""

from __future__ import annotations

import ipaddress
import socket
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from typing import Any, Literal
from urllib.parse import urljoin, urlparse

import httpx
from pydantic import BaseModel, Field, HttpUrl, field_validator

from proactive_core.agents.base import Agent, AgentContext


class CrawlInput(BaseModel):
    """Seed and safety limits for a crawl."""

    url: HttpUrl
    max_pages: int = Field(default=100, ge=1, le=10_000)
    max_depth: int = Field(default=3, ge=0, le=20)
    allow_private_networks: bool = False


class CrawledPage(BaseModel):
    """Normalized page result used by crawl and technical agents."""

    url: str
    status_code: int
    title: str | None = None
    links: list[str] = Field(default_factory=list)
    broken: bool = False


class CrawlOutput(BaseModel):
    """Bounded crawl result with broken-link rollup."""

    pages: list[CrawledPage]
    broken_links: list[str]
    total_discovered: int


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "a" and values.get("href"):
            self.links.append(values["href"] or "")
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title = (self.title or "") + data.strip()


async def _is_public_host(hostname: str) -> bool:
    try:
        addresses = (
            await __import__("asyncio")
            .get_running_loop()
            .getaddrinfo(hostname, None, family=socket.AF_UNSPEC, type=socket.SOCK_STREAM)
        )
    except socket.gaierror:
        return False
    for result in addresses:
        address = ipaddress.ip_address(result[4][0])
        if not address.is_global:
            return False
    return True


class SentinelAgent(Agent[CrawlInput, CrawlOutput]):
    """Same-origin crawler with SSRF guards and broken-link detection."""

    key = "sentinel"

    async def execute(self, input_data: CrawlInput, context: AgentContext) -> CrawlOutput:
        """Crawl bounded same-origin links and report 4xx/5xx pages."""
        seed = str(input_data.url)
        origin = urlparse(seed)
        if origin.scheme not in {"http", "https"} or not origin.hostname:
            raise ValueError("Only absolute HTTP(S) URLs can be crawled")
        if not input_data.allow_private_networks and not await _is_public_host(origin.hostname):
            raise ValueError("Private, loopback, and link-local crawl targets are blocked")
        queue: list[tuple[str, int]] = [(seed, 0)]
        seen: set[str] = set()
        pages: list[CrawledPage] = []
        timeout = httpx.Timeout(15, connect=5)
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": "ProActiveSEOBot/1.0 (+https://proactive-seo.local/bot)"},
        ) as client:
            while queue and len(pages) < input_data.max_pages:
                current, depth = queue.pop(0)
                if current in seen:
                    continue
                seen.add(current)
                try:
                    response = await client.get(current)
                    status = response.status_code
                    parser = _LinkParser()
                    if "text/html" in response.headers.get("content-type", ""):
                        parser.feed(response.text[:5_000_000])
                    normalized: list[str] = []
                    for href in parser.links:
                        candidate = urljoin(current, href).split("#", 1)[0]
                        parsed = urlparse(candidate)
                        if parsed.scheme in {"http", "https"} and parsed.netloc == origin.netloc:
                            normalized.append(candidate)
                            if depth < input_data.max_depth and candidate not in seen:
                                queue.append((candidate, depth + 1))
                    pages.append(
                        CrawledPage(
                            url=current,
                            status_code=status,
                            title=parser.title,
                            links=sorted(set(normalized)),
                            broken=status >= 400,
                        )
                    )
                except httpx.HTTPError:
                    pages.append(CrawledPage(url=current, status_code=0, broken=True))
        return CrawlOutput(
            pages=pages,
            broken_links=[page.url for page in pages if page.broken],
            total_discovered=len(seen) + len(queue),
        )


class TechnicalInput(BaseModel):
    """Page signals consumed by the technical audit."""

    url: str
    status_code: int = 200
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    h1_count: int = 1
    image_count: int = 0
    images_missing_alt: int = 0
    lcp_ms: int | None = None
    inp_ms: int | None = None
    cls: float | None = None
    schema_types: list[str] = Field(default_factory=list)


class TechnicalIssue(BaseModel):
    """One actionable technical SEO finding."""

    type: str
    severity: Literal["critical", "high", "medium", "low", "info"]
    message: str
    auto_fixable: bool


class TechnicalOutput(BaseModel):
    """Technical score, issues, and suggested schema."""

    score: float
    issues: list[TechnicalIssue]
    structured_data: dict[str, Any]


class TechnicalAgent(Agent[TechnicalInput, TechnicalOutput]):
    """Audit indexability, metadata, accessibility, CWV, and schema."""

    key = "technical"

    async def execute(self, input_data: TechnicalInput, context: AgentContext) -> TechnicalOutput:
        """Apply stable rules and generate safe JSON-LD suggestions."""
        issues: list[TechnicalIssue] = []
        checks: list[tuple[bool, str, Literal["critical", "high", "medium", "low", "info"], str, bool]] = [
            (input_data.status_code >= 400, "http_error", "critical", "Page is not reachable", False),
            (not input_data.title, "missing_title", "high", "Title tag is missing", True),
            (not input_data.meta_description, "missing_meta", "medium", "Meta description is missing", True),
            (input_data.h1_count != 1, "invalid_h1", "medium", "Page should contain exactly one H1", True),
            (
                input_data.images_missing_alt > 0,
                "missing_alt",
                "medium",
                "One or more images lack alternative text",
                True,
            ),
            (input_data.lcp_ms is not None and input_data.lcp_ms > 2500, "poor_lcp", "high", "LCP exceeds 2.5s", False),
            (input_data.inp_ms is not None and input_data.inp_ms > 200, "poor_inp", "high", "INP exceeds 200ms", False),
            (input_data.cls is not None and input_data.cls > 0.1, "poor_cls", "high", "CLS exceeds 0.1", False),
        ]
        for failed, issue_type, severity, message, fixable in checks:
            if failed:
                issues.append(
                    TechnicalIssue(
                        type=issue_type,
                        severity=severity,
                        message=message,
                        auto_fixable=fixable,
                    )
                )
        penalties = {"critical": 30, "high": 15, "medium": 8, "low": 3, "info": 0}
        score = max(0.0, 100.0 - sum(penalties[issue.severity] for issue in issues))
        schema = {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "url": input_data.url,
            "name": input_data.title or "",
            "description": input_data.meta_description or "",
        }
        return TechnicalOutput(score=score, issues=issues, structured_data=schema)


GOOGLE_WEIGHTS = {
    "title_optimization": 0.10,
    "meta_description": 0.08,
    "heading_structure": 0.10,
    "content_depth": 0.15,
    "keyword_usage": 0.12,
    "internal_linking": 0.08,
    "image_optimization": 0.05,
    "eeat_signals": 0.12,
    "url_structure": 0.05,
    "mobile_readability": 0.05,
    "schema_markup": 0.05,
    "page_speed_correlation": 0.05,
}
AI_WEIGHTS = {
    "question_answer_format": 0.15,
    "structured_data": 0.12,
    "entity_clarity": 0.12,
    "citation_worthiness": 0.10,
    "conversational_tone": 0.08,
    "featured_snippet_ready": 0.12,
    "passage_independence": 0.10,
    "freshness_signals": 0.08,
    "source_authority": 0.08,
    "ai_crawlability": 0.05,
}


class ContentAuditInput(BaseModel):
    """Normalized content signals, each scored from zero to 100."""

    google_signals: dict[str, float]
    ai_signals: dict[str, float]

    @field_validator("google_signals", "ai_signals")
    @classmethod
    def validate_scores(cls, values: dict[str, float]) -> dict[str, float]:
        if any(score < 0 or score > 100 for score in values.values()):
            raise ValueError("Content signals must be between zero and 100")
        return values


class ContentAuditOutput(BaseModel):
    """Google and AI-readiness scores with prioritized gaps."""

    google_score: float
    ai_readiness_score: float
    combined_score: float
    gaps: list[str]


class ForgeAgent(Agent[ContentAuditInput, ContentAuditOutput]):
    """Content auditor implementing the blueprint's dual scoring system."""

    key = "forge"

    @staticmethod
    def _weighted(signals: dict[str, float], weights: dict[str, float]) -> float:
        return round(sum(signals.get(key, 0) * weight for key, weight in weights.items()), 2)

    async def execute(self, input_data: ContentAuditInput, context: AgentContext) -> ContentAuditOutput:
        """Compute both score families without an LLM dependency."""
        google = self._weighted(input_data.google_signals, GOOGLE_WEIGHTS)
        ai = self._weighted(input_data.ai_signals, AI_WEIGHTS)
        gaps = sorted(
            [
                key
                for key, weight in {**GOOGLE_WEIGHTS, **AI_WEIGHTS}.items()
                if (input_data.google_signals | input_data.ai_signals).get(key, 0) < 70
            ],
            key=lambda key: ({**GOOGLE_WEIGHTS, **AI_WEIGHTS})[key],
            reverse=True,
        )
        return ContentAuditOutput(
            google_score=google,
            ai_readiness_score=ai,
            combined_score=round(google * 0.6 + ai * 0.4, 2),
            gaps=gaps,
        )


class RankInput(BaseModel):
    """SERP items for deterministic owned-domain position extraction."""

    keyword: str
    domain: str
    results: list[dict[str, Any]]


class RankOutput(BaseModel):
    """Owned rank and observed SERP features."""

    keyword: str
    position: int | None
    url: str | None
    features: list[str]


class ScoutAgent(Agent[RankInput, RankOutput]):
    """Normalize multi-engine SERP observations."""

    key = "scout"

    async def execute(self, input_data: RankInput, context: AgentContext) -> RankOutput:
        """Locate the first organic result owned by the project domain."""
        owned = next(
            (
                item
                for item in input_data.results
                if urlparse(str(item.get("url", ""))).hostname in {input_data.domain, f"www.{input_data.domain}"}
            ),
            None,
        )
        features = sorted({str(item["type"]) for item in input_data.results if item.get("type") != "organic"})
        return RankOutput(
            keyword=input_data.keyword,
            position=int(owned["rank_absolute"]) if owned and owned.get("rank_absolute") else None,
            url=str(owned["url"]) if owned else None,
            features=features,
        )


class OutreachInput(BaseModel):
    """Prospect and sequence input for approval-gated outreach."""

    campaign_type: Literal["haro", "broken_link", "guest_post", "unlinked_mention"]
    recipient: str
    subject: str
    body: str
    approved: bool = False
    replied: bool = False
    sent_at: datetime | None = None


class OutreachOutput(BaseModel):
    """Next safe outreach action and follow-up schedule."""

    action: Literal["draft", "send", "stop"]
    follow_ups: list[datetime]
    status: Literal["draft", "sent", "replied"]


class OutreachAgent(Agent[OutreachInput, OutreachOutput]):
    """Generate the 3/5/7-day sequence without performing email side effects."""

    key = "outreach"

    async def execute(self, input_data: OutreachInput, context: AgentContext) -> OutreachOutput:
        """Return a sequence plan; Action Executor owns real Gmail execution."""
        if input_data.replied:
            return OutreachOutput(action="stop", follow_ups=[], status="replied")
        anchor = input_data.sent_at or datetime.now(UTC)
        follow_ups = [anchor + timedelta(days=day) for day in (3, 5, 7)]
        return OutreachOutput(
            action="send" if input_data.approved else "draft",
            follow_ups=follow_ups,
            status="sent" if input_data.approved else "draft",
        )


class CompetitorInput(BaseModel):
    """Current project and competitor keyword positions."""

    own_positions: dict[str, int]
    competitor_positions: dict[str, int]


class CompetitorOutput(BaseModel):
    """Keywords where a competitor outranks the project."""

    opportunities: list[dict[str, int | str]]
    overtake_triggered: bool


class CompetitorAgent(Agent[CompetitorInput, CompetitorOutput]):
    """Detect keyword-stealing opportunities and proactive triggers."""

    key = "competitor"

    async def execute(self, input_data: CompetitorInput, context: AgentContext) -> CompetitorOutput:
        """Compare rankings and fire the three-keyword overtake threshold."""
        opportunities: list[dict[str, int | str]] = []
        for keyword, own_position in input_data.own_positions.items():
            competitor_position = input_data.competitor_positions.get(keyword)
            if competitor_position is not None and competitor_position < own_position:
                opportunities.append(
                    {
                        "keyword": keyword,
                        "own_position": own_position,
                        "competitor_position": competitor_position,
                    }
                )
        opportunities.sort(key=lambda item: int(item["own_position"]) - int(item["competitor_position"]), reverse=True)
        return CompetitorOutput(opportunities=opportunities, overtake_triggered=len(opportunities) >= 3)


class DecisionInput(BaseModel):
    """Priority factors from the decision-engine blueprint."""

    impact: float = Field(ge=0, le=10)
    urgency: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    effort: float = Field(gt=0, le=10)
    risk: float = Field(ge=0, le=1)


class DecisionOutput(BaseModel):
    """Normalized priority and execution policy."""

    raw: float
    score: float
    priority: Literal["P0", "P1", "P2", "P3"]
    execute: bool
    approval_required: bool


class DecisionEngineAgent(Agent[DecisionInput, DecisionOutput]):
    """Score impact times urgency times confidence over effort and risk."""

    key = "decision"

    async def execute(self, input_data: DecisionInput, context: AgentContext) -> DecisionOutput:
        """Normalize the blueprint formula to a bounded 0–100 score."""
        raw = (input_data.impact * input_data.urgency * input_data.confidence) / (
            input_data.effort * max(input_data.risk, 0.1)
        )
        score = min(raw * 10, 100)
        priority: Literal["P0", "P1", "P2", "P3"]
        if score >= 80:
            priority = "P0"
        elif score >= 60:
            priority = "P1"
        elif score >= 40:
            priority = "P2"
        else:
            priority = "P3"
        return DecisionOutput(
            raw=round(raw, 4),
            score=round(score, 2),
            priority=priority,
            execute=score >= 20,
            approval_required=priority in {"P2", "P3"},
        )


class ActionInput(BaseModel):
    """One potentially side-effecting action."""

    type: Literal["auto_fix", "publish_content", "send_email", "notify", "update_campaign"]
    payload: dict[str, Any]
    approved: bool = False
    rollback: dict[str, Any] = Field(default_factory=dict)


class ActionOutput(BaseModel):
    """Safe execution decision and rollback record."""

    status: Literal["approval_required", "dry_run", "executed"]
    action_type: str
    rollback: dict[str, Any]


class ActionExecutorAgent(Agent[ActionInput, ActionOutput]):
    """Final side-effect boundary for fixes, sends, and publication."""

    key = "executor"

    async def execute(self, input_data: ActionInput, context: AgentContext) -> ActionOutput:
        """Enforce approval and dry-run gates before external execution."""
        gated = input_data.type in {"publish_content", "send_email", "auto_fix"}
        if gated and not input_data.approved:
            return ActionOutput(status="approval_required", action_type=input_data.type, rollback=input_data.rollback)
        if context.dry_run:
            return ActionOutput(status="dry_run", action_type=input_data.type, rollback=input_data.rollback)
        return ActionOutput(status="executed", action_type=input_data.type, rollback=input_data.rollback)


AGENTS = {
    "sentinel": SentinelAgent(),
    "forge": ForgeAgent(),
    "technical": TechnicalAgent(),
    "scout": ScoutAgent(),
    "outreach": OutreachAgent(),
    "competitor": CompetitorAgent(),
    "decision": DecisionEngineAgent(),
    "executor": ActionExecutorAgent(),
}
