"""
BaseAgent -- abstract base class for all ProActive SEO agents.

Every agent follows the same lifecycle:
    IDLE -> WORKING -> REPORTING -> WAITING -> IDLE

All agents communicate through the Redis event bus and persist state
to PostgreSQL via the shared state store.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Agent state machine
# ---------------------------------------------------------------------------

class AgentState(str, Enum):
    """Canonical agent lifecycle states."""
    IDLE = "idle"
    INITIALIZING = "initializing"
    WORKING = "working"
    ANALYZING = "analyzing"
    REPORTING = "reporting"
    WAITING = "waiting"
    ERROR = "error"
    DEAD_LETTER = "dead_letter"


class AgentPriority(str, Enum):
    """Task priority levels matching the event schema."""
    P0 = "P0"   # Critical -- immediate
    P1 = "P1"   # High -- within 1 hour
    P2 = "P2"   # Normal -- within 24 hours
    P3 = "P3"   # Low -- best effort


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

class RetryPolicy:
    """Configurable retry with backoff strategies."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 10.0,
        backoff: str = "exponential",   # exponential | linear | none
        max_delay: float = 300.0,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff = backoff
        self.max_delay = max_delay

    def delay(self, attempt: int) -> float:
        if self.backoff == "exponential":
            return min(self.base_delay * (2 ** attempt), self.max_delay)
        elif self.backoff == "linear":
            return min(self.base_delay * (attempt + 1), self.max_delay)
        return 0.0


# ---------------------------------------------------------------------------
# Base Agent
# ---------------------------------------------------------------------------

class BaseAgent(abc.ABC):
    """
    Abstract base for every agent in the ProActive SEO system.

    Subclasses MUST implement:
        - agent_name  (class attribute)
        - execute()
        - get_triggers()

    Subclasses MAY override:
        - on_init()
        - on_shutdown()
        - handle_error()
    """

    # -- Class-level attributes (override in subclass) --
    agent_name: str = "base"
    agent_version: str = "1.0.0"

    # State machine transitions (override per agent)
    transitions: dict[AgentState, dict[str, AgentState]] = {
        AgentState.IDLE:        {"start": AgentState.WORKING},
        AgentState.WORKING:     {"complete": AgentState.REPORTING, "fail": AgentState.ERROR},
        AgentState.REPORTING:   {"done": AgentState.WAITING},
        AgentState.WAITING:     {"interval_elapsed": AgentState.IDLE, "override": AgentState.WORKING},
        AgentState.ERROR:       {"retry": AgentState.WORKING, "max_retries": AgentState.DEAD_LETTER},
    }

    def __init__(
        self,
        agent_id: str | None = None,
        event_bus: Any | None = None,
        db_session: Any | None = None,
        config: dict[str, Any] | None = None,
    ):
        self.agent_id = agent_id or f"{self.agent_name}-{uuid.uuid4().hex[:8]}"
        self.state = AgentState.IDLE
        self.event_bus = event_bus
        self.db_session = db_session
        self.config = config or {}
        self._started_at: datetime | None = None
        self._retry_count: int = 0
        self._last_error: str | None = None
        self._metrics: dict[str, int] = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "events_emitted": 0,
        }

    # -- Lifecycle hooks --------------------------------------------------

    async def on_init(self) -> None:
        """Called once when the agent starts. Override for setup logic."""
        pass

    async def on_shutdown(self) -> None:
        """Called when the agent is shutting down. Override for cleanup."""
        pass

    # -- State machine ----------------------------------------------------

    def transition(self, trigger: str) -> AgentState:
        """Apply a state transition. Returns new state."""
        current = self.transitions.get(self.state, {})
        if trigger not in current:
            logger.warning(
                "[%s] Invalid transition: %s -> %s (state=%s)",
                self.agent_name, self.state.value, trigger, self.state.value,
            )
            return self.state
        old_state = self.state
        self.state = current[trigger]
        logger.info(
            "[%s] State: %s -> %s (trigger=%s)",
            self.agent_name, old_state.value, self.state.value, trigger,
        )
        return self.state

    # -- Core abstract methods --------------------------------------------

    @abc.abstractmethod
    async def execute(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's primary work. Must be implemented by subclass."""
        ...

    @abc.abstractmethod
    def get_triggers(self) -> list[dict[str, Any]]:
        """Return list of trigger definitions this agent responds to."""
        ...

    # -- Event helpers ----------------------------------------------------

    async def emit_event(
        self,
        event_type: str,
        payload: dict[str, Any],
        target_agent: str = "decision",
        priority: AgentPriority = AgentPriority.P2,
        correlation_id: str | None = None,
    ) -> str:
        """Emit an event onto the Redis event bus."""
        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_agent": self.agent_name,
            "target_agent": target_agent,
            "event_type": event_type,
            "priority": priority.value,
            "payload": payload,
            "correlation_id": correlation_id or event_id,
            "ttl_seconds": 3600,
        }
        if self.event_bus:
            await self.event_bus.publish(event)
        self._metrics["events_emitted"] += 1
        logger.debug("[%s] Emitted event: %s -> %s", self.agent_name, event_type, target_agent)
        return event_id

    # -- Run wrapper ------------------------------------------------------

    async def run(self, task_payload: dict[str, Any]) -> dict[str, Any]:
        """
        Full lifecycle wrapper: init -> execute -> report -> cleanup.
        Handles state transitions, error handling, and metrics.
        """
        self._started_at = datetime.now(timezone.utc)
        self.transition("start")

        try:
            result = await self.execute(task_payload)
            self.transition("complete")
            self._metrics["tasks_completed"] += 1
            self._retry_count = 0

            # Emit completion event
            await self.emit_event(
                event_type=f"{self.agent_name}.task.completed",
                payload={"result": result, "duration_ms": self._duration_ms()},
            )

            self.transition("done")
            return {"status": "success", "result": result}

        except Exception as exc:
            self._last_error = str(exc)
            self._metrics["tasks_failed"] += 1
            self.transition("fail")
            logger.error("[%s] Execution failed: %s", self.agent_name, exc, exc_info=True)

            # Attempt retry
            self._retry_count += 1
            max_retries = self.config.get("max_retries", 3)

            if self._retry_count <= max_retries:
                self.transition("retry")
                await self.emit_event(
                    event_type=f"{self.agent_name}.task.retrying",
                    payload={"error": str(exc), "attempt": self._retry_count},
                    priority=AgentPriority.P1,
                )
                return {"status": "retrying", "error": str(exc), "attempt": self._retry_count}
            else:
                self.transition("max_retries")
                await self.emit_event(
                    event_type=f"{self.agent_name}.task.dead_letter",
                    payload={"error": str(exc), "total_attempts": self._retry_count},
                    priority=AgentPriority.P0,
                )
                return {"status": "dead_letter", "error": str(exc)}

    # -- Utilities --------------------------------------------------------

    def _duration_ms(self) -> int:
        if self._started_at:
            delta = datetime.now(timezone.utc) - self._started_at
            return int(delta.total_seconds() * 1000)
        return 0

    @property
    def health(self) -> dict[str, Any]:
        """Return agent health status for monitoring endpoints."""
        return {
            "agent_name": self.agent_name,
            "agent_id": self.agent_id,
            "state": self.state.value,
            "started_at": self._started_at.isoformat() if self._started_at else None,
            "retry_count": self._retry_count,
            "last_error": self._last_error,
            "metrics": dict(self._metrics),
        }
