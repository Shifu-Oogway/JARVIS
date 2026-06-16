"""Smoke tests that exercise the request path without a live NIM endpoint."""
import pytest

from app.agents.registry import AgentRegistry
from app.core_engine.jarvis_core import JarvisCore
from app.domain.entities import Plan, Task
from app.domain.enums import AgentRole, TaskStatus
from app.infrastructure.nim.router import NIMRouter


def test_plan_dependency_resolution():
    a = Task(objective="a", role=AgentRole.RESEARCH)
    b = Task(objective="b", role=AgentRole.ANALYSIS, depends_on=[a.id])
    plan = Plan(request="x", tasks=[a, b])
    ready = plan.ready_tasks(done=set())
    assert ready == [a]                       # b is blocked on a
    a.mark(TaskStatus.SUCCEEDED)
    assert plan.ready_tasks(done={a.id}) == [b]


@pytest.mark.asyncio
async def test_core_handles_offline():
    # No NIM key configured -> planner falls back, agents error per task,
    # but the executive path stays intact and returns a structured result.
    router = NIMRouter()
    core = JarvisCore(router, AgentRegistry(router))
    result = await core.handle("Summarise the NVIDIA earnings call")
    assert "plan_id" in result and "tasks" in result
    await router.stop()
