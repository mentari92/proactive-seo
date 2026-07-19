"""Shared lifecycle and result contracts for all eight AI agents."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from enum import StrEnum
from typing import Generic, TypeVar
from uuid import UUID

import structlog
from pydantic import BaseModel, Field
from uuid6 import uuid7

logger = structlog.get_logger(__name__)
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class RunStatus(StrEnum):
    """Agent lifecycle status."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentContext(BaseModel):
    """Tenant, trace, and resource context supplied to every agent run."""

    org_id: UUID
    project_id: UUID
    run_id: UUID = Field(default_factory=uuid7)
    correlation_id: UUID = Field(default_factory=uuid7)
    trace_id: str
    requested_by: UUID | None = None
    dry_run: bool = True
    budgets: dict[str, int] = Field(default_factory=dict)


class AgentResult(BaseModel, Generic[OutputT]):
    """Deterministic result envelope returned by every agent."""

    run_id: UUID
    agent: str
    status: RunStatus
    output: OutputT | None = None
    error: str | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    started_at: datetime
    completed_at: datetime


class Agent(ABC, Generic[InputT, OutputT]):
    """Base agent with validation, logging, metrics, and failure isolation."""

    key: str

    async def run(self, input_data: InputT, context: AgentContext) -> AgentResult[OutputT]:
        """Execute one lifecycle and convert failures to a stable result."""
        started = datetime.now(UTC)
        log = logger.bind(
            agent=self.key,
            run_id=str(context.run_id),
            org_id=str(context.org_id),
            project_id=str(context.project_id),
            trace_id=context.trace_id,
        )
        await log.ainfo("agent_run_started")
        try:
            output = await self.execute(input_data, context)
        except Exception as exc:
            await log.aexception("agent_run_failed", error_type=type(exc).__name__)
            return AgentResult(
                run_id=context.run_id,
                agent=self.key,
                status=RunStatus.FAILED,
                error=str(exc),
                started_at=started,
                completed_at=datetime.now(UTC),
            )
        completed = datetime.now(UTC)
        await log.ainfo("agent_run_completed", duration_ms=(completed - started).total_seconds() * 1000)
        return AgentResult(
            run_id=context.run_id,
            agent=self.key,
            status=RunStatus.COMPLETED,
            output=output,
            started_at=started,
            completed_at=completed,
        )

    @abstractmethod
    async def execute(self, input_data: InputT, context: AgentContext) -> OutputT:
        """Implement the agent-specific deterministic workflow."""
