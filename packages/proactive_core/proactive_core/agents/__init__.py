"""Canonical agent registry.

8 AI agents for enterprise SEO automation:
  - Sentinel, Technical, Forge, Scout, Outreach, Competitor, Decision, Executor
  - Rich source implementations in source_agents/ (original business logic)
"""

from proactive_core.agents.implementations import AGENTS

__all__ = ["AGENTS"]
