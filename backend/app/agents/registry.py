"""Instantiates and holds the live agent roster."""
from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.memory_agent import MemoryAgent
from app.agents.research_agent import ResearchAgent
from app.domain.enums import AgentRole
from app.infrastructure.nim.router import NIMRouter


class _GenericAgent(BaseAgent):
    """Stand-in for roles whose specialised subclass lands in Phase 2."""
    def __init__(self, role: AgentRole, router: NIMRouter) -> None:
        self.role = role
        self.system_prompt = f"You are JARVIS's {role.value} agent."
        super().__init__(router)


class AgentRegistry:
    def __init__(self, router: NIMRouter) -> None:
        self._agents: dict[AgentRole, BaseAgent] = {
            AgentRole.RESEARCH: ResearchAgent(router),
            AgentRole.MEMORY: MemoryAgent(router),
        }
        for role in AgentRole:
            self._agents.setdefault(role, _GenericAgent(role, router))

    def get(self, role: AgentRole) -> BaseAgent:
        return self._agents[role]

    def all(self) -> dict[AgentRole, BaseAgent]:
        return dict(self._agents)
