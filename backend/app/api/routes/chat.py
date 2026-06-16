from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_core
from app.core_engine.jarvis_core import JarvisCore

router = APIRouter(prefix="/chat", tags=["jarvis"])


@router.post("")
async def chat(body: dict, core: JarvisCore = Depends(get_core)) -> dict:
    request = body.get("message")
    if not request:
        raise HTTPException(422, "message is required")
    return await core.handle(request)
