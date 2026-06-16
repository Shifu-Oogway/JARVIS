"""Model capability registry — maps agent roles to NIM models and their capabilities.

Configurable via config files / UI later; sensible defaults shipped here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import AgentRole


@dataclass(frozen=True, slots=True)
class ModelSpec:
    name: str                       # NIM model id, e.g. "meta/llama-3.3-70b-instruct"
    role: AgentRole
    context_window: int = 8192
    max_concurrency: int = 4
    capabilities: frozenset[str] = field(default_factory=frozenset)


# Default routing table. Swap model ids for whatever your NIM gateway serves.
_DEFAULT: list[ModelSpec] = [
    ModelSpec("meta/llama-3.3-70b-instruct", AgentRole.RESEARCH, 128000, 4, frozenset({"chat", "tools", "long_context"})),
    ModelSpec("meta/codellama-70b", AgentRole.CODING, 16384, 4, frozenset({"chat", "code"})),
    ModelSpec("nvidia/nemotron-4-340b-instruct", AgentRole.PLANNING, 4096, 2, frozenset({"chat", "reasoning"})),
    ModelSpec("meta/llama-3.3-70b-instruct", AgentRole.ANALYSIS, 128000, 4, frozenset({"chat", "tools"})),
    ModelSpec("meta/llama-3.3-70b-instruct", AgentRole.EXECUTIVE, 128000, 2, frozenset({"chat"})),
    ModelSpec("meta/llama-3.1-8b-instruct", AgentRole.AUTOMATION, 8192, 8, frozenset({"chat", "fast"})),
    ModelSpec("meta/llama-3.1-8b-instruct", AgentRole.MEMORY, 8192, 8, frozenset({"chat", "fast"})),
    ModelSpec("meta/llama-3.1-8b-instruct", AgentRole.MAINTENANCE, 8192, 4, frozenset({"chat", "fast"})),
]


class ModelRegistry:
    def __init__(self, specs: list[ModelSpec] | None = None) -> None:
        self._by_role: dict[AgentRole, ModelSpec] = {s.role: s for s in (specs or _DEFAULT)}

    def for_role(self, role: AgentRole) -> ModelSpec:
        if role not in self._by_role:
            raise KeyError(f"No model registered for role {role!r}")
        return self._by_role[role]

    def upsert(self, spec: ModelSpec) -> None:
        self._by_role[spec.role] = spec

    def all(self) -> list[ModelSpec]:
        return list(self._by_role.values())


model_registry = ModelRegistry()
