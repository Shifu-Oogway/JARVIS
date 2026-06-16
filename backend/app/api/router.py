from fastapi import APIRouter

from app.api.routes import agents, chat, health, memory, ws

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(agents.router)
api_router.include_router(chat.router)
api_router.include_router(memory.router)
api_router.include_router(memory.vault_router)
api_router.include_router(ws.router)
