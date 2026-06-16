"""Concrete example agent. Other roles follow the same shape (Phase 2)."""
from app.agents.base import BaseAgent
from app.domain.enums import AgentRole


class ResearchAgent(BaseAgent):
    role = AgentRole.RESEARCH
    system_prompt = (
        "You are JARVIS's Research Agent. Gather, synthesise, and cite information "
        "concisely. Prefer primary sources. Flag uncertainty explicitly."
    )
