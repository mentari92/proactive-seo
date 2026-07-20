"""Source agents integrated from ahmadasrizalmi/proactive-seo (original implementation).

These agents contain the business logic originally developed in the source repository.
Codex's canonical agents (in implementations.py) use formal Pydantic contracts and
the abstract Agent base class. The classes here are the richer, more detailed
implementations that can be adapted or called by the canonical agents.

Available agents and key classes:
  - SentinelAgent (crawler.py) — Multi-engine crawling, broken links, index monitoring
  - ForgeAgent (content.py) — Dual scoring (Google + AI Readiness), AEO/GEO optimization
  - TechnicalAgent (technical.py) — PageSpeed, schema generation, self-healing
  - ScoutAgent (rank.py) — SERP tracking, position alerts, competitor comparison
  - OutreachAgent (backlink.py) — HARO, broken link building, guest post, unlinked mentions
  - CompetitorAgent (competitor.py) — Content monitoring, keyword stealing, gap analysis
  - DecisionEngine (decision.py) — Priority scoring, resource allocation, triggers
  - ActionExecutor (executor.py) — Auto-fix, email sending, rollback management
"""

from proactive_core.agents.source_agents.backlink import (
    BrokenLinkBuilder,
    BrokenLinkOpportunity,
    CampaignTracker,
    FollowUpEngine,
    GuestPostOutreach,
    HAROResponseGenerator,
    LinkVerifier,
    OutreachAgent,
    UnlinkedMentionMonitor,
)
from proactive_core.agents.source_agents.competitor import (
    CompetitorAgent,
    CompetitorBacklinkAnalyzer,
    CompetitorContentMonitor,
    GapIdentifier,
    KeywordStealDetector,
)
from proactive_core.agents.source_agents.content import (
    AEOOptimizer,
    ContentGenerator,
    DualScorer,
    ForgeAgent,
    GEOOptimizer,
    InternalLinkEngine,
    KeywordEngine,
    OnPageAuditor,
)
from proactive_core.agents.source_agents.crawler import (
    BrokenLinkDetector,
    DomainRateLimiter,
    IndexStatusMonitor,
    RobotsParser,
    SentinelAgent,
    SitemapManager,
    URLFrontier,
)
from proactive_core.agents.source_agents.decision import (
    ConflictResolver,
    DecisionEngine,
    PriorityScorer,
    ProactiveTriggerRegistry,
    ResourceAllocator,
)
from proactive_core.agents.source_agents.executor import ActionExecutor, RollbackManager
from proactive_core.agents.source_agents.governor import (
    GovernorAgent,
)
from proactive_core.agents.source_agents.rank import (
    CompetitorRankComparator,
    LocalSERPTracker,
    PositionChangeAlerter,
    ScoutAgent,
    SERPFeatureDetector,
)
from proactive_core.agents.source_agents.registry import AgentRegistry
from proactive_core.agents.source_agents.scheduler import SchedulerAgent
from proactive_core.agents.source_agents.technical import (
    MultiEngineValidator,
    PageSpeedInsightsClient,
    SchemaMarkupEngine,
    SelfHealingEngine,
    TechnicalAgent,
)

__all__ = [
    # Backlink & Outreach
    "BrokenLinkBuilder",
    "BrokenLinkOpportunity",
    "CampaignTracker",
    "FollowUpEngine",
    "GuestPostOutreach",
    "HAROResponseGenerator",
    "LinkVerifier",
    "OutreachAgent",
    "UnlinkedMentionMonitor",
    # Competitor
    "CompetitorAgent",
    "CompetitorBacklinkAnalyzer",
    "CompetitorContentMonitor",
    "GapIdentifier",
    "KeywordStealDetector",
    # Content
    "AEOOptimizer",
    "ContentGenerator",
    "DualScorer",
    "ForgeAgent",
    "GEOOptimizer",
    "InternalLinkEngine",
    "KeywordEngine",
    "OnPageAuditor",
    # Crawler
    "BrokenLinkDetector",
    "DomainRateLimiter",
    "IndexStatusMonitor",
    "RobotsParser",
    "SentinelAgent",
    "SitemapManager",
    "URLFrontier",
    # Decision
    "ConflictResolver",
    "DecisionEngine",
    "PriorityScorer",
    "ProactiveTriggerRegistry",
    "ResourceAllocator",
    # Executor
    "ActionExecutor",
    "RollbackManager",
    # Governor
    "GovernorAgent",
    # Rank
    "CompetitorRankComparator",
    "LocalSERPTracker",
    "PositionChangeAlerter",
    "ScoutAgent",
    "SERPFeatureDetector",
    # Registry
    "AgentRegistry",
    # Scheduler
    "SchedulerAgent",
    # Technical
    "MultiEngineValidator",
    "PageSpeedInsightsClient",
    "SchemaMarkupEngine",
    "SelfHealingEngine",
    "TechnicalAgent",
]
