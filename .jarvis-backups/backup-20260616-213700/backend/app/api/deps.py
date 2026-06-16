"""Dependency providers — pull singletons off app.state."""
from fastapi import Request

from app.agents.registry import AgentRegistry
from app.core_engine.jarvis_core import JarvisCore
from app.infrastructure.nim.router import NIMRouter


def get_router(request: Request) -> NIMRouter:
    return request.app.state.nim_router


def get_agents(request: Request) -> AgentRegistry:
    return request.app.state.agents


def get_core(request: Request) -> JarvisCore:
    return request.app.state.core
