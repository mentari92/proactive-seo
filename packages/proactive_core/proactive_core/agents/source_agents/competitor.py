"""
agents/competitor.py
Competitor Agent - Monitors, detects, and identifies gaps.

Components:
- Content monitoring via Exa AI
- Keyword stealing detection via DataForSEO
- Backlink strategy analysis
- Gap identification (content, keyword, backlink)

State Machine:
IDLE -> MONITORING -> ANALYZING -> REPORTING -> IDLE
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class CompetitorState(str, Enum):
    IDLE = "idle"
    MONITORING = "monitoring"
    ANALYZING = "analyzing"
    REPORTING = "reporting"


@dataclass
class Competitor:
    """Competitor information."""

    domain: str
    priority: str = "medium"  # high, medium, low
    name: str = ""


@dataclass
class CompetitorContent:
    """New content detected from competitor."""

    competitor_domain: str
    url: str
    title: str
    published_date: str = ""
    targeted_keywords: list[str] = field(default_factory=list)
    content_summary: str = ""


@dataclass
class KeywordStealAlert:
    """Alert when competitor overtakes us for a keyword."""

    keyword: str
    competitor_domain: str
    competitor_new_position: int
    competitor_old_position: int
    our_position: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class CompetitorBacklink:
    """New backlink acquired by competitor."""

    competitor_domain: str
    source_url: str
    source_domain: str
    source_domain_rank: float
    anchor_text: str = ""
    link_type: str = ""  # guest_post, editorial, directory, etc.


@dataclass
class GapReport:
    """Competitor gap analysis report."""

    competitor_domain: str
    content_gaps: list[dict] = field(default_factory=list)
    keyword_gaps: list[dict] = field(default_factory=list)
    backlink_gaps: list[dict] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# --- Content Monitor ---


class CompetitorContentMonitor:
    """Monitor competitor content via Exa AI."""

    def __init__(self, exa_client):
        self.exa = exa_client

    async def find_new_content(
        self,
        competitor_domain: str,
        known_urls: Optional[set] = None,
    ) -> list[CompetitorContent]:
        """Find new content published by competitor."""
        if not self.exa:
            return []

        try:
            data = await self.exa.search(
                query=f"site:{competitor_domain}",
                num_results=20,
                type="keyword",
            )
            results = data.get("results", [])
            new_content = []

            for r in results:
                url = r.get("url", "")
                if known_urls and url in known_urls:
                    continue

                new_content.append(CompetitorContent(
                    competitor_domain=competitor_domain,
                    url=url,
                    title=r.get("title", ""),
                    published_date=r.get("publishedDate", ""),
                ))

            return new_content

        except Exception as e:
            logger.error("Content monitoring failed for %s: %s", competitor_domain, e)
            return []


# --- Keyword Steal Detector ---


class KeywordStealDetector:
    """Detect when competitors overtake us for tracked keywords."""

    def __init__(self, dataforseo_client, our_domain: str):
        self.dataforseo = dataforseo_client
        self.our_domain = our_domain

    async def detect(
        self,
        keywords: list[str],
        competitors: list[Competitor],
        location_code: int = 2840,
    ) -> list[KeywordStealAlert]:
        """
        Detect keyword stealing events.

        Returns:
            List of KeywordStealAlert objects.
        """
        alerts = []

        for keyword in keywords:
            try:
                serp_data = await self.dataforseo.google_serp(
                    keyword=keyword,
                    location_code=location_code,
                    depth=20,
                )

                our_pos_data = self.dataforseo.find_our_position(
                    serp_data, self.our_domain
                )
                our_pos = our_pos_data["position"] if our_pos_data else None

                comp_positions = self.dataforseo.find_competitor_positions(
                    serp_data, [c.domain for c in competitors]
                )

                for comp_pos in comp_positions:
                    if our_pos and comp_pos["position"] < our_pos:
                        alerts.append(KeywordStealAlert(
                            keyword=keyword,
                            competitor_domain=comp_pos["domain"],
                            competitor_new_position=comp_pos["position"],
                            competitor_old_position=0,  # Would need history
                            our_position=our_pos,
                        ))

            except Exception as e:
                logger.error("Keyword steal detection failed for '%s': %s", keyword, e)

        return alerts


# --- Competitor Backlink Analyzer ---


class CompetitorBacklinkAnalyzer:
    """Analyze competitor backlink strategies."""

    def __init__(self, dataforseo_client):
        self.dataforseo = dataforseo_client

    async def get_new_backlinks(
        self,
        competitor_domain: str,
        limit: int = 100,
    ) -> list[CompetitorBacklink]:
        """Get recently discovered backlinks for a competitor."""
        try:
            links = await self.dataforseo.get_new_backlinks(
                target=competitor_domain,
                limit=limit,
            )
            return [
                CompetitorBacklink(
                    competitor_domain=competitor_domain,
                    source_url=item.get("url_from", ""),
                    source_domain=item.get("domain_from", ""),
                    source_domain_rank=item.get("domain_rank", 0),
                    anchor_text=item.get("anchor", ""),
                )
                for item in links
            ]
        except Exception as e:
            logger.error("Backlink analysis failed for %s: %s", competitor_domain, e)
            return []

    async def get_backlink_summary(
        self,
        competitor_domain: str,
    ) -> dict:
        """Get backlink summary for a competitor."""
        try:
            data = await self.dataforseo.get_backlink_summary(
                target=competitor_domain
            )
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                result = tasks[0]["result"][0]
                return {
                    "domain_rank": result.get("domain_rank", 0),
                    "backlinks": result.get("backlinks", 0),
                    "referring_domains": result.get("referring_domains", 0),
                    "referring_main_domains": result.get("referring_main_domains", 0),
                }
        except Exception as e:
            logger.error("Backlink summary failed for %s: %s", competitor_domain, e)
        return {}

    async def find_link_gaps(
        self,
        competitor_domain: str,
        our_domain: str,
        limit: int = 100,
    ) -> list[dict]:
        """
        Find domains linking to competitor but not us.

        Returns:
            List of link opportunity dicts.
        """
        try:
            data = await self.dataforseo.get_domain_intersection(
                target1=competitor_domain,
                target2=our_domain,
                limit=limit,
            )
            tasks = data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                items = tasks[0]["result"][0].get("items", [])
                return [
                    {
                        "domain": item.get("domain", ""),
                        "domain_rank": item.get("domain_rank", 0),
                        "links_to_competitor": item.get("intersections", [{}])[0].get("count", 0),
                        "links_to_us": item.get("intersections", [{}])[-1].get("count", 0) if len(item.get("intersections", [])) > 1 else 0,
                    }
                    for item in items
                ]
        except Exception as e:
            logger.error("Link gap analysis failed: %s", e)
        return []


# --- Gap Identifier ---


class GapIdentifier:
    """Identify content, keyword, and backlink gaps."""

    def __init__(self, dataforseo_client, exa_client=None):
        self.dataforseo = dataforseo_client
        self.exa = exa_client

    async def identify_keyword_gaps(
        self,
        our_domain: str,
        competitor_domain: str,
    ) -> list[dict]:
        """Identify keywords competitor ranks for but we don't."""
        try:
            our_data = await self.dataforseo.get_site_keywords(
                target=our_domain, limit=500
            )
            comp_data = await self.dataforseo.get_site_keywords(
                target=competitor_domain, limit=500
            )

            our_keywords = set()
            tasks = our_data.get("tasks", [])
            if tasks and tasks[0].get("result"):
                for item in tasks[0]["result"][0].get("keywords", []):
                    our_keywords.add(item.get("keyword", "").lower())

            gaps = []
            comp_tasks = comp_data.get("tasks", [])
            if comp_tasks and comp_tasks[0].get("result"):
                for item in comp_tasks[0]["result"][0].get("keywords", []):
                    kw = item.get("keyword", "").lower()
                    if kw and kw not in our_keywords:
                        gaps.append({
                            "keyword": item.get("keyword", ""),
                            "search_volume": item.get("search_volume", 0),
                            "competitor_position": item.get("position", 0),
                        })

            gaps.sort(key=lambda x: x["search_volume"], reverse=True)
            return gaps[:50]

        except Exception as e:
            logger.error("Keyword gap identification failed: %s", e)
            return []

    async def identify_content_gaps(
        self,
        competitor_domain: str,
        niche_keywords: list[str],
    ) -> list[dict]:
        """Identify content topics competitor covers that we don't."""
        if not self.exa:
            return []

        gaps = []
        for keyword in niche_keywords[:5]:
            try:
                # Find competitor content for keyword
                comp_data = await self.exa.search(
                    query=f"site:{competitor_domain} {keyword}",
                    num_results=10,
                )
                for result in comp_data.get("results", []):
                    gaps.append({
                        "topic": keyword,
                        "competitor_url": result.get("url", ""),
                        "competitor_title": result.get("title", ""),
                    })
            except Exception as e:
                logger.error("Content gap detection failed for '%s': %s", keyword, e)

        return gaps


# --- Competitor Agent ---


class CompetitorAgent:
    """
    Competitor Agent - Monitors, detects, and identifies gaps.

    Integrates:
    - Content monitoring via Exa AI
    - Keyword stealing detection via DataForSEO
    - Backlink strategy analysis
    - Gap identification

    State Machine:
    IDLE -> MONITORING -> ANALYZING -> REPORTING -> IDLE
    """

    def __init__(
        self,
        dataforseo_client,
        our_domain: str,
        competitors: Optional[list[Competitor]] = None,
        exa_client=None,
        tavily_client=None,
    ):
        self.dataforseo = dataforseo_client
        self.our_domain = our_domain
        self.competitors = competitors or []
        self.exa = exa_client
        self.tavily = tavily_client

        self.state = CompetitorState.IDLE
        self.content_monitor = CompetitorContentMonitor(exa_client)
        self.keyword_steal_detector = KeywordStealDetector(dataforseo_client, our_domain)
        self.backlink_analyzer = CompetitorBacklinkAnalyzer(dataforseo_client)
        self.gap_identifier = GapIdentifier(dataforseo_client, exa_client)

        # In-memory stores
        self._known_content: dict[str, set] = {}  # domain -> set of known URLs

    async def monitor_content(self) -> list[CompetitorContent]:
        """
        Monitor all competitors for new content.

        Returns:
            List of new content detected.
        """
        self.state = CompetitorState.MONITORING
        new_content = []

        for comp in self.competitors:
            known = self._known_content.get(comp.domain, set())
            content = await self.content_monitor.find_new_content(
                competitor_domain=comp.domain,
                known_urls=known,
            )
            for c in content:
                known.add(c.url)
            self._known_content[comp.domain] = known
            new_content.extend(content)

        self.state = CompetitorState.IDLE

        if new_content:
            logger.info(
                "Detected %d new competitor content pieces", len(new_content)
            )

        return new_content

    async def detect_keyword_stealing(
        self,
        keywords: list[str],
    ) -> list[KeywordStealAlert]:
        """
        Detect keyword stealing events.

        Returns:
            List of keyword steal alerts.
        """
        self.state = CompetitorState.ANALYZING
        alerts = await self.keyword_steal_detector.detect(
            keywords=keywords,
            competitors=self.competitors,
        )
        self.state = CompetitorState.IDLE

        if alerts:
            logger.warning("Detected %d keyword steal events", len(alerts))

        return alerts

    async def analyze_backlinks(self) -> dict[str, list[CompetitorBacklink]]:
        """
        Analyze competitor backlink strategies.

        Returns:
            Dict of competitor_domain -> list of new backlinks.
        """
        self.state = CompetitorState.ANALYZING
        results = {}

        for comp in self.competitors:
            links = await self.backlink_analyzer.get_new_backlinks(comp.domain)
            results[comp.domain] = links

        self.state = CompetitorState.IDLE
        return results

    async def identify_gaps(
        self,
        niche_keywords: Optional[list[str]] = None,
    ) -> list[GapReport]:
        """
        Identify all gaps (keyword, content, backlink).

        Returns:
            List of GapReport objects per competitor.
        """
        self.state = CompetitorState.ANALYZING
        reports = []

        for comp in self.competitors:
            # Keyword gaps
            keyword_gaps = await self.gap_identifier.identify_keyword_gaps(
                our_domain=self.our_domain,
                competitor_domain=comp.domain,
            )

            # Content gaps
            content_gaps = []
            if niche_keywords:
                content_gaps = await self.gap_identifier.identify_content_gaps(
                    competitor_domain=comp.domain,
                    niche_keywords=niche_keywords,
                )

            # Backlink gaps
            backlink_gaps = await self.backlink_analyzer.find_link_gaps(
                competitor_domain=comp.domain,
                our_domain=self.our_domain,
            )

            reports.append(GapReport(
                competitor_domain=comp.domain,
                content_gaps=content_gaps,
                keyword_gaps=keyword_gaps,
                backlink_gaps=backlink_gaps,
            ))

        self.state = CompetitorState.IDLE
        return reports

    async def get_competitor_summary(self) -> dict:
        """Get summary of all competitors."""
        summaries = {}
        for comp in self.competitors:
            summary = await self.backlink_analyzer.get_backlink_summary(comp.domain)
            summary["new_content_count"] = len(
                self._known_content.get(comp.domain, set())
            )
            summaries[comp.domain] = summary
        return summaries
