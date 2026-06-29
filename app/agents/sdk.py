"""
ILLIP Agent SDK — base class for third-party agent development.

Install ILLIP as a package (pip install -e .) then:

    from app.agents.sdk import IllipAgent, register_agent

    class MyAgent(IllipAgent):
        name = "my_agent"
        description = "Does cool things"

        async def process(self, task: str, context: dict = {}) -> str:
            return f"Processed: {task}"

    register_agent(MyAgent())

Agents appear in GET /api/agents and can be triggered via the event bus.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.utils import logger

_REGISTRY: dict[str, "IllipAgent"] = {}


class IllipAgent(ABC):
    """Base class for external ILLIP agents."""

    name: str = "unnamed"
    description: str = ""
    version: str = "0.1.0"

    # Override to declare env vars or pip packages this agent needs
    requires_env: list[str] = []
    requires_packages: list[str] = []

    @abstractmethod
    async def process(self, task: str, context: Dict[str, Any] = {}) -> str:
        """Run the agent on a task. Return result string."""

    async def on_event(self, event_type: str, payload: Dict[str, Any]) -> Optional[str]:
        """Handle bus events. Override to react to system events."""
        return None

    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "requires_env": self.requires_env,
            "requires_packages": self.requires_packages,
        }


def register_agent(agent: IllipAgent) -> None:
    """Register an agent instance. Call at module import time."""
    _REGISTRY[agent.name] = agent
    logger.info(f"Agent registered: {agent.name} v{agent.version}")


def get_agent(name: str) -> Optional[IllipAgent]:
    return _REGISTRY.get(name)


def list_agents() -> list[Dict[str, Any]]:
    return [a.metadata() for a in _REGISTRY.values()]


async def run_agent(name: str, task: str, context: Dict[str, Any] = {}) -> str:
    """Run a registered agent by name."""
    agent = get_agent(name)
    if agent is None:
        raise ValueError(f"No agent registered with name '{name}'")
    return await agent.process(task, context)


async def broadcast_event(event_type: str, payload: Dict[str, Any]) -> list[str]:
    """Broadcast event to all agents that handle it. Returns non-None responses."""
    tasks = [a.on_event(event_type, payload) for a in _REGISTRY.values()]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [r for r in results if isinstance(r, str)]
