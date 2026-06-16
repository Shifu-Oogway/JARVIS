"""BaseAgent — the contract every JARVIS agent fulfils.

Each agent owns: state, short-term memory, a tool registry, metrics, and permissions.
Agents are model-agnostic: they call the NIM router by role, so swapping the underlying
model is a registry change, not a code change.
"""
from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from app.core.events import event_bus
from app.core.logging import get_logger
from app.domain.enums import AgentRole, AgentStatus
from app.infrastructure.nim.router import NIMRouter

Tool = Callable[..., Awaitable[str]]


@dataclass
class AgentMetrics:
    invocations: int = 0
    failures: int = 0
    total_latency_s: float = 0.0

    @property
    def avg_latency_s(self) -> float:
        return self.total_latency_s / self.invocations if self.invocations else 0.0


@dataclass
class AgentState:
    status: AgentStatus = AgentStatus.IDLE
    current_task: str | None = None
    queue_depth: int = 0


class BaseAgent:
    role: AgentRole
    system_prompt: str = "You are a helpful JARVIS agent."

    def __init__(self, router: NIMRouter, permissions: set[str] | None = None) -> None:
        self._router = router
        self.state = AgentState()
        self.metrics = AgentMetrics()
        self.permissions: set[str] = permissions or set()
        self.memory: list[dict] = []                 # short-term rolling memory
        self.tools: dict[str, Tool] = {}
        self.log = get_logger(f"agent.{self.role}")

    # -- tools -----------------------------------------------------------
    def register_tool(self, name: str, fn: Tool) -> None:
        self.tools[name] = fn

    async def use_tool(self, name: str, **kwargs) -> str:
        if name not in self.tools:
            raise KeyError(f"{self.role} has no tool {name!r}")
        return await self.tools[name](**kwargs)

    # -- execution -------------------------------------------------------
    async def run(self, objective: str, context: str = "") -> str:
        self.state.status = AgentStatus.BUSY
        self.state.current_task = objective
        self.metrics.invocations += 1
        started = time.perf_counter()
        await event_bus.publish("agent.started", {"role": self.role, "objective": objective})
        try:
            messages = [
                {"role": "system", "content": self.system_prompt},
                *self.memory[-6:],
                {"role": "user", "content": f"{context}\n\nObjective: {objective}".strip()},
            ]
            result = await self._execute(objective, messages)
            self.memory.append({"role": "assistant", "content": result[:2000]})
            await event_bus.publish("agent.succeeded", {"role": self.role, "objective": objective})
            return result
        except Exception as exc:  # noqa: BLE001
            self.metrics.failures += 1
            self.state.status = AgentStatus.ERROR
            await event_bus.publish("agent.failed", {"role": self.role, "error": str(exc)})
            raise
        finally:
            self.metrics.total_latency_s += time.perf_counter() - started
            self.state.status = AgentStatus.IDLE
            self.state.current_task = None

    async def _execute(self, objective: str, messages: list[dict]) -> str:
        """Default execution = single NIM completion. Override for tool loops."""
        return await self._router.complete(self.role, messages)
