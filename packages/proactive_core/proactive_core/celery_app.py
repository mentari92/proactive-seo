"""Celery configuration, routing, retries, and dead-letter conventions."""

from __future__ import annotations

import json
from typing import Any

from celery import Celery, Task
from redis import Redis

from proactive_core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "proactive_seo",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["proactive_core.agent_tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    result_expires=86_400,
    broker_transport_options={"visibility_timeout": 3600},
    task_routes={
        f"proactive.agent.{name}": {"queue": f"agent.{name}"}
        for name in ("crawl", "content", "technical", "rank", "outreach", "competitor", "decision", "executor")
    },
    beat_schedule={
        "decision-engine-tick": {
            "task": "proactive.scheduler.decision_tick",
            "schedule": 60.0,
            "args": ({"trigger": "schedule"},),
        }
    },
)


class RetryingTask(Task):
    """Task base with bounded exponential retry and jitter."""

    autoretry_for = (TimeoutError, ConnectionError)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5

    def on_failure(
        self,
        exc: BaseException,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        """Record terminal failures in a bounded Redis dead-letter list."""
        queue = self.request.delivery_info.get("routing_key", "unknown")
        record = json.dumps(
            {
                "task": self.name,
                "task_id": task_id,
                "queue": queue,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "args": args,
                "kwargs": kwargs,
            },
            default=str,
        )
        try:
            client = Redis.from_url(settings.redis_url)
            key = f"proactive:dlq:{queue}"
            client.lpush(key, record)
            client.ltrim(key, 0, 9_999)
            client.expire(key, 2_592_000)
            client.close()
        except Exception:
            return


@celery_app.task(name="proactive.scheduler.decision_tick", base=RetryingTask)
def decision_tick(payload: dict[str, Any]) -> dict[str, Any]:
    """Scheduler heartbeat consumed by the async decision-engine runner."""
    return {"accepted": True, "payload": payload}
