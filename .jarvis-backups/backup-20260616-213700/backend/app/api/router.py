from fastapi import APIRouter

from app.api.routes import agents, chat, health, ws

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(agents.router)
api_router.include_router(chat.router)
api_router.include_router(ws.router)
