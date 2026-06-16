"""Jarvis Core — the executive layer every request passes through.

Pipeline: intent → decompose into a Plan → dispatch tasks to agents
(respecting dependencies, parallelising what it can) → synthesise a final answer.

Degrades gracefully: if NIM is unavailable, a heuristic planner keeps the path runnable.
"""
from __future__ import annotations

import asyncio
import json

from app.agents.registry import AgentRegistry
from app.core.events import event_bus
from app.core.logging import get_logger
from app.domain.entities import Plan, Task
from app.domain.enums import AgentRole, TaskStatus
from app.infrastructure.nim.client import NIMError
from app.infrastructure.nim.router import NIMRouter

log = get_logger("jarvis.core")

_PLANNER_PROMPT = (
    "You are JARVIS's planning kernel. Decompose the user's request into a minimal "
    "list of tasks. Reply with ONLY a JSON array; each item has keys: "
    '"objective" (string) and "role" (one of: research, coding, planning, analysis, '
    "executive, automation, memory, maintenance). Order implies sequence."
)


class JarvisCore:
    def __init__(self, router: NIMRouter, agents: AgentRegistry,
                 context_engine=None, compressor=None) -> None:
        self._router = router
        self._agents = agents
        self._context = context_engine   # ContextAssemblyEngine | None
        self._compressor = compressor    # MemoryCompressor | None

    # -- planning --------------------------------------------------------
    async def decompose(self, request: str) -> Plan:
        try:
            raw = await self._router.complete(
                AgentRole.PLANNING,
                [{"role": "system", "content": _PLANNER_PROMPT},
                 {"role": "user", "content": request}],
            )
            items = json.loads(raw[raw.find("["): raw.rfind("]") + 1])
            tasks = [Task(objective=i["objective"], role=AgentRole(i["role"])) for i in items]
            if tasks:
                return Plan(request=request, tasks=tasks)
        except (NIMError, json.JSONDecodeError, KeyError, ValueError) as exc:
            log.info("planner_fallback", reason=str(exc))
        # Heuristic fallback: single research task.
        return Plan(request=request, tasks=[Task(objective=request, role=AgentRole.RESEARCH)])

    # -- execution -------------------------------------------------------
    async def _run_task(self, task: Task, context: str) -> None:
        task.mark(TaskStatus.RUNNING)
        await event_bus.publish("task.started", {"id": task.id, "role": task.role})
        try:
            agent = self._agents.get(task.role)
            if self._context is not None:
                pkg = await self._context.assemble(task.objective, active_context=context)
                context = pkg.text or context
                await event_bus.publish("context.assembled",
                    {"task": task.id, "tokens": pkg.token_estimate, "layers": pkg.layers_used})
            result = await agent.run(task.objective, context=context)
            task.mark(TaskStatus.SUCCEEDED, result=result)
            await event_bus.publish("task.succeeded", {"id": task.id})
        except Exception as exc:  # noqa: BLE001
            task.mark(TaskStatus.FAILED, error=str(exc))
            await event_bus.publish("task.failed", {"id": task.id, "error": str(exc)})

    async def execute(self, plan: Plan) -> Plan:
        """Run a plan, dispatching dependency-ready tasks in parallel each wave."""
        done: set[str] = set()
        while True:
            ready = plan.ready_tasks(done)
            if not ready:
                break
            context = "\n".join(
                f"[{t.role}] {t.result}" for t in plan.tasks if t.result
            )
            await asyncio.gather(*(self._run_task(t, context) for t in ready))
            done |= {t.id for t in plan.tasks if t.status in (TaskStatus.SUCCEEDED, TaskStatus.FAILED)}
            if all(t.status != TaskStatus.PENDING for t in plan.tasks):
                break
        return plan

    async def synthesize(self, plan: Plan) -> str:
        succeeded = [t for t in plan.tasks if t.status == TaskStatus.SUCCEEDED]
        if not succeeded:
            return "No tasks completed successfully."
        if len(succeeded) == 1:
            return succeeded[0].result or ""
        digest = "\n\n".join(f"## {t.role}\n{t.result}" for t in succeeded)
        try:
            return await self._router.complete(
                AgentRole.EXECUTIVE,
                [{"role": "system", "content": "Synthesise these agent outputs into one coherent answer."},
                 {"role": "user", "content": digest}],
            )
        except NIMError:
            return digest

    # -- public entrypoint ----------------------------------------------
    async def handle(self, request: str) -> dict:
        await event_bus.publish("request.received", {"request": request})
        plan = await self.decompose(request)
        await self.execute(plan)
        answer = await self.synthesize(plan)
        if self._compressor is not None and answer:
            try:
                await self._compressor.to_knowledge(
                    f"Request: {request}\n\n{answer}", title=request[:60], folder="Reports")
            except Exception as exc:  # noqa: BLE001
                log.warning("persist_failed", error=str(exc))
        await event_bus.publish("request.completed", {"plan_id": plan.id})
        return {
            "plan_id": plan.id,
            "answer": answer,
            "tasks": [
                {"id": t.id, "role": t.role, "objective": t.objective,
                 "status": t.status, "result": t.result, "error": t.error}
                for t in plan.tasks
            ],
        }
