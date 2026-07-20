"""Celery entry points for all eight canonical agents."""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import BaseModel

from proactive_core.agents.base import AgentContext
from proactive_core.agents.implementations import (
    AGENTS,
    ActionInput,
    CompetitorInput,
    ContentAuditInput,
    CrawlInput,
    DecisionInput,
    OutreachInput,
    RankInput,
    TechnicalInput,
)
from proactive_core.celery_app import RetryingTask, celery_app

INPUT_MODELS: dict[str, type[BaseModel]] = {
    "sentinel": CrawlInput,
    "forge": ContentAuditInput,
    "technical": TechnicalInput,
    "scout": RankInput,
    "outreach": OutreachInput,
    "competitor": CompetitorInput,
    "decision": DecisionInput,
    "executor": ActionInput,
}


def run_agent(agent_key: str, payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Validate and execute one agent in a worker process."""
    input_data = INPUT_MODELS[agent_key].model_validate(payload)
    agent_context = AgentContext.model_validate(context)
    result = asyncio.run(AGENTS[agent_key].run(input_data, agent_context))
    return result.model_dump(mode="json")


@celery_app.task(name="proactive.agent.crawl", base=RetryingTask)
def crawl(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute Sentinel crawling and broken-link detection."""
    return run_agent("sentinel", payload, context)


@celery_app.task(name="proactive.agent.content", base=RetryingTask)
def content(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute Forge content scoring and optimization analysis."""
    return run_agent("forge", payload, context)


@celery_app.task(name="proactive.agent.technical", base=RetryingTask)
def technical(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute the Technical agent audit."""
    return run_agent("technical", payload, context)


@celery_app.task(name="proactive.agent.rank", base=RetryingTask)
def rank(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute Scout rank normalization."""
    return run_agent("scout", payload, context)


@celery_app.task(name="proactive.agent.outreach", base=RetryingTask)
def outreach(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute approval-gated outreach sequence planning."""
    return run_agent("outreach", payload, context)


@celery_app.task(name="proactive.agent.competitor", base=RetryingTask)
def competitor(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute competitor opportunity detection."""
    return run_agent("competitor", payload, context)


@celery_app.task(name="proactive.agent.decision", base=RetryingTask)
def decision(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute priority and resource-allocation scoring."""
    return run_agent("decision", payload, context)


@celery_app.task(name="proactive.agent.executor", base=RetryingTask)
def executor(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Execute the final side-effect gate and rollback capture."""
    return run_agent("executor", payload, context)
