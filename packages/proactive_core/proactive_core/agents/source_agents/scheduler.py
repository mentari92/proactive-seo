"""
AgentScheduler -- schedules and dispatches agent tasks.

Handles cron-based scheduling, event-triggered dispatch,
and priority-based task queuing.
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine

from app.agents.base import AgentPriority, BaseAgent

logger = logging.getLogger(__name__)


class ScheduleType(str, Enum):
    CRON = "cron"
    INTERVAL = "interval"
    EVENT = "event"
    ONCE = "once"


class ScheduledTask:
    """A single scheduled task entry."""

    def __init__(
        self,
        task_id: str,
        agent_name: str,
        task_payload: dict[str, Any],
        schedule_type: ScheduleType,
        priority: AgentPriority = AgentPriority.P2,
        cron: str | None = None,
        interval_seconds: int | None = None,
        event_trigger: str | None = None,
    ):
        self.task_id = task_id
        self.agent_name = agent_name
        self.task_payload = task_payload
        self.schedule_type = schedule_type
        self.priority = priority
        self.cron = cron
        self.interval_seconds = interval_seconds
        self.event_trigger = event_trigger
        self.last_run: datetime | None = None
        self.next_run: datetime | None = None
        self.run_count: int = 0
        self.enabled: bool = True

    def __lt__(self, other: ScheduledTask) -> bool:
        """For priority queue ordering."""
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
        return priority_order.get(self.priority.value, 9) < priority_order.get(other.priority.value, 9)


class AgentScheduler:
    """
    Manages scheduled and event-triggered agent task dispatch.

    Usage:
        scheduler = AgentScheduler(registry)
        scheduler.add_schedule(task)
        scheduler.register_event_handler("crawl.complete", handler)
        await scheduler.start()
    """

    def __init__(self, registry: Any):
        self.registry = registry
        self._schedules: dict[str, ScheduledTask] = {}
        self._event_handlers: dict[str, list[Callable[..., Coroutine[Any, Any, None]]]] = {}
        self._priority_queue: list[ScheduledTask] = []
        self._running = False
        self._dispatch_count: int = 0
        self._error_count: int = 0

    # -- Schedule management ----------------------------------------------

    def add_schedule(self, task: ScheduledTask) -> None:
        """Add or update a scheduled task."""
        self._schedules[task.task_id] = task
        if task.schedule_type in (ScheduleType.CRON, ScheduleType.INTERVAL):
            heapq.heappush(self._priority_queue, task)
        logger.info(
            "[scheduler] Added schedule: %s -> %s (%s)",
            task.task_id, task.agent_name, task.schedule_type.value,
        )

    def remove_schedule(self, task_id: str) -> bool:
        """Remove a scheduled task."""
        if task_id in self._schedules:
            del self._schedules[task_id]
            logger.info("[scheduler] Removed schedule: %s", task_id)
            return True
        return False

    def enable_schedule(self, task_id: str) -> bool:
        if task_id in self._schedules:
            self._schedules[task_id].enabled = True
            return True
        return False

    def disable_schedule(self, task_id: str) -> bool:
        if task_id in self._schedules:
            self._schedules[task_id].enabled = False
            return True
        return False

    # -- Event handlers ---------------------------------------------------

    def register_event_handler(
        self,
        event_type: str,
        handler: Callable[..., Coroutine[Any, Any, None]],
    ) -> None:
        """Register a handler for a specific event type."""
        self._event_handlers.setdefault(event_type, []).append(handler)
        logger.debug("[scheduler] Registered handler for event: %s", event_type)

    async def handle_event(self, event: dict[str, Any]) -> None:
        """Dispatch an event to all registered handlers."""
        event_type = event.get("event_type", "")
        handlers = self._event_handlers.get(event_type, [])
        handlers.extend(self._event_handlers.get("*", []))   # Wildcard handlers

        for handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                self._error_count += 1
                logger.error("[scheduler] Event handler error for %s: %s", event_type, exc)

        # Check event-triggered schedules
        for task in self._schedules.values():
            if (
                task.schedule_type == ScheduleType.EVENT
                and task.event_trigger == event_type
                and task.enabled
            ):
                await self._dispatch(task, trigger_event=event)

    # -- Dispatch ---------------------------------------------------------

    async def _dispatch(
        self,
        task: ScheduledTask,
        trigger_event: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Dispatch a task to its target agent."""
        agent = self.registry.get(task.agent_name)
        if agent is None:
            logger.error("[scheduler] Agent not found: %s", task.agent_name)
            return None

        payload = dict(task.task_payload)
        if trigger_event:
            payload["trigger_event"] = trigger_event

        try:
            result = await agent.run(payload)
            task.last_run = datetime.now(timezone.utc)
            task.run_count += 1
            self._dispatch_count += 1
            logger.info(
                "[scheduler] Dispatched %s to %s: %s",
                task.task_id, task.agent_name, result.get("status", "unknown"),
            )
            return result
        except Exception as exc:
            self._error_count += 1
            logger.error("[scheduler] Dispatch failed for %s: %s", task.task_id, exc)
            return None

    async def dispatch_priority(
        self,
        agent_name: str,
        task_payload: dict[str, Any],
        priority: AgentPriority = AgentPriority.P0,
    ) -> dict[str, Any] | None:
        """Immediately dispatch a high-priority task."""
        task = ScheduledTask(
            task_id=f"priority-{agent_name}-{int(time.time())}",
            agent_name=agent_name,
            task_payload=task_payload,
            schedule_type=ScheduleType.ONCE,
            priority=priority,
        )
        return await self._dispatch(task)

    # -- Scheduler loop ---------------------------------------------------

    async def start(self, check_interval: float = 60.0) -> None:
        """Start the scheduler loop."""
        self._running = True
        logger.info("[scheduler] Started with check interval: %.1fs", check_interval)

        while self._running:
            now = datetime.now(timezone.utc)
            await self._check_due_tasks(now)
            await asyncio.sleep(check_interval)

    async def stop(self) -> None:
        """Stop the scheduler loop."""
        self._running = False
        logger.info("[scheduler] Stopped")

    async def _check_due_tasks(self, now: datetime) -> None:
        """Check and dispatch any due tasks."""
        for task in self._schedules.values():
            if not task.enabled:
                continue
            if task.schedule_type not in (ScheduleType.CRON, ScheduleType.INTERVAL):
                continue

            if self._is_due(task, now):
                await self._dispatch(task)

    def _is_due(self, task: ScheduledTask, now: datetime) -> bool:
        """Check if a task is due for execution."""
        if task.schedule_type == ScheduleType.INTERVAL:
            if task.last_run is None:
                return True
            elapsed = (now - task.last_run).total_seconds()
            return elapsed >= (task.interval_seconds or 3600)

        # Cron tasks: simplified check (in production, use croniter)
        if task.last_run is None:
            return True
        elapsed = (now - task.last_run).total_seconds()
        return elapsed >= 3600   # Minimum 1 hour between runs

    # -- Status -----------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        return {
            "total_schedules": len(self._schedules),
            "enabled_schedules": sum(1 for t in self._schedules.values() if t.enabled),
            "total_dispatches": self._dispatch_count,
            "total_errors": self._error_count,
            "running": self._running,
        }

    def get_schedules(self) -> list[dict[str, Any]]:
        """List all registered schedules."""
        return [
            {
                "task_id": task.task_id,
                "agent_name": task.agent_name,
                "schedule_type": task.schedule_type.value,
                "priority": task.priority.value,
                "enabled": task.enabled,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "run_count": task.run_count,
            }
            for task in self._schedules.values()
        ]
