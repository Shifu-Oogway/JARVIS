"""JARVIS backend entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.metrics import MetricsMiddleware, metrics_app

from app.agents.registry import AgentRegistry
from app.api.router import api_router
from app.core.config import get_settings
from app.core.events import event_bus
from app.core.logging import configure_logging, get_logger
from app.core_engine.jarvis_core import JarvisCore
from app.infrastructure.db.session import init_models
from app.infrastructure.nim.router import NIMRouter

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.debug)
    log.info("jarvis_boot", environment=settings.environment)

    await event_bus.connect()
    nim_router = NIMRouter()
    await nim_router.start()
    agents = AgentRegistry(nim_router)
    core = JarvisCore(nim_router, agents)

    app.state.nim_router = nim_router
    app.state.agents = agents
    app.state.core = core

    try:
        await init_models()
    except Exception as exc:  # noqa: BLE001 - boot without DB in pure-dev/offline runs
        log.warning("db_init_skipped", error=str(exc))

    yield

    await nim_router.stop()
    await event_bus.close()
    log.info("jarvis_shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="JARVIS", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(MetricsMiddleware)
    app.include_router(api_router)
    app.mount("/metrics", metrics_app)
    return app


app = create_app()
