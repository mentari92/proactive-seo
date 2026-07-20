"""Versioned agent event envelopes and Redis Streams transport."""

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from redis.asyncio import Redis
from uuid6 import uuid7


class EventPriority(StrEnum):
    """Cross-agent delivery priority."""

    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class AgentEvent(BaseModel):
    """Canonical, replayable event exchanged through Redis Streams."""

    version: int = 1
    id: UUID = Field(default_factory=uuid7)
    source: str
    target: str = "broadcast"
    type: str
    priority: EventPriority = EventPriority.NORMAL
    org_id: UUID
    project_id: UUID | None = None
    correlation_id: UUID = Field(default_factory=uuid7)
    trace_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(days=7))


class EventBus:
    """Redis Streams publisher with bounded stream retention."""

    def __init__(self, redis: Redis, stream: str = "proactive:events:v1") -> None:
        self._redis = redis
        self._stream = stream

    async def publish(self, event: AgentEvent) -> str:
        """Publish one event and return the Redis stream entry ID."""
        values: dict[Any, Any] = {"event": event.model_dump_json()}
        result = await self._redis.xadd(self._stream, values, maxlen=100_000, approximate=True)
        return result.decode() if isinstance(result, bytes) else str(result)
