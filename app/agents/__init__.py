"""Agent registry and discovery helpers."""

from typing import Dict, Optional
from app.agents.base_agent import BaseAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.builder_agent import BuilderAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.tester_agent import TesterAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.specialist_agents import (
    ResearchAgent, CodeAgent, WriterAgent, AnalystAgent, SummarizerAgent,
    TranslatorAgent, SchedulerAgent, QAAgent, DataAgent, EmailAgent,
    CEOAgent, DesignAgent, ContentAgent, SEOAgent, CustomerSupportAgent,
    ComplianceAgent, FinanceAgent, TravelAgent, SkillBuilderAgent,
    PluginReviewAgent, DigitalTwinAgent, IntegrationAgent,
)
from app.utils import logger


class AgentRegistry:
    """Create and expose the starter agents used by the API."""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self._initialize_agents()

    def _initialize_agents(self):
        """Instantiate each built-in agent once at startup."""
        agents = [
            PlannerAgent(),
            BuilderAgent(),
            ReviewerAgent(),
            TesterAgent(),
            MemoryAgent(),
            ResearchAgent(),
            CodeAgent(),
            WriterAgent(),
            AnalystAgent(),
            SummarizerAgent(),
            TranslatorAgent(),
            SchedulerAgent(),
            QAAgent(),
            DataAgent(),
            EmailAgent(),
            CEOAgent(),
            DesignAgent(),
            ContentAgent(),
            SEOAgent(),
            CustomerSupportAgent(),
            ComplianceAgent(),
            FinanceAgent(),
            TravelAgent(),
            SkillBuilderAgent(),
            PluginReviewAgent(),
            DigitalTwinAgent(),
            IntegrationAgent(),
        ]
        
        for agent in agents:
            self.agents[agent.agent_type] = agent
            logger.info(f"Registered agent: {agent.agent_type}")
    
    def get_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """Return an agent by type, or None when it is unknown."""
        return self.agents.get(agent_type)
    
    def list_agents(self) -> Dict[str, BaseAgent]:
        """Return a copy of the registered agent map."""
        return self.agents.copy()
    
    def get_available_agents(self) -> list:
        """Return the agent types currently available for execution."""
        return [
            agent_type for agent_type, agent in self.agents.items()
            if agent.is_available
        ]
    
    def get_agent_status(self, agent_type: str) -> Optional[Dict]:
        """Return API-friendly status for one agent."""
        agent = self.get_agent(agent_type)
        if agent:
            return agent.to_dict()
        return None
    
    def get_all_agents_status(self) -> list:
        """Return API-friendly status for every registered agent."""
        return [agent.to_dict() for agent in self.agents.values()]


# Global registry instance
_registry: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Get or create the global agent registry"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
