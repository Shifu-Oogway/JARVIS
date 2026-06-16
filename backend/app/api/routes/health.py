from fastapi import APIRouter, Depends

from app.api.deps import get_router
from app.infrastructure.nim.router import NIMRouter

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(nim: NIMRouter = Depends(get_router)) -> dict:
    return {
        "status": "ok",
        "nim_endpoints": {
            c.base_url: nim.health.is_healthy(c.base_url) for c in nim._clients
        },
    }
