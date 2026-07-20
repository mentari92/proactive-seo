"""
AgentRegistry -- centralized registry for all agents.

Agents register themselves at startup; the registry provides
lookup, health checks, and lifecycle management.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Type

from app.agents.base import BaseAgent

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Central registry for all ProActive SEO agents.

    Usage:
        registry = AgentRegistry()
        registry.register(SentinelAgent, config={...})
        sentinel = registry.get("sentinel")
        await sentinel.run(task_payload)
    """

    def __init__(self):
        self._agent_classes: dict[str, Type[BaseAgent]] = {}
        self._agent_instances: dict[str, BaseAgent] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    # -- Registration -----------------------------------------------------

    def register(
        self,
        agent_class: Type[BaseAgent],
        config: dict[str, Any] | None = None,
        event_bus: Any | None = None,
        db_session: Any | None = None,
    ) -> BaseAgent:
        """Register an agent class and create its instance."""
        agent = agent_class(
            config=config or {},
            event_bus=event_bus,
            db_session=db_session,
        )
        name = agent.agent_name

        if name in self._agent_instances:
            logger.warning("[registry] Replacing existing agent: %s", name)

        self._agent_classes[name] = agent_class
        self._agent_instances[name] = agent
        self._metadata[name] = {
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "class": agent_class.__name__,
            "version": agent.agent_version,
        }

        logger.info("[registry] Registered agent: %s (%s)", name, agent_class.__name__)
        return agent

    def unregister(self, agent_name: str) -> bool:
        """Remove an agent from the registry."""
        if agent_name not in self._agent_instances:
            return False
        del self._agent_instances[agent_name]
        del self._agent_classes[agent_name]
        del self._metadata[agent_name]
        logger.info("[registry] Unregistered agent: %s", agent_name)
        return True

    # -- Lookup -----------------------------------------------------------

    def get(self, agent_name: str) -> BaseAgent | None:
        """Get an agent instance by name."""
        return self._agent_instances.get(agent_name)

    def get_all(self) -> dict[str, BaseAgent]:
        """Get all registered agent instances."""
        return dict(self._agent_instances)

    def get_by_capability(self, capability: str) -> list[BaseAgent]:
        """Find agents that have a specific capability (based on triggers)."""
        matches = []
        for agent in self._agent_instances.values():
            triggers = agent.get_triggers()
            for trigger in triggers:
                if capability in trigger.get("condition", ""):
                    matches.append(agent)
                    break
        return matches

    # -- Health -----------------------------------------------------------

    def health_check(self) -> dict[str, Any]:
        """Get health status of all registered agents."""
        return {
            name: agent.health
            for name, agent in self._agent_instances.items()
        }

    def get_registry_info(self) -> dict[str, Any]:
        """Get full registry information."""
        return {
            "total_agents": len(self._agent_instances),
            "agents": {
                name: {
                    "state": agent.state.value,
                    "version": agent.agent_version,
                    "triggers": agent.get_triggers(),
                    **self._metadata.get(name, {}),
                }
                for name, agent in self._agent_instances.items()
            },
        }

    # -- Lifecycle --------------------------------------------------------

    async def init_all(self) -> None:
        """Initialize all registered agents."""
        for name, agent in self._agent_instances.items():
            try:
                await agent.on_init()
                logger.info("[registry] Initialized agent: %s", name)
            except Exception as exc:
                logger.error("[registry] Failed to init agent %s: %s", name, exc)

    async def shutdown_all(self) -> None:
        """Shut down all registered agents."""
        for name, agent in self._agent_instances.items():
            try:
                await agent.on_shutdown()
                logger.info("[registry] Shut down agent: %s", name)
            except Exception as exc:
                logger.error("[registry] Failed to shutdown agent %s: %s", name, exc)

    # -- Convenience ------------------------------------------------------

    @property
    def agent_names(self) -> list[str]:
        return list(self._agent_instances.keys())

    def __len__(self) -> int:
        return len(self._agent_instances)

    def __contains__(self, agent_name: str) -> bool:
        return agent_name in self._agent_instances

    def __repr__(self) -> str:
        return f"AgentRegistry(agents={self.agent_names})"
