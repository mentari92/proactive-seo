"""
agents/rank.py
Rank Agent (Scout) - Tracks SERP positions across multiple engines.

Components:
- Multi-engine SERP tracking via DataForSEO SERP API
- SERP feature detection (featured snippets, PAA, local pack, knowledge panel)
- Position change alerting (threshold-based)
- Competitor rank comparison
- Local SERP tracking

State Machine:
IDLE -> TRACKING -> ANALYZING -> ALERTING -> IDLE
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# --- State Machine ---


class ScoutState(str, Enum):
    IDLE = "idle"
    TRACKING = "tracking"
    ANALYZING = "analyzing"
    ALERTING = "alerting"


# --- Data Classes ---


@dataclass
class SERPFeatures:
    """Detected SERP features for a keyword."""

    has_featured_snippet: bool = False
    featured_snippet_domain: Optional[str] = None
    has_people_also_ask: bool = False
    paa_questions: list[str] = field(default_factory=list)
    has_local_pack: bool = False
    has_knowledge_graph: bool = False
    has_image_pack: bool = False
    has_video_carousel: bool = False
    has_top_stories: bool = False
    has_sitelinks: bool = False
    related_searches: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "has_featured_snippet": self.has_featured_snippet,
            "featured_snippet_domain": self.featured_snippet_domain,
            "has_people_also_ask": self.has_people_also_ask,
            "paa_questions": self.paa_questions,
            "has_local_pack": self.has_local_pack,
            "has_knowledge_graph": self.has_knowledge_graph,
            "has_image_pack": self.has_image_pack,
            "has_video_carousel": self.has_video_carousel,
            "has_top_stories": self.has_top_stories,
            "has_sitelinks": self.has_sitelinks,
            "related_searches": self.related_searches,
        }


@dataclass
class RankDelta:
    """Position change between two snapshots."""

    keyword: str
    engine: str
    previous_position: Optional[int] = None
    current_position: Optional[int] = None
    previous_url: Optional[str] = None
    current_url: Optional[str] = None
    change: int = 0  # Negative = drop, positive = gain

    @property
    def direction(self) -> str:
        if self.change > 0:
            return "up"
        elif self.change < 0:
            return "down"
        return "stable"

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "engine": self.engine,
            "previous_position": self.previous_position,
            "current_position": self.current_position,
            "previous_url": self.previous_url,
            "current_url": self.current_url,
            "change": self.change,
            "direction": self.direction,
        }


@dataclass
class RankResult:
    """Rank tracking result for a keyword."""

    keyword: str
    engines: dict[str, dict] = field(default_factory=dict)
    delta: Optional[RankDelta] = None
    features: Optional[SERPFeatures] = None
    competitor_positions: list[dict] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "engines": self.engines,
            "delta": self.delta.to_dict() if self.delta else None,
            "features": self.features.to_dict() if self.features else None,
            "competitor_positions": self.competitor_positions,
            "timestamp": self.timestamp,
        }


@dataclass
class RankAlert:
    """Alert for significant rank changes."""

    keyword: str
    engine: str
    alert_type: str  # "drop", "gain", "competitor_overtake", "feature_change"
    severity: str  # "P0", "P1", "P2"
    details: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        return {
            "keyword": self.keyword,
            "engine": self.engine,
            "alert_type": self.alert_type,
            "severity": self.severity,
            "details": self.details,
            "timestamp": self.timestamp,
        }


@dataclass
class RankSnapshot:
    """Historical rank snapshot."""

    keyword: str
    engine: str
    position: Optional[int]
    url: Optional[str]
    features: dict = field(default_factory=dict)
    competitor_positions: list[dict] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


# --- SERP Feature Detector ---


class SERPFeatureDetector:
    """Detect SERP features from DataForSEO response data."""

    def detect(self, serp_data: dict, engine: str = "google") -> SERPFeatures:
        """
        Detect SERP features from DataForSEO response.

        Args:
            serp_data: Raw DataForSEO SERP response
            engine: Search engine

        Returns:
            SERPFeatures with detected features.
        """
        features = SERPFeatures()

        tasks = serp_data.get("tasks", [])
        if not tasks or not tasks[0].get("result"):
            return features

        result = tasks[0]["result"]
        if not result:
            return features

        items = result[0].get("items", []) if isinstance(result, list) and result else []

        for item in items:
            item_type = item.get("type", "")

            # Featured Snippet
            if item_type == "featured_snippet":
                features.has_featured_snippet = True
                features.featured_snippet_domain = item.get("domain", "")

            # People Also Ask
            elif item_type == "people_also_ask":
                features.has_people_also_ask = True
                for q in item.get("items", []):
                    question = q.get("title", "") or q.get("question", "")
                    if question:
                        features.paa_questions.append(question)

            # Local Pack
            elif item_type in ("local_pack", "map"):
                features.has_local_pack = True

            # Knowledge Graph
            elif item_type == "knowledge_graph":
                features.has_knowledge_graph = True

            # Image Pack
            elif item_type == "images":
                features.has_image_pack = True

            # Video
            elif item_type in ("video", "video_carousel"):
                features.has_video_carousel = True

            # Top Stories
            elif item_type == "top_stories":
                features.has_top_stories = True

            # Sitelinks
            elif item_type == "sitelinks":
                features.has_sitelinks = True

            # Related Searches
            elif item_type == "related_searches":
                related = item.get("items", [])
                for r in related:
                    kw = r.get("keyword", "") or r.get("query", "")
                    if kw:
                        features.related_searches.append(kw)

        return features


# --- Position Change Alerter ---


class PositionChangeAlerter:
    """Generate alerts for significant position changes."""

    def __init__(
        self,
        rank_drop_threshold: int = 3,
        rank_gain_threshold: int = 5,
        competitor_overtake_alert: bool = True,
    ):
        self.rank_drop_threshold = rank_drop_threshold
        self.rank_gain_threshold = rank_gain_threshold
        self.competitor_overtake_alert = competitor_overtake_alert

    def evaluate(
        self,
        keyword: str,
        engine: str,
        current_position: Optional[int],
        previous_position: Optional[int],
        competitor_positions: Optional[list[dict]] = None,
        previous_competitor_positions: Optional[list[dict]] = None,
    ) -> list[RankAlert]:
        """
        Evaluate position changes and generate alerts.

        Returns:
            List of RankAlert objects.
        """
        alerts = []

        if current_position is None or previous_position is None:
            return alerts

        change = previous_position - current_position  # Positive = gain

        # Rank drop alert
        if change <= -self.rank_drop_threshold:
            alerts.append(RankAlert(
                keyword=keyword,
                engine=engine,
                alert_type="drop",
                severity="P0" if change <= -5 else "P1",
                details={
                    "previous_position": previous_position,
                    "current_position": current_position,
                    "change": change,
                },
            ))

        # Rank gain alert
        if change >= self.rank_gain_threshold:
            alerts.append(RankAlert(
                keyword=keyword,
                engine=engine,
                alert_type="gain",
                severity="P1",
                details={
                    "previous_position": previous_position,
                    "current_position": current_position,
                    "change": change,
                },
            ))

        # Competitor overtake alert
        if self.competitor_overtake_alert and competitor_positions and previous_competitor_positions:
            prev_map = {c["domain"]: c["position"] for c in previous_competitor_positions}
            for comp in competitor_positions:
                domain = comp.get("domain", "")
                comp_pos = comp.get("position", 0)
                prev_pos = prev_map.get(domain)
                if prev_pos and comp_pos < current_position and prev_pos > previous_position:
                    alerts.append(RankAlert(
                        keyword=keyword,
                        engine=engine,
                        alert_type="competitor_overtake",
                        severity="P1",
                        details={
                            "competitor": domain,
                            "competitor_position": comp_pos,
                            "our_position": current_position,
                        },
                    ))

        return alerts


# --- Competitor Rank Comparator ---


class CompetitorRankComparator:
    """Compare our rankings with competitors."""

    def compare(
        self,
        our_domain: str,
        serp_data: dict,
        competitor_domains: list[str],
    ) -> dict:
        """
        Compare our position with competitors in SERP data.

        Returns:
            Dict with our position and competitor positions.
        """
        tasks = serp_data.get("tasks", [])
        if not tasks or not tasks[0].get("result"):
            return {"our_position": None, "competitors": []}

        items = tasks[0]["result"][0].get("items", []) if tasks[0]["result"] else []

        our_position = None
        our_url = None
        competitors = []

        for item in items:
            url = item.get("url", "")
            domain = item.get("domain", "")
            position = item.get("rank_group", item.get("position", 0))

            if our_domain in url or our_domain in domain:
                our_position = position
                our_url = url

            for comp_domain in competitor_domains:
                if comp_domain in url or comp_domain in domain:
                    competitors.append({
                        "domain": comp_domain,
                        "position": position,
                        "url": url,
                        "title": item.get("title", ""),
                    })

        return {
            "our_position": our_position,
            "our_url": our_url,
            "competitors": competitors,
        }


# --- Local SERP Tracker ---


class LocalSERPTracker:
    """Track geo-specific rankings."""

    def __init__(self, dataforseo_client):
        self.dataforseo = dataforseo_client

    async def track_local(
        self,
        keyword: str,
        locations: list[dict],
        engine: str = "google",
    ) -> list[dict]:
        """
        Track local SERP positions for multiple locations.

        Args:
            keyword: Search query
            locations: List of {name, location_code} dicts
            engine: Search engine

        Returns:
            List of location-specific rank results.
        """
        results = []
        for loc in locations:
            try:
                serp_data = await self.dataforseo.local_serp(
                    keyword=keyword,
                    location_code=loc.get("location_code", 2840),
                )
                results.append({
                    "location": loc.get("name", ""),
                    "location_code": loc.get("location_code"),
                    "serp_data": serp_data,
                })
            except Exception as e:
                logger.error(
                    "Local SERP failed for %s at %s: %s",
                    keyword, loc.get("name"), e,
                )
                results.append({
                    "location": loc.get("name", ""),
                    "error": str(e),
                })

        return results


# --- Scout Agent (Rank Agent) ---


class ScoutAgent:
    """
    Rank Agent (Scout) - Tracks SERP positions across multiple engines.

    Integrates:
    - Multi-engine SERP tracking via DataForSEO
    - SERP feature detection (featured snippets, PAA, local pack)
    - Position change alerting
    - Competitor rank comparison
    - Local SERP tracking

    State Machine:
    IDLE -> TRACKING -> ANALYZING -> ALERTING -> IDLE
    """

    def __init__(
        self,
        dataforseo_client,
        our_domain: str,
        competitor_domains: Optional[list[str]] = None,
        engines: Optional[list[str]] = None,
        rank_drop_threshold: int = 3,
        rank_gain_threshold: int = 5,
    ):
        self.dataforseo = dataforseo_client
        self.our_domain = our_domain
        self.competitor_domains = competitor_domains or []
        self.engines = engines or ["google", "bing"]

        self.state = ScoutState.IDLE
        self.feature_detector = SERPFeatureDetector()
        self.alerter = PositionChangeAlerter(
            rank_drop_threshold=rank_drop_threshold,
            rank_gain_threshold=rank_gain_threshold,
        )
        self.comparator = CompetitorRankComparator()
        self.local_tracker = LocalSERPTracker(dataforseo_client)

        # In-memory rank history (would be DB in production)
        self._rank_history: dict[str, RankSnapshot] = {}

    async def track_rankings(
        self,
        keywords: list[str],
        location_code: int = 2840,
        depth: int = 100,
    ) -> list[RankResult]:
        """
        Track SERP positions for a batch of keywords across engines.

        Args:
            keywords: List of keywords to track
            location_code: DataForSEO location code
            depth: Number of results to fetch per keyword

        Returns:
            List of RankResult objects.
        """
        self.state = ScoutState.TRACKING
        results = []

        for keyword in keywords:
            engine_results = {}
            all_alerts = []
            delta: Optional[RankDelta] = None

            for engine in self.engines:
                try:
                    # Fetch SERP data
                    serp_data = await self.dataforseo.serp_search(
                        keyword=keyword,
                        engine=engine,
                        location_code=location_code,
                        depth=depth,
                    )

                    # Find our position
                    our_position = self.dataforseo.find_our_position(
                        serp_data, self.our_domain
                    )

                    # Detect SERP features
                    features = self.feature_detector.detect(serp_data, engine)

                    # Find competitor positions
                    competitor_positions = self.dataforseo.find_competitor_positions(
                        serp_data, self.competitor_domains
                    )

                    engine_results[engine] = {
                        "position": our_position["position"] if our_position else None,
                        "url": our_position["url"] if our_position else None,
                        "features": features.to_dict(),
                        "competitor_positions": competitor_positions,
                    }

                    # Compare with previous snapshot
                    history_key = f"{keyword}:{engine}"
                    previous = self._rank_history.get(history_key)

                    if previous:
                        delta = RankDelta(
                            keyword=keyword,
                            engine=engine,
                            previous_position=previous.position,
                            current_position=our_position["position"] if our_position else None,
                            previous_url=previous.url,
                            current_url=our_position["url"] if our_position else None,
                            change=(
                                (previous.position - our_position["position"])
                                if previous.position and our_position
                                else 0
                            ),
                        )

                        # Generate alerts
                        self.state = ScoutState.ANALYZING
                        alerts = self.alerter.evaluate(
                            keyword=keyword,
                            engine=engine,
                            current_position=our_position["position"] if our_position else None,
                            previous_position=previous.position,
                            competitor_positions=competitor_positions,
                            previous_competitor_positions=previous.competitor_positions,
                        )
                        all_alerts.extend(alerts)
                    else:
                        delta = None

                    # Store snapshot
                    self._rank_history[history_key] = RankSnapshot(
                        keyword=keyword,
                        engine=engine,
                        position=our_position["position"] if our_position else None,
                        url=our_position["url"] if our_position else None,
                        features=features.to_dict(),
                        competitor_positions=competitor_positions,
                    )

                except Exception as e:
                    logger.error(
                        "SERP tracking failed for '%s' on %s: %s",
                        keyword, engine, e,
                    )
                    engine_results[engine] = {
                        "position": None,
                        "error": str(e),
                    }

            self.state = ScoutState.ALERTING

            # Build result
            result = RankResult(
                keyword=keyword,
                engines=engine_results,
                delta=delta or RankDelta(keyword=keyword, engine=""),
                features=self.feature_detector.detect({}, "google"),
                competitor_positions=[
                    comp
                    for engine_data in engine_results.values()
                    for comp in engine_data.get("competitor_positions", [])
                ],
            )

            # Log alerts
            for alert in all_alerts:
                logger.warning(
                    "Rank alert: %s - %s for '%s' on %s",
                    alert.severity, alert.alert_type, alert.keyword, alert.engine,
                )

            results.append(result)

        self.state = ScoutState.IDLE
        return results

    async def track_single_keyword(
        self,
        keyword: str,
        engine: str = "google",
        location_code: int = 2840,
    ) -> RankResult:
        """Track a single keyword on a single engine."""
        results = await self.track_rankings(
            keywords=[keyword],
            location_code=location_code,
        )
        return results[0] if results else RankResult(keyword=keyword)

    async def track_local_rankings(
        self,
        keywords: list[str],
        locations: list[dict],
    ) -> list[dict]:
        """
        Track local SERP positions.

        Args:
            keywords: Keywords to track
            locations: List of {name, location_code} dicts

        Returns:
            List of local rank results.
        """
        results = []
        for keyword in keywords:
            local_results = await self.local_tracker.track_local(
                keyword=keyword,
                locations=locations,
            )
            results.append({
                "keyword": keyword,
                "locations": local_results,
            })
        return results

    async def get_competitor_comparison(
        self,
        keyword: str,
        engine: str = "google",
        location_code: int = 2840,
    ) -> dict:
        """Get detailed competitor comparison for a keyword."""
        serp_data = await self.dataforseo.serp_search(
            keyword=keyword,
            engine=engine,
            location_code=location_code,
            depth=100,
        )

        return self.comparator.compare(
            our_domain=self.our_domain,
            serp_data=serp_data,
            competitor_domains=self.competitor_domains,
        )

    def get_rank_history(
        self,
        keyword: str,
        engine: str = "google",
    ) -> Optional[RankSnapshot]:
        """Get the latest rank snapshot for a keyword."""
        history_key = f"{keyword}:{engine}"
        return self._rank_history.get(history_key)

    def get_tracked_keywords(self) -> list[str]:
        """Get all currently tracked keywords."""
        keywords = set()
        for key in self._rank_history:
            keyword = key.split(":")[0]
            keywords.add(keyword)
        return sorted(keywords)

    def get_alert_summary(self) -> dict:
        """Get summary of recent alerts."""
        # In production, this would query the alert store
        return {
            "total_alerts": 0,
            "p0_alerts": 0,
            "p1_alerts": 0,
            "recent_drops": [],
            "recent_gains": [],
        }
