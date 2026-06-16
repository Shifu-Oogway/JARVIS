from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_agents
from app.agents.registry import AgentRegistry
from app.domain.enums import AgentRole
from app.infrastructure.nim.registry import model_registry

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
async def list_agents(agents: AgentRegistry = Depends(get_agents)) -> list[dict]:
    out = []
    for role, agent in agents.all().items():
        out.append({
            "role": role,
            "status": agent.state.status,
            "current_task": agent.state.current_task,
            "queue_depth": agent.state.queue_depth,
            "model": model_registry.for_role(role).name,
            "metrics": {
                "invocations": agent.metrics.invocations,
                "failures": agent.metrics.failures,
                "avg_latency_s": round(agent.metrics.avg_latency_s, 3),
            },
        })
    return out


@router.post("/{role}/run")
async def run_agent(role: AgentRole, body: dict, agents: AgentRegistry = Depends(get_agents)) -> dict:
    objective = body.get("objective")
    if not objective:
        raise HTTPException(422, "objective is required")
    result = await agents.get(role).run(objective)
    return {"role": role, "result": result}
