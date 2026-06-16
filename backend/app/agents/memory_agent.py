"""Memory Agent — maintains memory and synchronises the Obsidian vault."""
from app.agents.base import BaseAgent
from app.domain.enums import AgentRole


class MemoryAgent(BaseAgent):
    role = AgentRole.MEMORY
    system_prompt = (
        "You are JARVIS's Memory Agent. Summarise, deduplicate, and structure information "
        "into durable knowledge entries with clear titles, tags, and links."
    )
