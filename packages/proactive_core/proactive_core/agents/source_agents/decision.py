"""
agents/decision.py
Decision Engine - Central orchestrator with priority scoring and proactive triggers.

Priority Scoring: (Impact x Urgency x Confidence) / (Effort x Risk)
Resource Allocation: API budgets, compute time, LLM tokens
Conflict Resolution: Deduplication, prioritization, dependencies
Proactive Triggers: 8 rules for automatic action

State Machine:
RECEIVING -> SCORING -> ALLOCATING -> DISPATCHING -> MONITORING
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class DecisionState(str, Enum):
    RECEIVING = "receiving"
    SCORING = "scoring"
    ALLOCATING = "allocating"
    DISPATCHING = "dispatching"
    MONITORING = "monitoring"


class Priority(str, Enum):
    P0 = "P0"  # Critical - immediate action
    P1 = "P1"  # High - action within hours
    P2 = "P2"  # Medium - action within days
    P3 = "P3"  # Low - action when convenient


# --- Data Classes ---


@dataclass
class Task:
    """Task for the decision engine."""

    id: str
    type: str  # rank_drop, cwv_issue, broken_link, content_audit, haro, etc.
    title: str
    description: str
    source_agent: str
    target_agent: str = ""
    priority: Priority = Priority.P3
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Scoring inputs
    keyword_monthly_volume: int = 0
    current_position: int = 100
    page_traffic_pct: float = 0.0
    expected_da_boost: float = 0.0
    estimated_revenue_impact: float = 0.0
    drop_amount: int = 0
    deadline_hours: float = 0.0
    created_hours_ago: float = 0.0


@dataclass
class PriorityScore:
    """Priority score with breakdown."""

    raw: float
    normalized: float  # 0-100
    priority: Priority
    breakdown: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "raw": round(self.raw, 2),
            "normalized": round(self.normalized, 1),
            "priority": self.priority.value,
            "breakdown": self.breakdown,
        }


@dataclass
class ResourceAllocation:
    """Resource allocation result."""

    agent: str
    api: str
    requested: int
    granted: int
    reason: str = ""


@dataclass
class Conflict:
    """Resource conflict between agents."""

    type: str  # api_budget, same_url_task, llm_contention
    resource: str
    claimants: list[dict] = field(default_factory=list)


@dataclass
class Resolution:
    """Conflict resolution result."""

    conflict: Conflict
    winner: str
    action: str  # grant_budget, merge_tasks, queue_losers
    losers: list[str] = field(default_factory=list)


@dataclass
class ProactiveTrigger:
    """Proactive trigger rule."""

    name: str
    condition: str
    action: str
    enabled: bool = True


@dataclass
class TriggerEvent:
    """Event that fires a proactive trigger."""

    trigger_name: str
    event_data: dict
    priority: Priority
    timestamp: datetime = field(default_factory=datetime.utcnow)


# --- Priority Scorer ---


class PriorityScorer:
    """
    Score tasks on impact x urgency x confidence / effort x risk.

    Formula: (Impact x Urgency x Confidence) / (Effort x max(Risk, 0.1))
    Normalized to 0-100.
    """

    def score_task(self, task: Task) -> PriorityScore:
        """
        Calculate priority score for a task.

        Impact (0-10): Expected SEO improvement
        Urgency (0-10): Time sensitivity
        Confidence (0-1): How certain we are this will work
        Effort (0-10): Resources required
        Risk (0-1): Probability of negative outcome
        """
        impact = self._score_impact(task)
        urgency = self._score_urgency(task)
        confidence = self._score_confidence(task)
        effort = self._score_effort(task)
        risk = self._score_risk(task)

        raw_score = (impact * urgency * confidence) / (effort * max(risk, 0.1))

        # Normalize to 0-100
        normalized = min(raw_score * 10, 100)

        # Apply priority class
        if normalized >= 80:
            priority = Priority.P0
        elif normalized >= 60:
            priority = Priority.P1
        elif normalized >= 40:
            priority = Priority.P2
        else:
            priority = Priority.P3

        return PriorityScore(
            raw=raw_score,
            normalized=normalized,
            priority=priority,
            breakdown={
                "impact": round(impact, 2),
                "urgency": round(urgency, 2),
                "confidence": round(confidence, 2),
                "effort": round(effort, 2),
                "risk": round(risk, 2),
            },
        )

    def _score_impact(self, task: Task) -> float:
        """Score expected SEO impact (0-10)."""
        factors = [
            min(task.keyword_monthly_volume / 10000, 1.0) * 3,  # Volume
            ((101 - min(task.current_position, 100)) / 100) * 2,  # Room to improve
            task.page_traffic_pct * 2,  # Traffic share
            task.expected_da_boost * 1,  # DA boost
            min(task.estimated_revenue_impact / 10000, 1.0) * 2,  # Revenue
        ]
        return min(sum(factors), 10.0)

    def _score_urgency(self, task: Task) -> float:
        """Score time sensitivity (0-10)."""
        base = 5.0

        if task.type == "haro" and task.deadline_hours < 2:
            return 10.0
        if task.type == "rank_drop" and task.drop_amount >= 5:
            return 9.0
        if task.type == "cwv_critical":
            return 8.0
        if task.type == "broken_link_spike":
            return 7.0
        if task.type == "outreach_reply":
            return 8.0
        if task.type == "competitor_overtake":
            return 7.0

        # Aging boost
        if task.created_hours_ago > 48:
            base += 2
        if task.created_hours_ago > 168:  # 1 week
            base += 1

        return min(base, 10.0)

    def _score_confidence(self, task: Task) -> float:
        """Score confidence (0-1)."""
        confidence_map = {
            "rank_drop": 0.8,
            "cwv_issue": 0.9,
            "broken_link": 0.9,
            "content_audit": 0.7,
            "haro": 0.5,
            "guest_post": 0.4,
            "unlinked_mention": 0.6,
            "competitor_overtake": 0.7,
            "keyword_gap": 0.6,
        }
        return confidence_map.get(task.type, 0.5)

    def _score_effort(self, task: Task) -> float:
        """Score resources required (0-10)."""
        effort_map = {
            "rank_drop": 3.0,
            "cwv_issue": 4.0,
            "broken_link": 2.0,
            "content_audit": 5.0,
            "haro": 6.0,
            "guest_post": 7.0,
            "unlinked_mention": 4.0,
            "competitor_overtake": 6.0,
            "keyword_gap": 3.0,
        }
        return effort_map.get(task.type, 5.0)

    def _score_risk(self, task: Task) -> float:
        """Score risk of negative outcome (0-1)."""
        risk_map = {
            "rank_drop": 0.2,
            "cwv_issue": 0.1,
            "broken_link": 0.1,
            "content_audit": 0.3,
            "haro": 0.4,
            "guest_post": 0.5,
            "unlinked_mention": 0.3,
            "competitor_overtake": 0.2,
            "keyword_gap": 0.2,
        }
        return risk_map.get(task.type, 0.3)


# --- Resource Allocator ---


class ResourceAllocator:
    """Allocate API budgets, compute time, and LLM tokens across agents."""

    def __init__(self):
        self.daily_budgets = {
            "dataforseo_requests": 167,  # ~5000/month
            "gmail_sends": 50,
            "exa_requests": 1000,
            "tavily_requests": 1000,
            "pagespeed_requests": 1000,
            "gsc_requests": 5000,
            "llm_tokens": 100000,
        }

        self.agent_allocations = {
            "sentinel": {"dataforseo": 0.05, "gsc": 0.40, "pagespeed": 0.10},
            "forge": {"dataforseo": 0.20, "exa": 0.40, "tavily": 0.50, "llm": 0.50, "gsc": 0.20},
            "technical": {"pagespeed": 0.80, "gsc": 0.20},
            "scout": {"dataforseo": 0.60, "gsc": 0.10},
            "outreach": {"gmail": 1.00, "exa": 0.40, "tavily": 0.30, "dataforseo": 0.50, "llm": 0.30},
            "competitor": {"exa": 0.20, "tavily": 0.20, "dataforseo": 0.15},
        }

        self._used_today: dict[str, dict[str, int]] = {}

    def allocate(self, agent: str, api: str, requested: int) -> ResourceAllocation:
        """Return how many requests the agent can make."""
        daily_total = self.daily_budgets.get(api, 0)
        agent_share = self.agent_allocations.get(agent, {}).get(api, 0)
        agent_budget = int(daily_total * agent_share)

        used = self._used_today.get(agent, {}).get(api, 0)
        remaining = max(0, agent_budget - used)

        # Allow burst from unallocated pool
        if remaining < requested:
            total_used = sum(
                self._used_today.get(a, {}).get(api, 0)
                for a in self._used_today
            )
            pool_remaining = max(0, daily_total - total_used)
            remaining = min(remaining + pool_remaining, requested)

        granted = min(requested, remaining)

        # Track usage
        if agent not in self._used_today:
            self._used_today[agent] = {}
        self._used_today[agent][api] = used + granted

        return ResourceAllocation(
            agent=agent,
            api=api,
            requested=requested,
            granted=granted,
            reason="ok" if granted == requested else "partial",
        )

    def get_utilization(self) -> dict:
        """Get budget utilization across all APIs."""
        utilization = {}
        for api, budget in self.daily_budgets.items():
            total_used = sum(
                self._used_today.get(a, {}).get(api, 0)
                for a in self._used_today
            )
            utilization[api] = {
                "budget": budget,
                "used": total_used,
                "remaining": max(0, budget - total_used),
                "utilization_pct": round(total_used / max(budget, 1) * 100, 1),
            }
        return utilization


# --- Conflict Resolver ---


class ConflictResolver:
    """Resolve conflicts when multiple agents want the same resource."""

    def resolve(self, conflicts: list[Conflict]) -> list[Resolution]:
        """Resolve a list of conflicts."""
        resolutions = []

        for conflict in conflicts:
            if conflict.type == "api_budget":
                # Higher priority claimant wins
                winner = max(conflict.claimants, key=lambda c: c.get("priority_score", 0))
                resolutions.append(Resolution(
                    conflict=conflict,
                    winner=winner.get("agent", ""),
                    action="grant_budget",
                    losers=[c.get("agent", "") for c in conflict.claimants if c != winner],
                ))

            elif conflict.type == "same_url_task":
                # Deduplicate
                winner = max(conflict.claimants, key=lambda c: c.get("priority_score", 0))
                resolutions.append(Resolution(
                    conflict=conflict,
                    winner=winner.get("agent", ""),
                    action="merge_tasks",
                    losers=[c.get("agent", "") for c in conflict.claimants if c != winner],
                ))

            elif conflict.type == "llm_contention":
                # Round-robin with priority weighting
                sorted_claimants = sorted(
                    conflict.claimants,
                    key=lambda c: -c.get("priority_score", 0),
                )
                resolutions.append(Resolution(
                    conflict=conflict,
                    winner=sorted_claimants[0].get("agent", "") if sorted_claimants else "",
                    action="queue_losers",
                    losers=[c.get("agent", "") for c in sorted_claimants[1:]],
                ))

        return resolutions


# --- Proactive Trigger Registry ---


class ProactiveTriggerRegistry:
    """
    8 proactive trigger rules for automatic action.

    1. Rank drop >=3 for top-10 keyword -> immediate content audit
    2. CWV regression below "good" -> auto-fix trigger
    3. Broken link rate >5% -> crawl escalation
    4. Competitor outranks for 3+ keywords -> counter-strategy
    5. Backlink acquired -> re-crawl + rank check
    6. Content published -> schema inject + sitemap submit
    7. HARO deadline <2h -> priority boost
    8. Email reply received -> immediate notification
    """

    TRIGGERS = {
        "rank_drop_critical": ProactiveTrigger(
            name="rank_drop_critical",
            condition="rank_drop >= 3 for top10_keyword",
            action="priority_content_audit",
        ),
        "cwv_regression": ProactiveTrigger(
            name="cwv_regression",
            condition="cwv_status == 'poor'",
            action="trigger_self_healing",
        ),
        "broken_link_spike": ProactiveTrigger(
            name="broken_link_spike",
            condition="broken_link_rate > 0.05",
            action="escalate_crawl",
        ),
        "competitor_overtake": ProactiveTrigger(
            name="competitor_overtake",
            condition="competitor_outanks >= 3 keywords",
            action="generate_counter_strategy",
        ),
        "backlink_acquired": ProactiveTrigger(
            name="backlink_acquired",
            condition="new_backlink_verified",
            action="recrawl_and_rankcheck",
        ),
        "content_published": ProactiveTrigger(
            name="content_published",
            condition="new_content_published",
            action="schema_inject_and_sitemap",
        ),
        "haro_deadline": ProactiveTrigger(
            name="haro_deadline",
            condition="haro_deadline < 2h",
            action="boost_haro_priority",
        ),
        "outreach_reply": ProactiveTrigger(
            name="outreach_reply",
            condition="email_reply_received",
            action="immediate_notification",
        ),
    }

    def evaluate(
        self,
        event_type: str,
        event_data: dict,
    ) -> list[TriggerEvent]:
        """
        Evaluate an event against all trigger rules.

        Returns:
            List of TriggerEvent objects if triggers fire.
        """
        events = []

        if event_type == "alert.rank_drop":
            drop = event_data.get("drop", 0)
            if abs(drop) >= 3:
                events.append(TriggerEvent(
                    trigger_name="rank_drop_critical",
                    event_data=event_data,
                    priority=Priority.P0,
                ))

        elif event_type == "technical.cwv_issue":
            status = event_data.get("status", "")
            if status == "poor":
                events.append(TriggerEvent(
                    trigger_name="cwv_regression",
                    event_data=event_data,
                    priority=Priority.P0,
                ))

        elif event_type == "issue.broken_link":
            events.append(TriggerEvent(
                trigger_name="broken_link_spike",
                event_data=event_data,
                priority=Priority.P1,
            ))

        elif event_type == "competitor.keyword_stealing":
            events.append(TriggerEvent(
                trigger_name="competitor_overtake",
                event_data=event_data,
                priority=Priority.P1,
            ))

        elif event_type == "backlink.verified":
            events.append(TriggerEvent(
                trigger_name="backlink_acquired",
                event_data=event_data,
                priority=Priority.P2,
            ))

        elif event_type == "content.generated":
            events.append(TriggerEvent(
                trigger_name="content_published",
                event_data=event_data,
                priority=Priority.P2,
            ))

        elif event_type == "haro.query":
            deadline_hours = event_data.get("deadline_hours", 24)
            if deadline_hours < 2:
                events.append(TriggerEvent(
                    trigger_name="haro_deadline",
                    event_data=event_data,
                    priority=Priority.P0,
                ))

        elif event_type == "outreach.reply_received":
            events.append(TriggerEvent(
                trigger_name="outreach_reply",
                event_data=event_data,
                priority=Priority.P0,
            ))

        return events


# --- Decision Engine ---


class DecisionEngine:
    """
    Central orchestrator - scores, allocates, resolves, triggers.

    Integrates:
    - Priority scoring: (Impact x Urgency x Confidence) / (Effort x Risk)
    - Resource allocation: API budgets across agents
    - Conflict resolution: Deduplication, prioritization
    - 8 proactive trigger rules

    State Machine:
    RECEIVING -> SCORING -> ALLOCATING -> DISPATCHING -> MONITORING
    """

    def __init__(self):
        self.state = DecisionState.RECEIVING
        self.priority_scorer = PriorityScorer()
        self.resource_allocator = ResourceAllocator()
        self.conflict_resolver = ConflictResolver()
        self.trigger_registry = ProactiveTriggerRegistry()

        # Task queue
        self._task_queue: list[tuple[Task, PriorityScore]] = []
        self._dispatched_tasks: list[dict] = []

    def receive_event(self, event_type: str, event_data: dict) -> list[dict]:
        """
        Receive an event and evaluate triggers.

        Returns:
            List of actions to dispatch.
        """
        self.state = DecisionState.RECEIVING

        # Evaluate proactive triggers
        trigger_events = self.trigger_registry.evaluate(event_type, event_data)

        actions = []
        for te in trigger_events:
            logger.info(
                "Proactive trigger fired: %s (priority=%s)",
                te.trigger_name, te.priority.value,
            )
            actions.append({
                "trigger": te.trigger_name,
                "action": self.trigger_registry.TRIGGERS[te.trigger_name].action,
                "priority": te.priority.value,
                "event_data": te.event_data,
            })

        return actions

    def score_and_queue(self, task: Task) -> PriorityScore:
        """Score a task and add to queue."""
        self.state = DecisionState.SCORING

        score = self.priority_scorer.score_task(task)
        task.priority = score.priority

        self._task_queue.append((task, score))
        self._task_queue.sort(key=lambda x: x[1].normalized, reverse=True)

        logger.info(
            "Task '%s' scored: %.1f (%s)",
            task.title, score.normalized, score.priority.value,
        )

        return score

    def get_next_task(self) -> Optional[tuple[Task, PriorityScore]]:
        """Get the highest priority task from queue."""
        if self._task_queue:
            return self._task_queue.pop(0)
        return None

    def dispatch_task(self, task: Task, score: PriorityScore) -> dict:
        """
        Dispatch a task with resource allocation.

        Returns:
            Dispatch result with allocated resources.
        """
        self.state = DecisionState.DISPATCHING

        # Allocate resources
        allocations = {}
        agent = task.target_agent
        for api in ["dataforseo", "gsc", "exa", "tavily", "gmail", "llm"]:
            alloc = self.resource_allocator.allocate(agent, api, 10)
            allocations[api] = alloc.granted

        dispatch = {
            "task_id": task.id,
            "task_type": task.type,
            "target_agent": task.target_agent,
            "priority": score.priority.value,
            "score": score.normalized,
            "allocations": allocations,
            "dispatched_at": datetime.utcnow().isoformat(),
        }

        self._dispatched_tasks.append(dispatch)

        logger.info(
            "Dispatched task '%s' to %s (priority=%s, score=%.1f)",
            task.title, task.target_agent, score.priority.value, score.normalized,
        )

        return dispatch

    def resolve_conflicts(self, conflicts: list[Conflict]) -> list[Resolution]:
        """Resolve resource conflicts."""
        return self.conflict_resolver.resolve(conflicts)

    def get_queue_status(self) -> dict:
        """Get current task queue status."""
        priority_counts = {}
        for priority in Priority:
            priority_counts[priority.value] = sum(
                1 for _, s in self._task_queue if s.priority == priority
            )

        return {
            "queue_depth": len(self._task_queue),
            "by_priority": priority_counts,
            "dispatched_today": len(self._dispatched_tasks),
            "resource_utilization": self.resource_allocator.get_utilization(),
        }

    def get_dispatched_tasks(self) -> list[dict]:
        """Get all dispatched tasks."""
        return self._dispatched_tasks.copy()
